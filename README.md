# knva-nifty
Project NIFTY: a web application to assist Kellanova employees with the New Item Form.

NIFTY has a chatbot interface and uses LLM agents to perform tasks such as searching documentation, querying databases, and checking process rules as needed to answer user questions.

## Unified LLM provider selection

Use one env selection for all user modules:
- `Get started on training resources`
- `NIF step by step` (and `NIF field question` flow)
- `Search NIF`

Primary env variables:
- `APP_LLM_PROVIDER=bedrock|openai`
- `APP_LLM_MODEL=<single model used across modules>`

Provider-specific auth:
- Bedrock IAM (recommended on EC2):
  - `APP_LLM_PROVIDER=bedrock`
  - `BEDROCK_AUTH_MODE=iam` (or `auto`)
  - `BEDROCK_REGION=us-east-1` (or use `AWS_REGION` / `AWS_DEFAULT_REGION`)
- Bedrock API key:
  - `APP_LLM_PROVIDER=bedrock`
  - `BEDROCK_AUTH_MODE=api_key`
  - `AWS_BEARER_TOKEN_BEDROCK=<bedrock_api_key_value>`
  - `BEDROCK_REGION=us-east-1`
- OpenAI API key:
  - `APP_LLM_PROVIDER=openai`
  - `OPENAI_API_KEY=<key>`
  - optional `OPENAI_BASE_URL=<gateway_or_proxy>`

Model overrides (optional):
- Bedrock: `BEDROCK_CHAT_MODEL`, `BEDROCK_DOCSEARCH_MODEL`, `BEDROCK_NIFGUIDE_MODEL`, `BEDROCK_SQL_MODEL`, `BEDROCK_VISION_MODEL`
- OpenAI: `OPENAI_CHAT_MODEL`, `OPENAI_DOCSEARCH_MODEL`, `OPENAI_NIFGUIDE_MODEL`, `OPENAI_SQL_MODEL`, `OPENAI_VISION_MODEL`

Embedding config:
- OpenAI: `OPENAI_EMBED_MODEL`, `OPENAI_EMBED_DIMENSIONS`
- Bedrock: `BEDROCK_EMBED_MODEL`, `BEDROCK_EMBED_DIMENSIONS`, `BEDROCK_EMBED_NORMALIZE`

Backward compatibility:
- If `APP_LLM_PROVIDER` is not set, the app falls back to `VECTORSTORE_LLM_PROVIDER`.

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

## Parallel React UI

A new React UI is available under `react-ui/` and runs in parallel to the existing Dash UI.

Backend API routes exposed by Flask:
- `GET /api/v1/health/live`
- `GET /api/v1/me`
- `POST /api/v1/session`
- `GET /api/v1/modules`
- `POST /api/v1/modules/select`
- `POST /api/v1/chat/turn`
- `GET /api/v1/nif/step/options`
- `GET /api/v1/nif/saved`
- `POST /api/v1/nif/new-session`
- `POST /api/v1/nif/load-session`
- `POST /api/v1/nif/save-session`
- `POST /api/v1/nif/reload-config`
- `POST /api/v1/nif/progress-preview`
- `POST /api/v1/nif/download`

React UI dev run:
1. Start backend app:
   - `DEBUG=false .venv/bin/python DCAI_KN_Chat_Dash_UI_Gradio_Mock.py`
2. Start React app:
   - `cd react-ui`
   - `npm install`
   - `npm run dev`

CORS allow-list for React dev origins:
- `REACT_UI_ALLOWED_ORIGINS=http://localhost:5173`

Feature flag for enhanced NIF step starter/load flow in React:
- `REACT_NIF_STEP_ENHANCED=true`

## Vectorstore maintenance

Clear all collections in the project vectorstore:

`DEBUG=false .venv/bin/python lib/clear_vectorstore.py`

Optional custom folder:

`DEBUG=false .venv/bin/python lib/clear_vectorstore.py --folder /path/to/vectorstore`

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
