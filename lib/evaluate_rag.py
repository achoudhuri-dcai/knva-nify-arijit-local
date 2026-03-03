#!/usr/bin/env python3
"""
Offline RAG evaluation harness for NIFTY doc retrieval.

Focus:
1) Retrieval quality metrics (hit-rate, recall, MRR, latency)
2) Optional answer-generation checks (term recall + abstention rate)

Dataset format (JSONL, one object per line):
{
  "id": "q1",
  "question": "What does subtype mean?",
  "expected_sources": [
    {"document_name": "NIF Training Deck v4.pdf", "page_number": "24"}
  ],
  "expected_terms": ["subtype", "product type"]
}
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import knova_utils as utils


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_PAGE_IMAGES_DIR = ROOT_DIR / "assets" / "doc_images_and_summaries"
DEFAULT_DATASET_PATH = ROOT_DIR / "control_docs" / "rag_eval_questions.jsonl"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "logs"


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as err:
                raise ValueError(f"Invalid JSON at line {line_num} in {path}: {err}") from err
            if not isinstance(payload, dict):
                raise ValueError(f"Line {line_num} in {path} is not a JSON object.")
            rows.append(payload)
    return rows


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    sorted_values = sorted(float(v) for v in values)
    idx = (len(sorted_values) - 1) * pct
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _normalize_source_key(document_name: str, page_number: str) -> Tuple[str, str]:
    return (str(document_name or "").strip().lower(), str(page_number or "").strip())


def _normalize_expected_sources(payload: Dict[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    raw = payload.get("expected_sources", [])
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            _normalize_source_key(
                item.get("document_name", ""),
                item.get("page_number", ""),
            )
        )
    deduped = []
    seen = set()
    for item in out:
        if not item[0]:
            continue
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def _build_prompt(strict_grounding: bool) -> str:
    if strict_grounding:
        return """
You are answering a user question using images of retrieved training-document pages.

Grounding rules (strict):
- Use only information visible in the provided pages.
- Do not use outside knowledge or assumptions.
- If the pages are insufficient, unclear, or conflicting, reply exactly:
  "I don't have enough evidence in the retrieved training pages to answer that confidently."

Response requirements:
- Keep answer concise and factual.
- Do NOT include source citations, document names, or page numbers.
- Prefer direct wording from the page content when possible.
""".strip()

    return """
You are answering a user question using images of retrieved training-document pages.

If the pages are insufficient, say you could not find enough evidence.
Do not make up details.

