import json
import math
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


QUESTION_ID_PATTERN = re.compile(r"\b([A-Z][A-Z0-9_]*_Q)\b")
GOTO_PATTERN = re.compile(r"go to\s+([A-Z][A-Z0-9_]*_Q)\b", flags=re.IGNORECASE)
REF_LIST_PATTERN = re.compile(r"reference list:\s*(?:PRL:\s*)?([A-Z_]+)", flags=re.IGNORECASE)
ASSIGNMENT_PATTERN = re.compile(
    r'"([^"]+)"\s*\((\d+)\)\s*is\s*<\s*\'([^\']*)\'\s*>',
    flags=re.IGNORECASE,
)
CAPTURE_PATTERN = re.compile(r'Capture\s+"([^"]+)"\s*\((\d+)\)', flags=re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    text = _safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(value: Any) -> List[str]:
    return TOKEN_PATTERN.findall(_normalize_text(value))


def _placeholder(value: Any) -> bool:
    text = _normalize_text(value)
    return text in {
        "",
        "not yet determined",
        "n a",
        "na",
        "none",
        "null",
        "nan",
    }


def _extract_reference_list_names(instructions: str) -> List[str]:
    refs = []
    for match in REF_LIST_PATTERN.finditer(instructions or ""):
        ref_name = _safe_text(match.group(1)).upper()
        if ref_name and ref_name not in refs:
            refs.append(ref_name)
    return refs


def _extract_goto_target(line: str) -> Optional[str]:
    match = GOTO_PATTERN.search(line or "")
    if match:
        return _safe_text(match.group(1)).upper()
    return None


def _extract_condition_tokens(line: str) -> Tuple[List[str], List[str]]:
    line_text = _safe_text(line)
    if not re.match(r"(?i)^\s*(?:else\s+)?if\b", line_text):
        return [], []

    prefix = line_text
    selected_match = re.search(r"\bselected\b", line_text, flags=re.IGNORECASE)
    if selected_match:
        prefix = line_text[: selected_match.start()]
    else:
        then_match = re.search(r"\bthen\b", line_text, flags=re.IGNORECASE)
        if then_match:
            prefix = line_text[: then_match.start()]

    raw_tokens = [t.strip() for t in re.findall(r"'([^']+)'", prefix) if _safe_text(t)]
    normalized = [_normalize_text(t) for t in raw_tokens if _normalize_text(t)]
    return raw_tokens, normalized


def _extract_assignments(line: str) -> List[Tuple[int, str, str]]:
    assignments = []
    for field_name, field_number, value in ASSIGNMENT_PATTERN.findall(line or ""):
        try:
            field_num = int(field_number)
        except Exception:
            continue
        assignments.append((field_num, _safe_text(value), _safe_text(field_name)))
    return assignments


def _extract_captures(line: str) -> List[Tuple[int, str]]:
    captures = []
    for field_name, field_number in CAPTURE_PATTERN.findall(line or ""):
        try:
            field_num = int(field_number)
        except Exception:
            continue
        captures.append((field_num, _safe_text(field_name)))
    return captures


def _extract_instruction_choice_values(line: str) -> List[str]:
    """
    Extract literal option values from instruction lines like:
    either <'ESTIMATED'> or <'FINALIZED'>
    """
    line_text = _safe_text(line)
    if not line_text:
        return []

    # Only treat literals in the conditional prefix as user-selectable choices.
    # Values in assignment clauses (after THEN) are usually target field values,
    # e.g. Form Type = CASE, and should not become displayed options.
    prefix = line_text
    selected_match = re.search(r"\bselected\b", line_text, flags=re.IGNORECASE)
    if selected_match:
        prefix = line_text[: selected_match.start()]
    else:
        then_match = re.search(r"\bthen\b", line_text, flags=re.IGNORECASE)
        if then_match:
            prefix = line_text[: then_match.start()]

    literals = [_safe_text(x) for x in re.findall(r"<\s*'([^']+)'\s*>", prefix)]
    literals = [x for x in literals if x]
    if len(literals) < 2:
        return []

    line_norm = _normalize_text(prefix)
    # Treat as explicit choices only when wording indicates alternatives.
    if "either" not in line_norm and " or " not in f" {line_norm} ":
        return []

    deduped = []
    seen = set()
    for value in literals:
        key = _normalize_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _fuzzy_score(query: str, target: str) -> float:
    if not query or not target:
        return 0.0
    return SequenceMatcher(None, query[:280], target[:280]).ratio()


def _match_token(answer_norm: str, candidate_norm: str) -> bool:
    if not answer_norm or not candidate_norm:
        return False
    if answer_norm == candidate_norm:
        return True
    if answer_norm in candidate_norm or candidate_norm in answer_norm:
        return True
    answer_tokens = set(TOKEN_PATTERN.findall(answer_norm))
    candidate_tokens = set(TOKEN_PATTERN.findall(candidate_norm))
    if not answer_tokens or not candidate_tokens:
        return False
    inter = answer_tokens.intersection(candidate_tokens)
    if not inter:
        return False
    union = answer_tokens.union(candidate_tokens)
    return len(inter) / max(1, len(union)) >= 0.5


@dataclass
class InstructionLine:
    raw: str
    goto: Optional[str]
    condition_raw_tokens: List[str]
    condition_norm_tokens: List[str]
    assignments: List[Tuple[int, str, str]]
    captures: List[Tuple[int, str]]
    dropdown_refs: List[str]


@dataclass
class RuleCard:
    question_id: str
    question: str
    instructions: str
    order: int
    dropdown_refs: List[str]
    options: List[str]
    option_aliases: Dict[str, List[str]]
    lines: List[InstructionLine]
    next_in_order: Optional[str]


@dataclass
class RetrievalChunk:
    chunk_id: str
    kind: str
    source: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)


