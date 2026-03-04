# NIFTY React UI

Parallel React UI for Project NIFTY that runs alongside the existing Dash UI.

## Local run

1. Start backend Dash/Flask app (port 8052):
   - `DEBUG=false .venv/bin/python DCAI_KN_Chat_Dash_UI_Gradio_Mock.py`
2. Start React dev server:
   - `cd react-ui`
   - `npm install`
   - `npm run dev`

## API routes used

- `POST /api/v1/session`
- `POST /api/v1/modules/select`
- `POST /api/v1/chat/turn`
- `GET /api/v1/me`
- `GET /api/v1/health/live`

## CORS allowlist

Set `REACT_UI_ALLOWED_ORIGINS` in backend `.env` (comma-separated), for example:

`REACT_UI_ALLOWED_ORIGINS=http://localhost:5173`
