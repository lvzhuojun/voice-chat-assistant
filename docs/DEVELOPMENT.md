# Development Guide

> **Audience:** Contributors and developers running the project locally for development.
> **Prerequisite:** Complete the [Quick Start](../README.md#quick-start) in the main README first.

---

## Table of Contents

- [Environment Overview](#environment-overview)
- [Starting Services Individually](#starting-services-individually)
- [Hot-Reload Reference](#hot-reload-reference)
- [Backend Development](#backend-development)
  - [Project Layout](#project-layout)
  - [Adding a New API Endpoint](#adding-a-new-api-endpoint)
  - [Database Migrations](#database-migrations)
  - [Logging](#logging)
- [Frontend Development](#frontend-development)
  - [Project Layout](#project-layout-1)
  - [Adding a New Page](#adding-a-new-page)
  - [State Management Pattern](#state-management-pattern)
  - [WebSocket Hook](#websocket-hook)
- [Testing](#testing)
- [Environment Variables Reference](#environment-variables-reference)
- [Troubleshooting Development Issues](#troubleshooting-development-issues)

---

## Environment Overview

| Service | URL | Start command |
|---------|-----|---------------|
| Frontend (Vite dev server) | http://localhost:5173 | `npm run dev` (in `frontend/`) |
| Backend (FastAPI) | http://localhost:8000 | `uvicorn backend.main:app --reload` |
| Swagger UI | http://localhost:8000/docs | (auto, when backend is running) |
| ReDoc | http://localhost:8000/redoc | (auto, when backend is running) |
| PostgreSQL | localhost:5432 | Docker Compose |
| Redis | localhost:6379 | Docker Compose |

Vite proxies `/api/*` and `/ws/*` to `localhost:8000`, so the frontend
always uses its own origin (`localhost:5173`) for all requests.

---

## Starting Services Individually

If `start.bat` / `start.ps1` is not suitable (e.g., you only need to restart the backend):

```bash
# 1. Start database services (if not already running)
docker compose -f docker/docker-compose.yml up postgres redis -d

# 2. Apply any pending migrations
conda activate voice-chat
alembic -c backend/alembic/alembic.ini upgrade head

# 3. Start backend
conda activate voice-chat
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start frontend (in a separate terminal)
cd frontend
npm install   # only needed after dependency changes
npm run dev
```

---

## Hot-Reload Reference

| Change type | Action needed |
|-------------|---------------|
| Edit any `.ts` / `.tsx` file | **Nothing** — Vite HMR updates the browser instantly |
| Edit any `.py` file | **Nothing** — uvicorn `--reload` restarts the backend (~1–2 s) |
| Edit `.env` | Restart the backend manually |
| Add a new Python dependency | `pip install <pkg>` + update `environment.yml` and `requirements.txt` |
| Add a new npm dependency | `npm install <pkg>` in `frontend/`; commit `package.json` and `package-lock.json` |
| Add/edit a migration | Run `alembic -c backend/alembic/alembic.ini upgrade head` |
| Edit `docker-compose.yml` | `docker compose -f docker/docker-compose.yml up -d` |
| Edit `nginx.conf` | `docker compose -f docker/docker-compose.yml restart frontend` |

---

## Backend Development

### Project Layout

```
backend/
├── main.py           # FastAPI app, lifespan, middleware, route inclusion
├── config.py         # Pydantic Settings — reads from .env
├── database.py       # SQLAlchemy async engine and session factory
├── api/
│   ├── auth.py       # POST /api/auth/register, /login, GET /me
│   ├── voices.py     # Voice model CRUD + test synthesis
│   ├── conversations.py  # Conversation + message CRUD
│   └── ws.py         # WS /ws/chat/{id} — STT → LLM → TTS pipeline
├── core/
│   ├── stt_engine.py     # faster-whisper wrapper
│   ├── llm_client.py     # OpenAI-compatible streaming client
│   ├── tts_engine.py     # GPT-SoVITS v2 wrapper with LRU cache
│   ├── pipeline.py       # Orchestrates STT → LLM → TTS per WebSocket turn
│   ├── security.py       # JWT creation and verification
│   └── limiter.py        # slowapi rate limiter instance
├── models/
│   ├── user.py
│   ├── voice_model.py
│   ├── conversation.py
│   └── message.py
├── schemas/
│   └── schemas.py        # All Pydantic DTOs
└── utils/
    ├── file_utils.py     # ZIP validation and extraction
    └── logger.py         # Loguru setup
```

### Adding a New API Endpoint

1. Add the route handler to the appropriate file in `backend/api/` (or create a new file).
2. Inject `AsyncSession` via `Depends(get_db)` for database access.
3. Inject the current user via `Depends(get_current_user)` for authentication.
4. Register the router in `backend/main.py` if adding a new file.
5. Add a Pydantic schema to `backend/schemas/schemas.py` for request/response.
6. **Update `docs/API.md`** with the new endpoint's documentation.

```python
# Example: backend/api/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.core.security import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/api/example", tags=["example"])

@router.get("/")
async def list_example(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Always filter by current_user.id — never return other users' data
    ...
```

### Database Migrations

Migrations live in `backend/alembic/versions/`. Always run Alembic from the
**project root** using the `-c` flag:

```bash
# Apply pending migrations
alembic -c backend/alembic/alembic.ini upgrade head

# Create a new migration (after editing SQLAlchemy models)
alembic -c backend/alembic/alembic.ini revision --autogenerate -m "add_column_xyz"

# Downgrade one step
alembic -c backend/alembic/alembic.ini downgrade -1

# View migration history
alembic -c backend/alembic/alembic.ini history
```

> **Warning:** Never edit a migration file that has already been applied to a
> shared database. Create a new migration instead.

### Logging

The project uses [Loguru](https://github.com/Delgan/loguru).

```python
from backend.utils.logger import logger

logger.info("Voice model loaded: {voice_id}", voice_id=voice_id)
logger.warning("TTS cache evicted: {evicted_id}", evicted_id=old_id)
logger.error("STT failed: {error}", error=str(e))
logger.exception("Unexpected error")   # includes stack trace
```

Never log passwords, API keys, JWT tokens, or other secrets.

---

## Frontend Development

### Project Layout

```
frontend/src/
├── api/
│   ├── client.ts         # Axios instance (base URL, token injection, error handling)
│   ├── auth.ts           # /api/auth/* calls
│   ├── conversations.ts  # /api/conversations/* calls
│   └── voices.ts         # /api/voices/* calls
├── components/
│   ├── chat/
│   │   ├── AudioPlayer.tsx    # Sequential multi-chunk audio playback
│   │   └── MessageBubble.tsx  # Chat message display (user + assistant roles)
│   └── voice/
│       └── RecordButton.tsx   # Record button with live waveform (AnalyserNode, 60 fps)
├── hooks/
│   ├── useAuth.ts           # Login / register / logout; redirects to /login when unauthed
│   ├── useAudioRecorder.ts  # MediaRecorder, WebM encoding, VAD auto-stop
│   └── useWebSocket.ts      # WS connection lifecycle, message routing, audio queue
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── ChatPage.tsx          # Main chat UI — orchestrates all hooks
│   └── VoicePage.tsx         # Voice model management
├── store/
│   ├── authStore.ts          # { user, token }
│   ├── chatStore.ts          # { conversations, messages, streamingText, messageAudioData, ... }
│   └── voiceStore.ts         # { voices, currentVoice }
└── types/
    └── index.ts              # All shared TypeScript interfaces
```

### Adding a New Page

1. Create `frontend/src/pages/NewPage.tsx`.
2. Add a route in `frontend/src/App.tsx`.
3. Add a navigation link where appropriate (sidebar in `ChatPage.tsx`, or a new nav component).
4. Add any required API calls in `frontend/src/api/`.
5. If the page needs global state, add it to the appropriate Zustand store.

### State Management Pattern

All global state lives in Zustand stores under `frontend/src/store/`.
Access state with a selector to avoid unnecessary re-renders:

```typescript
// Good — only re-renders when activeConversationId changes
const activeId = useChatStore((s) => s.activeConversationId)

// Avoid — re-renders on any store change
const store = useChatStore()
```

Local UI state (e.g., form inputs, modal open/closed) stays in `useState` within the component.

### WebSocket Hook

All WebSocket communication goes through `useWebSocket` in `ChatPage.tsx`.
Do not instantiate `WebSocket` directly in components.

The hook returns:

| Property | Type | Description |
|----------|------|-------------|
| `isConnected` | `boolean` | Current connection state |
| `wsError` | `string \| null` | Last server error message (auto-clears after 5 s) |
| `sendAudio` | `(blob: Blob) => void` | Send binary audio frame |
| `sendText` | `(text: string) => void` | Send text message |
| `disconnect` | `() => void` | Close the connection |

Both `sendAudio` and `sendText` safely handle `CONNECTING` state by queuing
the payload via `addEventListener('open', ..., { once: true })`.

---

## Testing

### API Tests

```bash
conda activate voice-chat
# Requires the backend to be running at http://localhost:8000
python test_api.py
```

`test_api.py` covers authentication, voice management, and conversation CRUD endpoints.

### Voice Pipeline Tests

```bash
conda activate voice-chat
# Requires a GPU, loaded STT model, and at least one imported voice model
python test_voice_pipeline.py
```

Tests the full STT → LLM → TTS pipeline end-to-end.

### Manual WebSocket Testing

1. Open http://localhost:5173 and log in.
2. Import a voice model (see `docs/VOICE_MODEL_IMPORT.md`).
3. Create a new conversation.
4. Click the microphone button and speak; verify:
   - Waveform animates while recording.
   - VAD stops recording after 1.5 s of silence.
   - Transcript appears as a user message.
   - LLM response streams in with typewriter effect.
   - Audio plays sentence by sentence without overlap.
   - Replay button plays the full response (all sentences).
5. Switch conversations and verify the WebSocket reconnects cleanly.

---

## Environment Variables Reference

All variables are defined in `.env.example`. Copy it to `.env` to get started.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HOST` | No | `0.0.0.0` | Backend bind address |
| `BACKEND_PORT` | No | `8000` | Backend port |
| `DATABASE_URL` | **Yes** | — | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection URL |
| `POSTGRES_PASSWORD` | No | dev default | PostgreSQL password (Docker Compose) |
| `REDIS_PASSWORD` | No | (none) | Redis auth password (production only) |
| `JWT_SECRET_KEY` | **Yes** | — | JWT signing secret (≥ 32 chars). Generate: `openssl rand -hex 32` |
| `JWT_EXPIRE_DAYS` | No | `7` | Token expiry in days |
| `LLM_API_KEY` | No | (none) | OpenAI-compatible API key; mock mode if empty |
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | LLM API base URL |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name passed to the LLM API |
| `WHISPER_MODEL_SIZE` | No | `medium` | faster-whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `WHISPER_DEVICE` | No | `cuda` | `cuda` or `cpu` |
| `GPTSOVITS_DIR` | No | `./GPT-SoVITS` | Path to cloned GPT-SoVITS repository |
| `VOICE_MODELS_DIR` | No | `./storage/voice_models` | User voice model storage root |
| `PRETRAINED_MODELS_DIR` | No | `./storage/pretrained_models/GPT-SoVITS` | Pretrained model weights root |
| `STORAGE_DIR` | No | `./storage` | Root for all runtime file storage |
| `CORS_ORIGINS` | No | (none) | Comma-separated extra CORS origins |
| `MAX_UPLOAD_SIZE_MB` | No | `500` | Maximum voice ZIP upload size |

---

## Troubleshooting Development Issues

### Backend fails to start — "No module named backend"

Run uvicorn from the project root, not from inside `backend/`:

```bash
# Correct (project root)
python -m uvicorn backend.main:app --reload

# Wrong (inside backend/)
uvicorn main:app --reload
```

### Alembic error — "No 'script_location' key found"

You are running alembic without the `-c` flag. Always specify the config:

```bash
alembic -c backend/alembic/alembic.ini upgrade head
```

### Frontend cannot reach the backend

Check that the Vite proxy is configured in `frontend/vite.config.ts`:

```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws':  { target: 'ws://localhost:8000', ws: true },
  }
}
```

If the backend is on a non-default port, update the proxy target.

### CUDA out of memory

The TTS LRU cache holds at most 3 voice models. If VRAM is tight, reduce this
in `backend/core/tts_engine.py` (the `maxsize` parameter of the LRU cache).
Alternatively, use `WHISPER_DEVICE=cpu` to free GPU memory from the STT model.

### WebSocket connects but audio is silent

1. Check that a voice model is imported and selected (Voice Management page).
2. Check browser permissions — microphone access must be granted.
3. Check the browser console for `audio_chunk` messages or errors.
4. Verify `LLM_API_KEY` is set, or confirm mock mode is working (backend logs).

### Docker containers not starting

```bash
# View container logs
docker compose -f docker/docker-compose.yml logs postgres
docker compose -f docker/docker-compose.yml logs redis

# Reset containers (keeps data volumes)
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml up -d
```
