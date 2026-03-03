# knva-nifty
Project NIFTY: a web application to assist Kellanova employees with the New Item Form.

NIFTY has a chatbot interface and uses LLM agents to perform tasks such as searching documentation, querying databases, and checking process rules as needed to answer user questions.

## New NIF RAG v2 engine

A high-performance rule+RAG engine is available for **New NIF chat session** and is linked to the existing UI button.

- Keep existing behavior (default):
  - `NIF_CHAT_ENGINE=legacy`
- Enable new RAG engine:
  - `NIF_CHAT_ENGINE=rag_v2`

When enabled, the New NIF button uses a compiled knowledge pack built from:
- `control_docs/Expert_System_Rules.xlsx` (sheet `Implementation v1`)
- `control_docs/NIFTY Definitions v1.xlsx` (sheet `glossary`)
- `control_docs/dropdown_references/`

Compiled artifacts are written to:
- `control_docs/compiled_nif_rag/question_graph.json`
- `control_docs/compiled_nif_rag/question_cards.jsonl`
- `control_docs/compiled_nif_rag/glossary_terms.jsonl`
- `control_docs/compiled_nif_rag/dropdown_catalog.json`

Tuning environment variables:
- `NIF_RAG_MAX_AUTO_STEPS` (default `10`)
- `NIF_RAG_RETRIEVAL_TOP_K` (default `4`)

## Offline RAG evaluation

1. Create a dataset file from the sample:
   `cp control_docs/rag_eval_questions.sample.jsonl control_docs/rag_eval_questions.jsonl`
2. Edit `control_docs/rag_eval_questions.jsonl` and label `expected_sources` and `expected_terms`.
   `expected_sources` supports either:
   - document + page match: `{"document_name":"NIF Training Deck v4.pdf","page_number":"24"}`
   - document-only match (any page): `{"document_name":"NIF Training Deck v4.pdf"}`
3. Run retrieval-only evaluation:
   `DEBUG=false .venv/bin/python lib/evaluate_rag.py --dataset control_docs/rag_eval_questions.jsonl`
4. Optional end-to-end answer check:
   `DEBUG=false .venv/bin/python lib/evaluate_rag.py --dataset control_docs/rag_eval_questions.jsonl --run-answer-check --strict-grounding`
5. Optional strict failure mode (default is continue-on-error and report error rates):
   `DEBUG=false .venv/bin/python lib/evaluate_rag.py --dataset control_docs/rag_eval_questions.jsonl --fail-fast`

Outputs are written under `logs/` as:
- `rag_eval_summary_YYYYMMDD_HHMMSS.json`
- `rag_eval_details_YYYYMMDD_HHMMSS.jsonl`