@dataclass
class KnowledgePack:
    rules: List[RuleCard]
    rule_by_id: Dict[str, RuleCard]
    rule_order: List[str]
    glossary_terms: Dict[str, str]
    dropdown_catalog: Dict[str, List[str]]
    chunks: List[RetrievalChunk]
    idf: Dict[str, float]
    artifacts_dir: str
    retrieval_cache: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    @property
    def first_question_id(self) -> Optional[str]:
        return self.rule_order[0] if self.rule_order else None


def _build_rule_card(
    row: pd.Series,
    order: int,
    next_in_order: Optional[str],
    dropdown_catalog: Dict[str, List[str]],
) -> RuleCard:
    question_id = _safe_text(row.get("Question ID", "")).upper()
    question = _safe_text(row.get("Question", ""))
    instructions = _safe_text(row.get("Instructions", ""))
    instruction_lines_raw = [ln.strip() for ln in instructions.splitlines() if _safe_text(ln)]

    lines: List[InstructionLine] = []
    dropdown_refs_agg: List[str] = []
    option_aliases: Dict[str, List[str]] = {}
    condition_display_options: List[str] = []

    for line in instruction_lines_raw:
        line_refs = _extract_reference_list_names(line)
        for ref_name in line_refs:
            if ref_name not in dropdown_refs_agg:
                dropdown_refs_agg.append(ref_name)

        cond_raw, cond_norm = _extract_condition_tokens(line)
        goto = _extract_goto_target(line)
        line_obj = InstructionLine(
            raw=line,
            goto=goto,
            condition_raw_tokens=cond_raw,
            condition_norm_tokens=cond_norm,
            assignments=_extract_assignments(line),
            captures=_extract_captures(line),
            dropdown_refs=line_refs,
        )
        lines.append(line_obj)

        if cond_raw:
            display = _safe_text(cond_raw[0])
            if display:
                if display not in condition_display_options:
                    condition_display_options.append(display)
                existing = option_aliases.get(display, [])
                merged = existing + cond_raw
                deduped = []
                seen = set()
                for item in merged:
                    key = _normalize_text(item)
                    if key and key not in seen:
                        seen.add(key)
                        deduped.append(_safe_text(item))
                option_aliases[display] = deduped

        # Handle literal choices encoded in instruction text
        # e.g. either <'ESTIMATED'> or <'FINALIZED'>
        line_choices = _extract_instruction_choice_values(line)
        for choice in line_choices:
            existing = option_aliases.get(choice, [])
            merged = existing + [choice]
            deduped = []
            seen = set()
            for item in merged:
                key = _normalize_text(item)
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(_safe_text(item))
            option_aliases[choice] = deduped

    options: List[str] = []
    if dropdown_refs_agg:
        for ref_name in dropdown_refs_agg:
            values = dropdown_catalog.get(ref_name, [])
            for value in values:
                value_text = _safe_text(value)
                if value_text and value_text not in options:
                    options.append(value_text)
                    option_aliases[value_text] = [value_text]
    else:
        inline_options = list(condition_display_options) if condition_display_options else _extract_inline_question_options(question)
        if inline_options:
            # Prefer concise display options from the question text and map
            # aliases from condition tokens for robust matching.
            alias_snapshot = dict(option_aliases)
            for parsed_opt in inline_options:
                disp = _safe_text(parsed_opt)
                if not disp:
                    continue
                disp_norm = _normalize_text(disp)
                aliases = [disp]

                for alias_key, alias_vals in alias_snapshot.items():
                    alias_norm = _normalize_text(alias_key)
                    if not alias_norm:
                        continue
                    if (
                        alias_norm == disp_norm
                        or alias_norm in disp_norm
                        or disp_norm in alias_norm
                    ):
                        aliases.append(alias_key)
                        aliases.extend([_safe_text(v) for v in alias_vals if _safe_text(v)])

                deduped = []
                seen = set()
                for item in aliases:
                    key = _normalize_text(item)
                    if key and key not in seen:
                        seen.add(key)
                        deduped.append(_safe_text(item))
                option_aliases[disp] = deduped
                if disp not in options:
                    options.append(disp)
        else:
            for display in option_aliases:
                if display not in options:
                    options.append(display)

    return RuleCard(
        question_id=question_id,
        question=question,
        instructions=instructions,
        order=order,
        dropdown_refs=dropdown_refs_agg,
        options=options,
        option_aliases=option_aliases,
        lines=lines,
        next_in_order=next_in_order,
    )


