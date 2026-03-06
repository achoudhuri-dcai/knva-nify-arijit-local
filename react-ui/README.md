# NIFTY React UI

Parallel React UI for Project NIFTY that runs alongside the existing Dash UI.

## Local run

1. Start backend Dash/Flask app (default `8052`, or your `DASH_PORT`):
   - `DEBUG=false .venv/bin/python DCAI_KN_Chat_Dash_UI_Gradio_Mock.py`
2. Start React dev server:
   - `cd react-ui`
   - `npm install`
   - if backend is not on `8052`, create `react-ui/.env.local`:
     - `VITE_API_PROXY_TARGET=http://localhost:<your_dash_port>`
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
