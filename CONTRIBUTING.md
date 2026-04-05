# Contributing Guide

Thank you for considering contributing to **voice-chat-assistant**.
This guide covers everything you need to set up a development environment,
follow project conventions, and submit high-quality changes.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Environment Setup](#development-environment-setup)
  - [Prerequisites](#prerequisites)
  - [Clone and Install](#clone-and-install)
  - [Start Development Services](#start-development-services)
  - [Hot-Reload Workflow](#hot-reload-workflow)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
  - [Python (Backend)](#python-backend)
  - [TypeScript / React (Frontend)](#typescript--react-frontend)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
  - [Branch Naming](#branch-naming)
  - [Commit Messages](#commit-messages)
  - [Pull Request Checklist](#pull-request-checklist)
- [Documentation Requirements](#documentation-requirements)
- [Security Guidelines](#security-guidelines)

---

## Code of Conduct

Be respectful, constructive, and inclusive in all interactions.
Focus feedback on code and ideas, not on individuals.

---

## Development Environment Setup

### Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| OS | Windows 11 or Ubuntu 20.04/22.04 | Primary dev targets |
| GPU | NVIDIA RTX (8 GB+ VRAM) | Required for STT + TTS |
| CUDA | 12.8+ | Must match `environment.yml` |
| Conda | Miniconda or Anaconda | Manages Python + PyTorch |
| Node.js | 20+ | Frontend toolchain |
| Docker Desktop | 24+ | Runs PostgreSQL and Redis |
| Git | Latest stable | SSH key recommended |

### Clone and Install

```bash
# 1. Fork and clone
git clone git@github.com:<your-username>/voice-chat-assistant.git
cd voice-chat-assistant

# 2. Add upstream remote
git remote add upstream git@github.com:lvzhuojun/voice-chat-assistant.git

# 3. Create conda environment (includes Python, Node.js, PyTorch/CUDA)
conda env create -f environment.yml
conda activate voice-chat

# 4. Clone GPT-SoVITS inference engine
git clone https://github.com/RVC-Boss/GPT-SoVITS.git GPT-SoVITS
# or on Windows:
setup\clone_gptsovits.bat

# 5. Download pretrained models
python setup/download_models.py

# 6. Configure environment
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET_KEY and DATABASE_URL
```

Generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Start Development Services

```bash
# Windows (cmd)
start.bat

# Windows (PowerShell)
.\start.ps1
```

This script:
1. Starts Docker containers (PostgreSQL + Redis)
2. Runs Alembic database migrations
3. Launches the backend (`uvicorn --reload`)
4. Launches the frontend (`vite --port 5173`)

The backend runs at **http://localhost:8000** and the frontend at **http://localhost:5173**.

To start services individually:

```bash
# Database services only
docker compose -f docker/docker-compose.yml up postgres redis -d

# Database migrations
conda activate voice-chat
alembic -c backend/alembic/alembic.ini upgrade head

# Backend (with hot-reload)
conda activate voice-chat
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (with HMR)
cd frontend
npm install
npm run dev
```

### Hot-Reload Workflow

| Layer | Trigger | Reload behavior |
|-------|---------|-----------------|
| Frontend `.ts` / `.tsx` | Save file | Vite HMR — instant, no page reload |
| Backend `.py` | Save file | uvicorn `--reload` — process restarts (~1–2 s) |
| Database schema | Edit `alembic/versions/` | Run `alembic upgrade head` manually |
| Docker services | Edit `docker-compose.yml` | Run `docker compose up -d` manually |
| `.env` file | Edit value | Restart backend manually |

---

## Project Structure

```
voice-chat-assistant/
├── backend/
│   ├── api/          # Route handlers: auth, voices, conversations, ws (WebSocket)
│   ├── core/         # Business logic: stt_engine, llm_client, tts_engine, pipeline, security
│   ├── models/       # SQLAlchemy ORM models: User, VoiceModel, Conversation, Message
│   ├── schemas/      # Pydantic request/response DTOs
│   ├── utils/        # File utilities, logger configuration
│   ├── alembic/      # Database migrations
│   └── main.py       # FastAPI app entry point
├── frontend/
│   └── src/
│       ├── api/        # Axios API client + per-resource modules
│       ├── components/ # Reusable UI components (AudioPlayer, MessageBubble, RecordButton)
│       ├── hooks/      # Custom hooks (useWebSocket, useAudioRecorder, useAuth)
│       ├── pages/      # Route-level pages (ChatPage, VoicePage, LoginPage, RegisterPage)
│       ├── store/      # Zustand state stores (authStore, chatStore, voiceStore)
│       └── types/      # Shared TypeScript interfaces
├── docker/           # Docker Compose + Dockerfiles + nginx.conf
├── setup/            # Installation scripts (install.bat, download_models.py)
├── docs/             # Documentation
└── storage/          # Runtime data — gitignored (voice models, audio, logs)
```

---

## Coding Standards

### Python (Backend)

- **Style:** PEP 8. Line length ≤ 100 characters.
- **Type hints:** Required on all function signatures (parameters and return type).
- **Async:** Use `async def` / `await` for all I/O-bound operations.
  Never call blocking functions in async handlers.
- **Error handling:** Raise `HTTPException` with specific status codes and
  English messages at API boundaries. Log unexpected exceptions with `logger.exception`.
- **Security:**
  - Never log passwords, tokens, or API keys.
  - Validate and sanitize all user-supplied file content (ZIP archives, audio).
  - Use parameterized queries via SQLAlchemy ORM — never raw string SQL.
- **Database:** Use `AsyncSession` for all database operations. No synchronous `session.execute`.
- **Imports:** Standard library → third-party → local, each group separated by one blank line.

### TypeScript / React (Frontend)

- **Style:** Follow the existing Vite + TypeScript project conventions.
  Prettier and ESLint configs are in `frontend/`.
- **Type safety:** Use explicit TypeScript types. Avoid `any`.
  Define all shared types in `frontend/src/types/index.ts`.
- **State management:** Use Zustand stores for global state.
  Keep component-local state with `useState`.
- **Hooks:** Custom hooks go in `frontend/src/hooks/`. One hook per file.
- **Components:** One component per file. Use `forwardRef` when the component
  is a direct child of `AnimatePresence`.
- **Security:**
  - Never store sensitive data (passwords, raw tokens) in component state or `localStorage`
    beyond what is necessary for session management.
  - Sanitize any user-generated content before rendering.
- **WebSocket:** Do not access `wsRef.current` directly from outside `useWebSocket`.
  Use the returned `sendAudio`, `sendText`, and `disconnect` methods.

---

## Testing

```bash
# Backend API tests (requires running backend)
conda activate voice-chat
python test_api.py

# Voice pipeline tests (requires GPU + voice model loaded)
conda activate voice-chat
python test_voice_pipeline.py

# Frontend type-check
cd frontend
npm run build   # TypeScript compilation errors will surface here
```

When adding a new feature:
- Add at least one happy-path test to `test_api.py`.
- For WebSocket behavior, test manually via the browser and document the test scenario
  in the PR description.

---

## Submitting Changes

### Branch Naming

```
feat/<short-description>      # New feature
fix/<short-description>       # Bug fix
docs/<short-description>      # Documentation only
refactor/<short-description>  # Code restructure, no behavior change
chore/<short-description>     # Build, CI, dependency updates
```

Examples: `feat/voice-equalizer`, `fix/ws-onclose-race`, `docs/api-update`

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short summary in imperative mood>

[Optional body: explain what changed and why, not how]

[Optional footer: references, breaking change notice]

Co-Authored-By: <name> <email>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`

**Scope** (optional): `ws`, `tts`, `stt`, `llm`, `auth`, `voice`, `chat`, `ui`, `docker`, `ci`

Examples:

```
fix(ws): guard onclose handler to prevent new WS reference from being wiped

feat(tts): add audio chunk accumulation for full message replay

docs: add DOC_STANDARD and CHANGELOG, update README directory structure
```

### Pull Request Checklist

Before marking your PR ready for review:

- [ ] Code compiles without errors (`npm run build` for frontend, `uvicorn` starts for backend)
- [ ] No `console.log` debug statements left in frontend code
- [ ] No hardcoded secrets, absolute paths, or personal information
- [ ] Documentation updated (see [Documentation Requirements](#documentation-requirements))
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]`
- [ ] PR description explains **what** changed and **why**
- [ ] PR description includes manual test steps or references existing tests

---

## Documentation Requirements

Every PR that changes behavior must update the relevant documentation.
See [docs/DOC_STANDARD.md](docs/DOC_STANDARD.md) for the complete rules.

**Quick reference:**

| What changed | Update these files |
|--------------|--------------------|
| New/changed feature | `README.md`, `README.zh.md`, `CHANGELOG.md` |
| New/changed API endpoint | `docs/API.md`, `CHANGELOG.md` |
| New/changed `.env` variable | `README.md` (env table), `.env.example`, `CHANGELOG.md` |
| New/changed startup step | `README.md`, `README.zh.md`, `docs/DEPLOY.md`, `CHANGELOG.md` |
| Architecture change | `ARCHITECTURE.md`, `CHANGELOG.md` |
| Database schema change | `ARCHITECTURE.md` (schema section), `CHANGELOG.md` |
| Voice import format change | `docs/VOICE_MODEL_IMPORT.md`, `CHANGELOG.md` |

---

## Security Guidelines

- **Report vulnerabilities privately** — see [SECURITY.md](SECURITY.md) for the process.
- **Input validation:** Validate all file uploads (ZIP structure, file size, MIME type)
  server-side. Never trust client-side validation alone.
- **Authentication:** All WebSocket connections require a valid JWT via `?token=` query
  parameter. All REST endpoints (except `/api/auth/register`, `/api/auth/login`,
  `/api/health`) require `Authorization: Bearer <token>`.
- **User isolation:** Every database query must filter by the authenticated `user_id`.
  Never return another user's data.
- **Dependencies:** When adding a new dependency, check it against known vulnerability
  databases (e.g., `pip-audit`, `npm audit`) before submitting the PR.