def _build_chunks(
    rules: List[RuleCard],
    glossary_terms: Dict[str, str],
    dropdown_catalog: Dict[str, List[str]],
) -> List[RetrievalChunk]:
    chunks: List[RetrievalChunk] = []
    for rule in rules:
        text = f"{rule.question_id}\n{rule.question}\n{rule.instructions}".strip()
        chunk = RetrievalChunk(
            chunk_id=f"rule::{rule.question_id}",
            kind="rule",
            source=f"Expert_System_Rules.xlsx::{rule.question_id}",
            text=text,
            metadata={"question_id": rule.question_id},
            tokens=_tokenize(text),
        )
        chunks.append(chunk)

    for term, definition in glossary_terms.items():
        text = f"{_safe_text(term)}: {_safe_text(definition)}"
        chunk = RetrievalChunk(
            chunk_id=f"glossary::{_normalize_text(term)}",
            kind="glossary",
            source="NIFTY Definitions v1.xlsx::glossary",
            text=text,
            metadata={"term": _safe_text(term)},
            tokens=_tokenize(text),
        )
        chunks.append(chunk)

    for ref_name, values in dropdown_catalog.items():
        head_values = values[:120]
        text = f"{ref_name}: " + ", ".join([_safe_text(v) for v in head_values if _safe_text(v)])
        chunk = RetrievalChunk(
            chunk_id=f"dropdown::{ref_name}",
            kind="dropdown",
            source=f"dropdown_references::{ref_name}",
            text=text,
            metadata={"reference_name": ref_name},
            tokens=_tokenize(text),
        )
        chunks.append(chunk)

    return chunks


