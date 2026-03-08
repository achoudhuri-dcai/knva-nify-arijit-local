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

## NIF Step By Step Engine

NIF Step by Step now runs in legacy mode only.

- `NIF_CHAT_ENGINE=legacy`
- Rule flow source: `control_docs/Expert_System_Rules.xlsx` (sheet `Implementation v1`) injected into the NIF guide prompt as `<STEP_BY_STEP_RULES>`.
- User progress persistence: user `.pkl` files plus Dash JSON state.
- Backend autosave interval for in-progress NIFs:
  - `NIF_BACKEND_SAVE_EVERY_STEPS` (default `5`)

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
   - if backend uses a non-default port, set proxy target in `react-ui/.env.local`:
     - `VITE_API_PROXY_TARGET=http://localhost:<DASH_PORT>`
   - `npm run dev`

CORS allow-list for React dev origins:
- `REACT_UI_ALLOWED_ORIGINS=http://localhost:5173`
- Local-only auth bypass for React API testing without ALB SSO headers:
  - `LOCAL_DEV_AUTH_BYPASS=true` (use only for localhost/dev)
- Temporary AWS dev auth bypass (not for production):
  - `AWS_DEV_AUTH_BYPASS=true`
  - `AWS_DEV_AUTH_BYPASS_KEY=<shared secret>`
  - React header key env: `VITE_AWS_DEV_AUTH_BYPASS_KEY=<same shared secret>`

Feature flag for enhanced NIF step starter/load flow in React:
- `REACT_NIF_STEP_ENHANCED=true`

Opik tracing (OpenTelemetry OTLP):
- `OPIK_TRACE_ENABLED=true`
- `OPIK_OTLP_ENDPOINT=http://otel-collector:4317`
- `OPIK_OTLP_INSECURE=true`
- `OPIK_PROJECT_NAME=knva-nifty`
- `OPIK_SERVICE_NAME=dcai-app`
- `OPIK_ENV=local|qa|prod`
- `OPIK_TRACE_SAMPLE_RATE=0.0..1.0`

Opik UI-native traces (Opik Python SDK):
- `OPIK_SDK_TRACE_ENABLED=true`
- `OPIK_SDK_HOST=http://opik-backend-1:8080`
- `OPIK_SDK_WORKSPACE=default`
- `OPIK_SDK_PROJECT_NAME=Default Project`

## Dash QA merge track

For staged migration of Dash-only UI behavior from the QA repo into this codebase:
- `DASH_UI_QA_MERGE=false` (default)
- Set `DASH_UI_QA_MERGE=true` only when validating a gated merge slice.

Implementation notes for this effort are tracked in:
- `docs/merge_qa_plan.md`
- `docs/merge_qa_callback_matrix.csv`

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
