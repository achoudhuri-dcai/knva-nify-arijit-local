# Dash QA Merge Plan (Branch: merge-qa)

Goal: merge useful Dash UI changes from `/Users/arijitchoudhuri/ai_app/dcai/knva-nifty-qa` into this repo without changing core app logic (agent/task flow, API contracts, data model).

## Guardrails
- Keep `DCAI_KN_Chat_Dash_UI_Gradio_Mock.py` in this repo as source-of-truth.
- Do not wholesale-copy QA `lib/` or main app file.
- Keep React/API v1 routes unchanged.
- Port Dash-only presentation/UX behavior in small slices behind a feature flag.

## Feature Flag
- Env flag: `DASH_UI_QA_MERGE=false` (default)
- Purpose: safely enable/disable staged QA UI behavior.

## Phases
1. Baseline and scaffolding
- Add feature flag and expose in `/api/v1/health/live`.
- Create callback matrix and smoke checklist.

2. Safe visual parity
- Port CSS-only tweaks and static layout text updates.
- No callback behavior changes.

3. Non-core callback parity
- Port/tune non-business callbacks first (dialogs, show/hide, minor UX state).
- Keep all agent/task execution paths untouched.

4. Higher-risk UX parity with adapters
- QA callback behavior that depends on older internals should call current equivalents.
- Avoid introducing old query/agent flow from QA.

5. Regression and rollout
- Validate Dash and React flows side-by-side.
- Keep feature flag off by default until sign-off.

## Out of Scope (for initial merge)
- Replacing current `lib/nif_rag_engine.py` and related RAG stack with QA variants.
- Mass import/swap of `assets/raw_docs`, `vectorstore`, or QA infra scripts.
- Requirements changes not directly required for Dash UI parity.

## Smoke Checklist
- App loads and module switching works.
- NIF step-by-step: new/load/save/download works.
- Search NIF flow works.
- Chat history show/hide and clear work.
- Feedback save works.
- React API endpoints still respond as before.