def _compute_idf(chunks: List[RetrievalChunk]) -> Dict[str, float]:
    doc_count = max(1, len(chunks))
    doc_freq: Dict[str, int] = {}
    for chunk in chunks:
        for token in set(chunk.tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1
    idf = {}
    for token, freq in doc_freq.items():
        idf[token] = 1.0 + math.log((1.0 + doc_count) / (1.0 + freq))
    return idf


def _write_artifacts(
    rules: List[RuleCard],
    glossary_terms: Dict[str, str],
    dropdown_catalog: Dict[str, List[str]],
    artifacts_dir: str,
) -> None:
    out_dir = Path(artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph_nodes = []
    graph_edges = []
    for rule in rules:
        graph_nodes.append(
            {
                "question_id": rule.question_id,
                "order": rule.order,
                "question": rule.question,
                "dropdown_refs": rule.dropdown_refs,
            }
        )
        for line in rule.lines:
            if line.goto:
                graph_edges.append(
                    {
                        "from": rule.question_id,
                        "to": line.goto,
                        "conditions": line.condition_raw_tokens,
                        "raw": line.raw,
                    }
                )
        if rule.next_in_order:
            graph_edges.append(
                {
                    "from": rule.question_id,
                    "to": rule.next_in_order,
                    "conditions": ["<implicit_next_row>"],
                    "raw": "Implicit next row fallback",
                }
            )

    with (out_dir / "question_graph.json").open("w", encoding="utf-8") as f:
        json.dump({"nodes": graph_nodes, "edges": graph_edges}, f, indent=2)

    with (out_dir / "question_cards.jsonl").open("w", encoding="utf-8") as f:
        for rule in rules:
            row = {
                "question_id": rule.question_id,
                "order": rule.order,
                "question": rule.question,
                "instructions": rule.instructions,
                "dropdown_refs": rule.dropdown_refs,
                "options": rule.options,
                "next_in_order": rule.next_in_order,
                "lines": [
                    {
                        "raw": line.raw,
                        "goto": line.goto,
                        "condition_tokens": line.condition_raw_tokens,
                        "assignments": line.assignments,
                        "captures": line.captures,
                    }
                    for line in rule.lines
                ],
            }
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    with (out_dir / "glossary_terms.jsonl").open("w", encoding="utf-8") as f:
        for term, definition in glossary_terms.items():
            f.write(
                json.dumps(
                    {"term": _safe_text(term), "definition": _safe_text(definition)},
                    ensure_ascii=True,
                )
                + "\n"
            )

    with (out_dir / "dropdown_catalog.json").open("w", encoding="utf-8") as f:
        json.dump(dropdown_catalog, f, indent=2)


def build_knowledge_pack(
    rules_df: pd.DataFrame,
    glossary_terms: Dict[str, str],
    dropdown_catalog: Dict[str, List[str]],
    artifacts_dir: str,
) -> KnowledgePack:
    if rules_df is None or rules_df.empty:
        raise ValueError("rules_df cannot be empty.")

    rules_df_local = rules_df.copy()
    rules_df_local = rules_df_local.dropna(subset=["Question ID"])
    rules_df_local = rules_df_local.reset_index(drop=True)

    qids = [_safe_text(x).upper() for x in rules_df_local["Question ID"].tolist()]
    rules: List[RuleCard] = []
    for idx, row in rules_df_local.iterrows():
        qid = _safe_text(row.get("Question ID", "")).upper()
        if not qid:
            continue
        next_qid = qids[idx + 1] if idx + 1 < len(qids) else None
        rules.append(
            _build_rule_card(
                row=row,
                order=idx,
                next_in_order=next_qid,
                dropdown_catalog=dropdown_catalog,
            )
        )

    rule_by_id = {rule.question_id: rule for rule in rules}
    rule_order = [rule.question_id for rule in rules]

    glossary_clean = {
        _safe_text(k): _safe_text(v)
        for k, v in (glossary_terms or {}).items()
        if _safe_text(k) and _safe_text(v)
    }
    dropdown_clean = {}
    for ref_name, values in (dropdown_catalog or {}).items():
        name = _safe_text(ref_name).upper()
        if not name:
            continue
        deduped = []
        seen = set()
        for value in values or []:
            value_text = _safe_text(value)
            key = _normalize_text(value_text)
            if not value_text or not key or key in seen:
                continue
            seen.add(key)
            deduped.append(value_text)
        dropdown_clean[name] = deduped

    chunks = _build_chunks(rules, glossary_clean, dropdown_clean)
    idf = _compute_idf(chunks)

    _write_artifacts(rules, glossary_clean, dropdown_clean, artifacts_dir=artifacts_dir)

    return KnowledgePack(
        rules=rules,
        rule_by_id=rule_by_id,
        rule_order=rule_order,
        glossary_terms=glossary_clean,
        dropdown_catalog=dropdown_clean,
        chunks=chunks,
        idf=idf,
        artifacts_dir=str(artifacts_dir),
    )


def hybrid_retrieve(
    pack: KnowledgePack,
    query: str,
    kinds: Optional[List[str]] = None,
    top_k: int = 5,
    current_question_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query_text = _safe_text(query)
    query_norm = _normalize_text(query_text)
    query_tokens = _tokenize(query_text)
    if not query_norm:
        return []

    kinds_set = {k.lower() for k in kinds} if kinds else None
    cache_key = (
        f"{query_norm}|"
        f"{','.join(sorted(kinds_set)) if kinds_set else '*'}|"
        f"{int(top_k)}|"
        f"{_safe_text(current_question_id).upper()}"
    )
    if cache_key in pack.retrieval_cache:
        return pack.retrieval_cache[cache_key][: max(1, top_k)]

    scored = []
    for chunk in pack.chunks:
        if kinds_set and chunk.kind.lower() not in kinds_set:
            continue
        overlap = set(query_tokens).intersection(set(chunk.tokens))
        lexical = 0.0
        if query_tokens:
            lexical = sum(pack.idf.get(tok, 0.0) for tok in overlap) / max(1, len(query_tokens))
        fuzzy = _fuzzy_score(query_norm, _normalize_text(chunk.text))
        score = (0.78 * lexical) + (0.22 * fuzzy)
        if current_question_id and chunk.metadata.get("question_id") == current_question_id:
            score += 0.15
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, chunk in scored[: max(1, top_k)]:
        results.append(
            {
                "score": round(score, 6),
                "kind": chunk.kind,
                "source": chunk.source,
                "text": chunk.text,
                "metadata": chunk.metadata,
            }
        )
    pack.retrieval_cache[cache_key] = results
    return results


def infer_next_question_id(
    pack: KnowledgePack,
    last_question_id: str,
    last_answer: str,
) -> Optional[str]:
    if not pack.rule_order:
        return None

    qid = _safe_text(last_question_id).upper()
    answer_norm = _normalize_text(last_answer)
    if not qid or qid not in pack.rule_by_id:
        return pack.first_question_id

    card = pack.rule_by_id[qid]

    default_target = None
    for line in card.lines:
        if line.goto and not line.condition_norm_tokens and default_target is None:
            default_target = line.goto
        if line.goto and line.condition_norm_tokens:
            for token in line.condition_norm_tokens:
                if _match_token(answer_norm, token):
                    return line.goto

    if default_target:
        return default_target
    return card.next_in_order


def _resolve_answer(card: RuleCard, user_input: str) -> Tuple[str, bool]:
    answer_text = _safe_text(user_input)
    answer_norm = _normalize_text(answer_text)
    if not answer_text:
        return "", False

    if card.options:
        if answer_text.isdigit():
            idx = int(answer_text) - 1
            if 0 <= idx < len(card.options):
                return card.options[idx], True

        best_option = None
        best_score = 0.0
        for option in card.options:
            aliases = card.option_aliases.get(option, [option])
            for alias in aliases:
                alias_norm = _normalize_text(alias)
                if not alias_norm:
                    continue
                if _match_token(answer_norm, alias_norm):
                    return option, True
                score = _fuzzy_score(answer_norm, alias_norm)
                if score > best_score:
                    best_score = score
                    best_option = option

        if best_option and best_score >= 0.78:
            return best_option, True
        return answer_text, False

    return answer_text, True


def _select_lines_for_answer(card: RuleCard, resolved_answer: str) -> List[InstructionLine]:
    answer_norm = _normalize_text(resolved_answer)
    if not answer_norm:
        return card.lines

    matched = []
    for line in card.lines:
        if not line.condition_norm_tokens:
            continue
        if any(_match_token(answer_norm, token) for token in line.condition_norm_tokens):
            matched.append(line)

    if matched:
        return matched

    unconditional = [line for line in card.lines if not line.condition_norm_tokens]
    return unconditional if unconditional else card.lines


def _collect_updates(
    selected_lines: List[InstructionLine],
    answer_value: str,
) -> Tuple[List[Tuple[int, str]], str]:
    updates: List[Tuple[int, str]] = []
    seen = set()

    # Static assignments first.
    for line in selected_lines:
        for field_num, value, _field_name in line.assignments:
            if field_num in seen:
                continue
            updates.append((field_num, _safe_text(value)))
            seen.add(field_num)

    # Capture fields next.
    for line in selected_lines:
        for field_num, _field_name in line.captures:
            if field_num in seen:
                continue
            updates.append((field_num, _safe_text(answer_value)))
            seen.add(field_num)

    tracking_value = _safe_text(answer_value)
    if not tracking_value and updates:
        tracking_value = updates[-1][1]
    return updates, tracking_value


def _choose_next_question(
    card: RuleCard,
    selected_lines: List[InstructionLine],
    resolved_answer: str,
) -> Optional[str]:
    answer_norm = _normalize_text(resolved_answer)
    for line in selected_lines:
        if line.goto:
            if not line.condition_norm_tokens:
                return line.goto
            if any(_match_token(answer_norm, token) for token in line.condition_norm_tokens):
                return line.goto

    for line in card.lines:
        if line.goto and not line.condition_norm_tokens:
            return line.goto
    for line in card.lines:
        if line.goto:
            return line.goto
    return card.next_in_order


def _extract_inline_question_options(question_text: str) -> List[str]:
    """
    Parse inline comma/or choice lists from question sentence.
    Example:
    "... sold in United States, Canada, Latin America, ... , or UNSURE?"
    """
    text = _safe_text(question_text)
    if not text:
        return []

    normalized = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )

    match = re.search(r"\b(?:in|for)\s+(.+?)\?\s*$", normalized, flags=re.IGNORECASE)
    if not match:
        return []

    segment = match.group(1).strip()
    if not segment:
        return []

    # Normalize connector wording into comma separators.
    segment = re.sub(r"\s+or\s+", ", ", segment, flags=re.IGNORECASE)
    segment = re.sub(r"\s+and\s+", ", ", segment, flags=re.IGNORECASE)

    options = []
    seen = set()
    for raw_part in segment.split(","):
        part = re.sub(r"\s+", " ", raw_part).strip(" '\"()")
        if not part:
            continue
        if len(part) > 48:
            # Likely not a simple option value.
            continue
        key = _normalize_text(part)
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(part)

    if len(options) < 2 or len(options) > 15:
        return []
    return options


def _compact_question_text(question_text: str, options: List[str]) -> str:
    """
    Remove inline comma-separated options from question text when options are
    rendered as numbered list below.
    """
    text = _safe_text(question_text) or "Please provide the required value."
    if not options:
        return text

    text_lc = text.lower()
    first_idx = None
    for option in options:
        idx = text_lc.find(_safe_text(option).lower())
        if idx == -1:
            continue
        if first_idx is None or idx < first_idx:
            first_idx = idx

    if first_idx is None:
        return text

    prefix = text[:first_idx].rstrip(" ,;:-")
    if len(prefix) < 12:
        return text
    if not prefix.endswith("?"):
        prefix = prefix.rstrip(" ?") + "?"
    return prefix


def _render_question(card: RuleCard) -> str:
    question_text = _safe_text(card.question) or "Please provide the required value."
    options = list(card.options or [])
    if not options:
        options = _extract_inline_question_options(question_text)
    question_display = _compact_question_text(question_text, options)

    lines = [f"Question {card.question_id}: {question_display}"]
    if options:
        lines.append("")
        for idx, option in enumerate(options, start=1):
            lines.append(f"{idx}. {option}")
        lines.append("")
        lines.append("Reply with the option number or option text.")
    return "\n".join(lines)


def _is_start_command(text_norm: str) -> bool:
    return any(
        phrase in text_norm
        for phrase in [
            "start a new nif",
            "new nif chat",
            "start new nif",
        ]
    )


def _is_resume_command(text_norm: str) -> bool:
    return any(
        phrase in text_norm
        for phrase in [
            "nif rag resume",
            "resume the user s nif",
            "resume nif",
            "loaded successfully",
            "resume nif from prior chat",
            "last answered question id",
        ]
    )


def _is_clarification_request(text_norm: str) -> bool:
    return any(
        phrase in text_norm
        for phrase in [
            "what is",
            "define",
            "meaning",
            "clarify",
            "explain",
            "help with",
            "show options",
        ]
    )


def _is_back_command(text_norm: str) -> bool:
    return any(
        phrase in text_norm
        for phrase in [
            "go back",
            "previous question",
            "back one question",
        ]
    )


def _find_previous_question(pack: KnowledgePack, question_id: str) -> Optional[str]:
    if question_id not in pack.rule_order:
        return pack.first_question_id
    idx = pack.rule_order.index(question_id)
    if idx <= 0:
        return pack.rule_order[0]
    return pack.rule_order[idx - 1]


def _apply_progress(
    progress_df: pd.DataFrame,
    question_id: str,
    tracking_value: str,
    updates: List[Tuple[int, str]],
    field_number_to_column: Dict[int, str],
) -> pd.DataFrame:
    updated_df = progress_df.copy()
    updated_df["_agentref_last_question_answered"] = _safe_text(question_id)
    updated_df["_agentref_last_answer_given"] = _safe_text(tracking_value)

    for field_number, field_value in updates:
        column_name = field_number_to_column.get(int(field_number))
        if not column_name:
            continue
        if column_name not in updated_df.columns:
            continue
        updated_df[column_name] = _safe_text(field_value)
    return updated_df


def _auto_advance_rules(
    pack: KnowledgePack,
    progress_df: pd.DataFrame,
    start_question_id: Optional[str],
    field_number_to_column: Dict[int, str],
    max_steps: int,
) -> Tuple[pd.DataFrame, Optional[str], List[Dict[str, Any]]]:
    events: List[Dict[str, Any]] = []
    updated_df = progress_df.copy()
    qid = start_question_id
    steps = 0

    while qid and steps < max_steps:
        card = pack.rule_by_id.get(qid)
        if card is None:
            break

        # Stop when we hit a user-facing question.
        if _safe_text(card.question):
            break

        selected_lines = [line for line in card.lines if not line.condition_norm_tokens]
        if not selected_lines:
            selected_lines = card.lines

        updates, tracking_value = _collect_updates(selected_lines, answer_value="")
        if not tracking_value:
            tracking_value = "<AUTO>"

        updated_df = _apply_progress(
            progress_df=updated_df,
            question_id=card.question_id,
            tracking_value=tracking_value,
            updates=updates,
            field_number_to_column=field_number_to_column,
        )
        events.append(
            {
                "question_id": card.question_id,
                "tracking_value": tracking_value,
                "field_updates": updates,
                "auto": True,
            }
        )
        qid = _choose_next_question(card, selected_lines, resolved_answer=tracking_value)
        steps += 1

    return updated_df, qid, events


def run_turn(
    pack: KnowledgePack,
    user_input: str,
    progress_df: pd.DataFrame,
    field_number_to_column: Dict[int, str],
    session_state: Optional[Dict[str, Any]] = None,
    max_auto_steps: int = 10,
    retrieval_top_k: int = 4,
) -> Dict[str, Any]:
    if progress_df is None or progress_df.empty:
        raise ValueError("progress_df cannot be empty.")
    if not pack.rule_order:
        raise RuntimeError("Knowledge pack has no rules.")

    state = dict(session_state or {})
    current_qid = _safe_text(state.get("current_question_id", "")).upper()
    input_text = _safe_text(user_input)
    input_norm = _normalize_text(input_text)

    # Allow direct jump by question ID mention.
    qid_match = QUESTION_ID_PATTERN.search(input_text.upper())
    if qid_match:
        jump_qid = _safe_text(qid_match.group(1)).upper()
        if jump_qid in pack.rule_by_id:
            current_qid = jump_qid

    # Bootstrap or resume when no active question is pinned.
    if not current_qid or current_qid not in pack.rule_by_id:
        try:
            last_qid = _safe_text(progress_df["_agentref_last_question_answered"].iloc[0]).upper()
        except Exception:
            last_qid = ""
        try:
            last_answer = _safe_text(progress_df["_agentref_last_answer_given"].iloc[0])
        except Exception:
            last_answer = ""
        current_qid = infer_next_question_id(pack, last_qid, last_answer) or pack.first_question_id

    # Start/resume commands reset to inferred starting point.
    if _is_start_command(input_norm):
        current_qid = pack.first_question_id
    elif _is_resume_command(input_norm):
        try:
            last_qid = _safe_text(progress_df["_agentref_last_question_answered"].iloc[0]).upper()
            last_answer = _safe_text(progress_df["_agentref_last_answer_given"].iloc[0])
        except Exception:
            last_qid, last_answer = "", ""
        current_qid = infer_next_question_id(pack, last_qid, last_answer) or current_qid

    updated_df = progress_df.copy()
    events: List[Dict[str, Any]] = []

    # Auto-run no-question nodes until a real question is reached.
    updated_df, current_qid, auto_events = _auto_advance_rules(
        pack=pack,
        progress_df=updated_df,
        start_question_id=current_qid,
        field_number_to_column=field_number_to_column,
        max_steps=max_auto_steps,
    )
    events.extend(auto_events)

    if not current_qid:
        response = "Requestor - Project Initiation section is complete."
        state["current_question_id"] = ""
        return {
            "response_text": response,
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": [],
            "current_question_id": "",
            "current_options": [],
            "answer_matched": True,
            "needs_clarification": False,
        }

    current_card = pack.rule_by_id[current_qid]

    # For start/resume bootstrap turns, ask current question without consuming answer.
    if _is_start_command(input_norm) or _is_resume_command(input_norm):
        state["current_question_id"] = current_qid
        return {
            "response_text": _render_question(current_card),
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": [],
            "current_question_id": current_qid,
            "current_options": list(current_card.options or []),
            "answer_matched": True,
            "needs_clarification": False,
        }

    # Clarification request keeps current question pinned and adds RAG context.
    if _is_clarification_request(input_norm):
        hits = hybrid_retrieve(
            pack=pack,
            query=input_text,
            kinds=["glossary", "rule", "dropdown"],
            top_k=retrieval_top_k,
            current_question_id=current_qid,
        )
        guidance_lines = []
        for hit in hits[:3]:
            hit_text = _safe_text(hit.get("text", ""))
            if not hit_text:
                continue
            if hit.get("kind") == "glossary":
                guidance_lines.append(f"- {hit_text}")
            elif hit.get("kind") == "dropdown":
                guidance_lines.append(f"- Relevant list: {hit_text}")
            else:
                guidance_lines.append(f"- Relevant rule context: {hit_text[:200]}")
        if guidance_lines:
            prefix = "Helpful context:\n" + "\n".join(guidance_lines) + "\n\n"
        else:
            prefix = "I could not find matching glossary context for that request.\n\n"
        state["current_question_id"] = current_qid
        return {
            "response_text": prefix + _render_question(current_card),
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": hits,
            "current_question_id": current_qid,
            "current_options": list(current_card.options or []),
            "answer_matched": True,
            "needs_clarification": False,
        }

    if _is_back_command(input_norm):
        prev_qid = _find_previous_question(pack, current_qid) or current_qid
        state["current_question_id"] = prev_qid
        prev_card = pack.rule_by_id.get(prev_qid, current_card)
        response = "Moved back one question.\n\n" + _render_question(prev_card)
        return {
            "response_text": response,
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": [],
            "current_question_id": prev_qid,
            "current_options": list(prev_card.options or []),
            "answer_matched": True,
            "needs_clarification": False,
        }

    resolved_answer, matched = _resolve_answer(current_card, input_text)
    if current_card.options and not matched:
        response = (
            "I could not match your response to the available options.\n\n"
            + _render_question(current_card)
        )
        state["current_question_id"] = current_qid
        return {
            "response_text": response,
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": [],
            "current_question_id": current_qid,
            "current_options": list(current_card.options or []),
            "answer_matched": False,
            "needs_clarification": True,
        }

    selected_lines = _select_lines_for_answer(current_card, resolved_answer=resolved_answer)
    field_updates, tracking_value = _collect_updates(selected_lines, answer_value=resolved_answer)
    if not tracking_value:
        tracking_value = resolved_answer

    updated_df = _apply_progress(
        progress_df=updated_df,
        question_id=current_card.question_id,
        tracking_value=tracking_value,
        updates=field_updates,
        field_number_to_column=field_number_to_column,
    )
    events.append(
        {
            "question_id": current_card.question_id,
            "tracking_value": tracking_value,
            "field_updates": field_updates,
            "auto": False,
        }
    )

    next_qid = _choose_next_question(
        current_card,
        selected_lines=selected_lines,
        resolved_answer=resolved_answer,
    )

    updated_df, next_qid, auto_events_2 = _auto_advance_rules(
        pack=pack,
        progress_df=updated_df,
        start_question_id=next_qid,
        field_number_to_column=field_number_to_column,
        max_steps=max_auto_steps,
    )
    events.extend(auto_events_2)

    if not next_qid:
        state["current_question_id"] = ""
        response = (
            "I recorded your response.\n\n"
            "Requestor - Project Initiation section is complete."
        )
        return {
            "response_text": response,
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": [],
            "current_question_id": "",
            "current_options": [],
            "answer_matched": True,
            "needs_clarification": False,
        }

    next_card = pack.rule_by_id.get(next_qid)
    state["current_question_id"] = next_qid

    if next_card is None:
        response = "I recorded your response, but could not find the next question in rules."
        return {
            "response_text": response,
            "updated_progress_df": updated_df,
            "session_state": state,
            "events": events,
            "retrieval_hits": [],
            "current_question_id": next_qid,
            "current_options": [],
            "answer_matched": True,
            "needs_clarification": False,
        }

    response = (
        "I recorded your response.\n\n"
        + _render_question(next_card)
    )
    return {
        "response_text": response,
        "updated_progress_df": updated_df,
        "session_state": state,
        "events": events,
        "retrieval_hits": [],
        "current_question_id": next_qid,
        "current_options": list(next_card.options or []),
        "answer_matched": True,
        "needs_clarification": False,
    }