Response requirements:
- Keep answer concise and factual.
- Do NOT include source citations, document names, or page numbers.
""".strip()


def _extract_hits_for_eval(
    query: str,
    provider: str,
    per_collection_k: int,
    max_total_pages: int,
    max_distance: Optional[float],
) -> Tuple[List[Dict[str, Any]], float]:
    embedding_model = utils.get_cached_retrieval_embedding_function(provider=provider)

    started = time.perf_counter()
    retrieved_docs_all_collections = utils.query_vectorstore(
        FOLDER_PATH=str(utils.VECTORSTORE_FOLDER),
        QUERY=query,
        N_RESULTS=per_collection_k,
        EMBEDDING_MODEL=embedding_model,
        USE_CACHE=True,
    )
    selected_hits = utils.select_vectorstore_hits(
        retrieved_docs_all_collections,
        max_total_results=max_total_pages,
        max_distance=max_distance,
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    return selected_hits, latency_ms


def _hit_to_eval_source(hit: Dict[str, Any]) -> Dict[str, Any]:
    metadata = hit.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    doc_name = str(metadata.get("document_name", "") or "").strip()
    page_num = str(metadata.get("page_number", "") or "").strip()
    return {
        "document_name": doc_name,
        "page_number": page_num,
        "distance": hit.get("distance"),
        "image_path": str(hit.get("document", "") or ""),
    }


def _compute_retrieval_metrics(
    selected_sources: List[Dict[str, Any]],
    expected_sources: List[Tuple[str, str]],
) -> Dict[str, Any]:
    metrics = {
        "expected_source_count": len(expected_sources),
        "matched_source_count": 0,
        "hit_at_k": None,
        "recall_at_k": None,
        "first_match_rank": None,
        "mrr": None,
    }

    if not expected_sources:
        return metrics

    expected_list = list(expected_sources)
    selected_keys = [
        _normalize_source_key(item.get("document_name", ""), item.get("page_number", ""))
        for item in selected_sources
    ]

    def _is_match(expected_key: Tuple[str, str], selected_key: Tuple[str, str]) -> bool:
        exp_doc, exp_page = expected_key
        sel_doc, sel_page = selected_key
        if exp_doc != sel_doc:
            return False
        # Document-level label: empty expected page means any page in document is valid.
        if exp_page == "":
            return True
        return exp_page == sel_page

    matched_positions = [
        idx + 1
        for idx, key in enumerate(selected_keys)
        if any(_is_match(expected_key, key) for expected_key in expected_list)
    ]
    matched_expected_indexes = set()
    for exp_idx, expected_key in enumerate(expected_list):
        if any(_is_match(expected_key, key) for key in selected_keys):
            matched_expected_indexes.add(exp_idx)

    metrics["matched_source_count"] = len(matched_expected_indexes)
    metrics["hit_at_k"] = bool(matched_positions)
    metrics["recall_at_k"] = (
        len(matched_expected_indexes) / len(expected_list) if expected_list else None
    )
    metrics["first_match_rank"] = min(matched_positions) if matched_positions else None
    metrics["mrr"] = (
        1.0 / float(metrics["first_match_rank"])
        if metrics["first_match_rank"] is not None
        else 0.0
    )
    return metrics


def _build_image_list_from_hits(selected_sources: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for source in selected_sources:
        raw_image_path = str(source.get("image_path", "") or "").strip()
        if not raw_image_path:
            continue

        filename = os.path.basename(raw_image_path)
        candidate_asset_path = ASSETS_PAGE_IMAGES_DIR / filename
        if candidate_asset_path.exists():
            out.append(str(candidate_asset_path))
        elif os.path.exists(raw_image_path):
            out.append(raw_image_path)
    return out


def _generate_answer(
    provider: str,
    image_list: List[str],
    question: str,
    strict_grounding: bool,
) -> str:
    if not image_list:
        return ""
    prompt = _build_prompt(strict_grounding=strict_grounding)
    return utils.query_multiple_images_by_provider(
        IMAGE_LIST=image_list,
        SYSTEM_PROMPT=prompt,
        USER_QUESTION=question,
        provider=provider,
    ).strip()


def _expected_term_recall(answer: str, expected_terms: List[str]) -> Optional[float]:
    if not expected_terms:
        return None
    answer_lc = str(answer or "").lower()
    normalized_terms = [str(term).strip().lower() for term in expected_terms if str(term).strip()]
    if not normalized_terms:
        return None
    matched = sum(1 for term in normalized_terms if term in answer_lc)
    return matched / len(normalized_terms)


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _save_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_eval(
    dataset_path: Path,
    output_dir: Path,
    per_collection_k: int,
    max_total_pages: int,
    max_distance: Optional[float],
    provider: Optional[str],
    run_answer_check: bool,
    strict_grounding: bool,
    fail_fast: bool = False,
) -> Dict[str, Any]:
    questions = _load_jsonl(dataset_path)
    if not questions:
        raise RuntimeError(f"Dataset is empty: {dataset_path}")

    resolved_provider = (provider or utils.get_app_llm_provider()).strip().lower()
    if resolved_provider not in {"bedrock", "openai"}:
        raise RuntimeError(f"Unsupported provider: {resolved_provider!r}")

    per_question_results: List[Dict[str, Any]] = []
    retrieval_latencies_ms: List[float] = []
    hit_values: List[float] = []
    recall_values: List[float] = []
    mrr_values: List[float] = []
    term_recall_values: List[float] = []
    abstain_count = 0
    retrieval_error_count = 0
    answer_error_count = 0

    for idx, row in enumerate(questions, start=1):
        question_id = str(row.get("id") or f"q{idx}")
        question = str(row.get("question") or "").strip()
        if not question:
            raise RuntimeError(f"Missing 'question' in dataset row {idx} ({question_id}).")

        expected_sources = _normalize_expected_sources(row)
        expected_terms = row.get("expected_terms", [])
        if not isinstance(expected_terms, list):
            expected_terms = []

        retrieval_error = None
        answer_error = None
        answer = None
        term_recall = None
        selected_sources: List[Dict[str, Any]] = []
        retrieval_metrics: Dict[str, Any] = {
            "expected_source_count": len(expected_sources),
            "matched_source_count": 0,
            "hit_at_k": None,
            "recall_at_k": None,
            "first_match_rank": None,
            "mrr": None,
        }
        latency_ms = 0.0

        try:
            hits, latency_ms = _extract_hits_for_eval(
                query=question,
                provider=resolved_provider,
                per_collection_k=per_collection_k,
                max_total_pages=max_total_pages,
                max_distance=max_distance,
            )
            retrieval_latencies_ms.append(latency_ms)
            selected_sources = [_hit_to_eval_source(hit) for hit in hits]
            retrieval_metrics = _compute_retrieval_metrics(selected_sources, expected_sources)
        except Exception as err:
            retrieval_error = str(err)
            retrieval_error_count += 1
            if fail_fast:
                raise

        if retrieval_metrics.get("hit_at_k") is not None:
            hit_values.append(1.0 if retrieval_metrics["hit_at_k"] else 0.0)
        if retrieval_metrics.get("recall_at_k") is not None:
            recall_values.append(float(retrieval_metrics["recall_at_k"]))
        if retrieval_metrics.get("mrr") is not None:
            mrr_values.append(float(retrieval_metrics["mrr"]))

        if run_answer_check:
            image_list = _build_image_list_from_hits(selected_sources)
            if image_list and retrieval_error is None:
                try:
                    answer = _generate_answer(
                        provider=resolved_provider,
                        image_list=image_list,
                        question=question,
                        strict_grounding=strict_grounding,
                    )
                    term_recall = _expected_term_recall(answer, expected_terms)
                    if term_recall is not None:
                        term_recall_values.append(term_recall)
                    if isinstance(answer, str) and "i don't have enough evidence" in answer.lower():
                        abstain_count += 1
                except Exception as err:
                    answer_error = str(err)
                    answer_error_count += 1
                    if fail_fast:
                        raise
            elif answer is None:
                answer = ""

        per_question_results.append(
            {
                "id": question_id,
                "question": question,
                "retrieval_latency_ms": round(latency_ms, 2),
                "retrieved_source_count": len(selected_sources),
                "selected_sources": selected_sources,
                "retrieval_metrics": retrieval_metrics,
                "answer": answer,
                "expected_term_recall": term_recall,
                "retrieval_error": retrieval_error,
                "answer_error": answer_error,
            }
        )

    summary = {
        "provider": resolved_provider,
        "dataset_path": str(dataset_path),
        "question_count": len(per_question_results),
        "config": {
            "per_collection_k": per_collection_k,
            "max_total_pages": max_total_pages,
            "max_distance": max_distance,
            "run_answer_check": run_answer_check,
            "strict_grounding": strict_grounding,
            "fail_fast": fail_fast,
        },
        "metrics": {
            "retrieval_latency_ms_mean": (
                round(statistics.mean(retrieval_latencies_ms), 2) if retrieval_latencies_ms else None
            ),
            "retrieval_latency_ms_p50": (
                round(_percentile(retrieval_latencies_ms, 0.50) or 0.0, 2)
                if retrieval_latencies_ms
                else None
            ),
            "retrieval_latency_ms_p95": (
                round(_percentile(retrieval_latencies_ms, 0.95) or 0.0, 2)
                if retrieval_latencies_ms
                else None
            ),
            "hit_at_k_rate": round(statistics.mean(hit_values), 4) if hit_values else None,
            "recall_at_k_mean": round(statistics.mean(recall_values), 4) if recall_values else None,
            "mrr_mean": round(statistics.mean(mrr_values), 4) if mrr_values else None,
            "expected_term_recall_mean": (
                round(statistics.mean(term_recall_values), 4) if term_recall_values else None
            ),
            "abstention_rate": (
                round(abstain_count / len(per_question_results), 4)
                if run_answer_check and per_question_results
                else None
            ),
            "retrieval_error_count": retrieval_error_count,
            "retrieval_error_rate": round(retrieval_error_count / len(per_question_results), 4),
            "answer_error_count": answer_error_count if run_answer_check else None,
            "answer_error_rate": (
                round(answer_error_count / len(per_question_results), 4)
                if run_answer_check and per_question_results
                else None
            ),
        },
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"rag_eval_summary_{stamp}.json"
    details_path = output_dir / f"rag_eval_details_{stamp}.jsonl"
    _save_json(summary_path, summary)
    _save_jsonl(details_path, per_question_results)

    return {
        "summary": summary,
        "summary_path": str(summary_path),
        "details_path": str(details_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline RAG evaluation for NIFTY.")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(DEFAULT_DATASET_PATH),
        help="Path to JSONL dataset file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for summary/detail result files.",
    )
    parser.add_argument(
        "--per-collection-k",
        type=int,
        default=int(os.getenv("DOCSEARCH_RESULTS_PER_COLLECTION", "2")),
        help="Top-k retrieved per collection before global ranking.",
    )
    parser.add_argument(
        "--max-total-pages",
        type=int,
        default=int(os.getenv("DOCSEARCH_MAX_TOTAL_PAGES", "4")),
        help="Global max hits used for answer context.",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=None,
        help="Optional max retrieval distance threshold.",
    )
    parser.add_argument(
        "--provider",
        choices=["bedrock", "openai"],
        default=None,
        help="Force provider (otherwise APP_LLM_PROVIDER is used).",
    )
    parser.add_argument(
        "--run-answer-check",
        action="store_true",
        help="Also run multimodal answer generation on retrieved pages.",
    )
    parser.add_argument(
        "--strict-grounding",
        action="store_true",
        default=False,
        help="Use strict grounding abstention prompt when --run-answer-check is enabled.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=False,
        help="Stop immediately on first retrieval or answer-generation error.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}\n"
            "Create it from control_docs/rag_eval_questions.sample.jsonl first."
        )

    result = run_eval(
        dataset_path=dataset_path,
        output_dir=output_dir,
        per_collection_k=max(1, int(args.per_collection_k)),
        max_total_pages=max(1, int(args.max_total_pages)),
        max_distance=args.max_distance,
        provider=args.provider,
        run_answer_check=bool(args.run_answer_check),
        strict_grounding=bool(args.strict_grounding),
        fail_fast=bool(args.fail_fast),
    )

    print("RAG evaluation complete.")
    print(f"Summary: {result['summary_path']}")
    print(f"Details: {result['details_path']}")
    print(json.dumps(result["summary"]["metrics"], indent=2))


if __name__ == "__main__":
    main()
