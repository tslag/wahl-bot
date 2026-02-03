# WahlBot

A full-stack chat assistant for program ingestion, QA and discussion (React frontend + FastAPI backend).

**This README** gives quick setup, development and security guidance so you can run and extend the app locally.

**Quick Start**
- **Backend**: Python (uv) + FastAPI. Configure `.env`, then run the app.
- **Frontend**: Vite + React. Install deps and run dev server.

**Prerequisites**
- Node.js (16+) and npm or yarn
- Python 3.11+ and Poetry (or a virtualenv)
- Postgres18 (or any other version capable of running the vector extention)
- Docker Desktop
- uv

**Repository Layout (high level)**
- **backend/wahl_bot**: FastAPI backend (routes, auth, models, services)
- **frontend**: Vite + React app (components, contexts, services)

Getting started (development)
1. Backend

  - Create a `.env` file in `backend` (copy from `.env.example` if present) and set required variables. 

  - Crete a venv and install requirements using uv:
    ```powershell
    cd backend
    uv venv --python 3.11
    .venv\Scripts\activate
    uv pip install -r requirements.txt
    ```

  - Run PG Container and FastAPI ap in venv:
    ```powershell
    docker compose up -d
    cd wahl_bot
    uv run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

  - Notes:
    - The app mounts the API with `root_path="/api"` in development. The backend includes CORS and cookie-based refresh token support.
    - Database tables are created automatically on startup via the app lifespan hook (`initialize_database`).

2. Frontend

  - Install and run:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

  - Vite dev proxy: the frontend expects API calls at `/api/*` so the Vite dev server should proxy `/api` to the backend (see `vite.config.js`). If you prefer not to use the proxy, set `API_BASE_URL` in `frontend/src/util.js` to `http://localhost:8000/api` and ensure CORS `allow_credentials=True` on the backend.

Auth and persistence (how login persists across reloads)
- The backend issues a short-lived access token and stores a refresh token in an HttpOnly cookie. Frontend uses `credentials: 'include'` for auth requests.
- On page load `AuthContext` calls the `/auth/refresh` endpoint to obtain a fresh access token. `ProtectedRoute` waits for that initialization (`loading`) before redirecting to login.
- Files to inspect/adjust:
  - Frontend auth client: [frontend/src/services/authService.js](frontend/src/services/authService.js#L1)
  - Frontend auth provider: [frontend/src/contexts/AuthContext.jsx](frontend/src/contexts/AuthContext.jsx#L1)
  - Backend auth routes: [backend/wahl_bot/api/routes/auth_with_refresh.py](backend/wahl_bot/api/routes/auth_with_refresh.py#L1)

Security notes (important)
- Refresh tokens are stored in HttpOnly cookies to mitigate XSS exposure. Use `Secure` + HTTPS in production.
- Protect state-changing endpoints with CSRF mitigations (SameSite cookie + CSRF token or double-submit cookie pattern).
- Use short lifetimes for access tokens and rotate refresh tokens on use (implemented in the backend helper).
- Never store refresh tokens in localStorage/sessionStorage in production.

Developer tips
- Centralize API calls through `authService.apiRequest` so token refresh and retries are handled consistently.
- When adding new frontend network calls, remember to use relative `/api/...` paths so the Vite proxy applies, or use the configured `API_BASE_URL`.
- To locate work quickly:
  - App entry: [frontend/src/main.jsx](frontend/src/main.jsx#L1)
  - App providers and routes: [frontend/src/App.jsx](frontend/src/App.jsx#L1)
  - Program context: [frontend/src/contexts/ProgramContext.jsx](frontend/src/contexts/ProgramContext.jsx#L1)
  - Backend main: [backend/wahl_bot/main.py](backend/wahl_bot/main.py#L1)

Troubleshooting
- If login cookies are not persisted:
  - Ensure requests reach the backend (proxy enabled or API_BASE_URL points to backend)
  - Confirm `Set-Cookie` appears on the login response and cookie flags (`HttpOnly`, `Secure`) are compatible with your environment
  - Check that frontend requests use `credentials: 'include'`

Contributing
- Fork, make branches for features/fixes, open PRs with a short description and tests where practical.
