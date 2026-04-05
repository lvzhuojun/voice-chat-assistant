# Troubleshooting Guide

> **Audience:** Developers and users encountering errors during setup, development, or production.
> **Prerequisite:** You have followed either the [Quick Start](../README.md#quick-start)
> or the [Production Deployment Guide](DEPLOY.md).

[中文 README](../README.zh.md) | [English README](../README.md)

---

## Table of Contents

- [Installation & Environment](#installation--environment)
  - [conda not found in Git Bash / terminal](#conda-not-found-in-git-bash--terminal)
  - [npm not found in PATH](#npm-not-found-in-path)
  - [_lzma / lzma import error on Windows](#_lzma--lzma-import-error-on-windows)
  - [G2PWModel path not found](#g2pwmodel-path-not-found)
  - [fast_langdetect model missing](#fast_langdetect-model-missing)
- [Backend Startup](#backend-startup)
  - [No module named 'backend'](#no-module-named-backend)
  - [Alembic — No 'script_location' key found](#alembic--no-script_location-key-found)
  - [Alembic — relation already exists](#alembic--relation-already-exists)
  - [Weak JWT_SECRET_KEY warning at startup](#weak-jwt_secret_key-warning-at-startup)
- [Database & Docker](#database--docker)
  - [Docker containers not starting](#docker-containers-not-starting)
  - [PostgreSQL port already in use](#postgresql-port-already-in-use)
  - [Redis connection refused](#redis-connection-refused)
- [STT (Speech-to-Text)](#stt-speech-to-text)
  - [faster-whisper fails to load](#faster-whisper-fails-to-load)
  - [STT produces empty or garbled transcripts](#stt-produces-empty-or-garbled-transcripts)
- [TTS (Text-to-Speech)](#tts-text-to-speech)
  - [TTS engine fails to start / pretrained models missing](#tts-engine-fails-to-start--pretrained-models-missing)
  - [CUDA out of memory during TTS](#cuda-out-of-memory-during-tts)
  - [Audio is silent after recording](#audio-is-silent-after-recording)
- [WebSocket](#websocket)
  - [WebSocket connects but audio is never played](#websocket-connects-but-audio-is-never-played)
  - [WebSocket disconnects when switching conversations](#websocket-disconnects-when-switching-conversations)
  - [Nginx drops WebSocket connections](#nginx-drops-websocket-connections)
- [Frontend](#frontend)
  - [Frontend cannot reach the backend](#frontend-cannot-reach-the-backend)
  - [TypeScript build errors](#typescript-build-errors)
  - [Microphone permission denied](#microphone-permission-denied)
- [Voice Model Import](#voice-model-import)
  - [400 Bad Request on ZIP upload](#400-bad-request-on-zip-upload)
  - [413 Request Entity Too Large](#413-request-entity-too-large)
  - [409 Conflict — voice ID already imported](#409-conflict--voice-id-already-imported)
- [Production / HTTPS](#production--https)
  - [CUDA not available inside Docker](#cuda-not-available-inside-docker)
  - [WebSocket blocked by browser (mixed content)](#websocket-blocked-by-browser-mixed-content)
- [Known Limitations](#known-limitations)

---


## Installation & Environment


### conda not found in Git Bash / terminal

**Symptom:** `conda: command not found` in Git Bash or a similar shell.

**Cause:** Conda is not on the `PATH` in non-Anaconda shells on Windows.

**Fix:**

```powershell
# Option 1 — run all conda commands through PowerShell
powershell.exe -Command "conda activate voice-chat && python ..."

# Option 2 — open Anaconda Prompt directly and run commands there

# Option 3 — add conda to PATH (permanent, run in PowerShell as Administrator)
conda init bash
# then restart Git Bash
```

---

### npm not found in PATH

**Symptom:** `npm: command not found` when running frontend commands.

**Cause:** Node.js was installed to a non-standard location and the directory is
not in `PATH`.

**Fix:** Find your Node installation path and use the full path, or add it to
your `PATH` environment variable:

```powershell
# Find Node.js location
where.exe node

# Then call npm explicitly, e.g.:
"C:\Program Files\nodejs\npm.cmd" install
```

---

### _lzma / lzma import error on Windows

**Symptom:**

```
ModuleNotFoundError: No module named '_lzma'
```

or

```
UserWarning: lzma module not available
```

**Cause:** The `_lzma.pyd` DLL is missing from the conda environment on some
Windows installations.

**Fix:** Run the automated repair included in the setup script:

```bat
setup\install.bat
```

Or repair manually by copying the DLL from the Anaconda base environment:

```powershell
# PowerShell — replace D:\Anaconda3 with your Anaconda install path
$base = "D:\Anaconda3"
$env  = "$base\envs\voice-chat"

Copy-Item "$base\DLLs\_lzma.pyd"          "$env\DLLs\_lzma.pyd"
Copy-Item "$base\Library\bin\liblzma.dll"  "$env\Library\bin\liblzma.dll"
```

---

### G2PWModel path not found

**Symptom:** TTS fails with a path error mentioning `G2PWModel` during
Chinese text preprocessing.

**Cause:** The G2PWModel directory junction was not created.

**Fix:**

```bat
# Windows — re-run the setup script which creates the junction automatically
python setup/download_models.py
```

If you are setting up manually, create a junction from the project root:

```powershell
# PowerShell
New-Item -ItemType Junction `
  -Path "GPT_SoVITS\text\G2PWModel" `
  -Target "..\voice-cloning-service\GPT-SoVITS\GPT_SoVITS\text\G2PWModel"
```

---

### fast_langdetect model missing

**Symptom:**

```
FileNotFoundError: ... lid.176.bin
```

**Cause:** The `fast_langdetect` language-identification model file is absent.

**Fix:**

```bat
python setup/download_models.py
```

Or copy from `voice-cloning-service` if Project 1 is already set up:

```powershell
Copy-Item `
  "..\voice-cloning-service\GPT-SoVITS\GPT_SoVITS\pretrained_models\fast_langdetect\lid.176.bin" `
  "GPT_SoVITS\pretrained_models\fast_langdetect\lid.176.bin"
```

---


## Backend Startup


### No module named 'backend'

**Symptom:**

```
ModuleNotFoundError: No module named 'backend'
```

**Cause:** `uvicorn` is being run from inside the `backend/` subdirectory instead
of the project root.

**Fix:** Always run from the project root:

```bash
# Correct — run from project root
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Wrong — do NOT cd into backend/ first
```

---

### Alembic — No 'script_location' key found

**Symptom:**

```
FAILED: No 'script_location' key found in configuration.
```

**Cause:** Alembic is run without the `-c` flag and cannot find `alembic.ini`.

**Fix:**

```bash
alembic -c backend/alembic/alembic.ini upgrade head
```

---

### Alembic — relation already exists

**Symptom:** Alembic reports `relation "users" already exists` (or similar) on a
fresh deployment.

**Cause:** The database was partially initialized before migrations ran.

**Fix (development only — destroys all data):**

```bash
docker compose -f docker/docker-compose.yml exec postgres \
  psql -U voice -c "DROP DATABASE voicechat; CREATE DATABASE voicechat;"

alembic -c backend/alembic/alembic.ini upgrade head
```

> **Warning:** This deletes all data. Do not run in production without a backup.

---

### Weak JWT_SECRET_KEY warning at startup

**Symptom:** The backend logs a warning like:

```
WARNING: JWT_SECRET_KEY is too short or uses the default value. Set a strong secret in .env.
```

**Fix:** Generate a proper 32-byte hex secret and set it in `.env`:

```bash
# Generate a secure key
openssl rand -hex 32
# or:
python -c "import secrets; print(secrets.token_hex(32))"
```

Then update `.env`:

```bash
JWT_SECRET_KEY=<paste-the-generated-value-here>
```

---


## Database & Docker


### Docker containers not starting

**Symptom:** `docker compose up` returns errors or containers exit immediately.

**Diagnosis:**

```bash
# Check container logs
docker compose -f docker/docker-compose.yml logs postgres
docker compose -f docker/docker-compose.yml logs redis
```

**Common fixes:**

```bash
# Restart containers (keeps data volumes)
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml up -d

# If volumes are corrupted, reset completely (destroys all data)
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml up -d
```

> **Warning:** `down -v` deletes all database data permanently.

---

### PostgreSQL port already in use

**Symptom:**

```
Error starting userland proxy: listen tcp 0.0.0.0:5432: bind: address already in use
```

**Cause:** Another PostgreSQL instance is running on the host.

**Fix (option 1):** Stop the conflicting service:

```bash
# Linux
sudo systemctl stop postgresql

# Windows
net stop postgresql-x64-14
```

**Fix (option 2):** Change the host-side port in `docker/docker-compose.yml`:

```yaml
ports:
  - "5433:5432"   # host port 5433 → container port 5432
```

Then update `DATABASE_URL` in `.env` accordingly:

```bash
DATABASE_URL=postgresql://voice:<your-db-password>@localhost:5433/voicechat
```

---

### Redis connection refused

**Symptom:**

```
aioredis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**Cause:** Redis container is not running.

**Fix:**

```bash
docker compose -f docker/docker-compose.yml up redis -d
```

---


## STT (Speech-to-Text)


### faster-whisper fails to load

**Symptom:** Backend startup shows:

```
ERROR: Failed to load faster-whisper model
```

**Diagnosis steps:**

1. Confirm CUDA is available:
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```
2. Check available VRAM (need ~1.5 GB for `medium`):
   ```bash
   nvidia-smi
   ```
3. Fall back to CPU if VRAM is unavailable:
   ```bash
   # In .env
   WHISPER_DEVICE=cpu
   ```

---

### STT produces empty or garbled transcripts

**Possible causes and fixes:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty transcript, no text | Microphone not capturing audio | Check browser microphone permission; try a different browser |
| Garbled text | Wrong `WHISPER_MODEL_SIZE` for the language | Use `medium` or `large` for non-English |
| Silence detected immediately | VAD threshold too sensitive | Speak louder; move away from background noise |
| Transcript appears but in wrong language | Language auto-detect wrong | Currently auto-detected; check `faster-whisper` `language` parameter in `stt_engine.py` |

---


## TTS (Text-to-Speech)


### TTS engine fails to start / pretrained models missing

**Symptom:**

```
FileNotFoundError: ... chinese-hubert-base
```

**Fix:**

```bash
conda activate voice-chat
python setup/download_models.py
```

Confirm the directory structure is correct:

```bash
ls storage/pretrained_models/GPT-SoVITS/
# Expected: chinese-hubert-base  chinese-roberta-wwm-ext-large
```

---

### CUDA out of memory during TTS

**Symptom:**

```
RuntimeError: CUDA out of memory
```

**Cause:** The LRU cache holds up to 3 voice models in VRAM simultaneously.

**Fixes:**

- Reduce the LRU cache size in `backend/core/tts_engine.py` (change `maxsize=3`
  to a smaller value).
- Free GPU memory used by the STT model:
  ```bash
  # In .env
  WHISPER_DEVICE=cpu
  ```
- Use a GPU with more VRAM (16 GB+ recommended for 3 concurrent models).

---

### Audio is silent after recording

**Diagnosis checklist:**

1. Verify a voice model is imported and selected (**Voice Management** page).
2. Check browser microphone permissions — the browser must have microphone access.
3. Open the browser console (F12) and look for `audio_chunk` messages or errors.
4. Check backend logs for TTS errors.
5. Verify LLM is responding — check that `LLM_API_KEY` is set, or confirm mock
   mode is active:
   ```bash
   # Backend logs should show:
   # INFO: LLM mock mode — no LLM_API_KEY set
   ```

---


## WebSocket


### WebSocket connects but audio is never played

**Symptom:** The transcript and LLM text appear, but no audio plays.

**Possible causes:**

| Cause | Fix |
|-------|-----|
| No voice model selected | Go to **Voice Management** and click **Set as Current** |
| TTS engine not loaded | Check backend logs; run `GET /api/health` and inspect `whisper_loaded` and `tts_models_loaded` |
| Browser autoplay policy blocked | Click anywhere on the page before recording; modern browsers require a user gesture before audio can play |
| Blob URL revoked too early | Update to latest version — fixed in v0.4.2 |

---

### WebSocket disconnects when switching conversations

**Symptom:** After switching to a different conversation, the first message shows
"WebSocket disconnected".

**Status:** Fixed in **v0.4.2**. The `onclose` handler now guards against wiping
a new connection's reference.

If you are still experiencing this, ensure you are on the latest commit:

```bash
git pull
```

---

### Nginx drops WebSocket connections

**Symptom:** WebSocket connection works locally but drops immediately behind Nginx.

**Fix:** Ensure `docker/nginx/nginx.conf` has the WebSocket upgrade headers for
`/ws/` locations:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 3600s;
```

---


## Frontend


### Frontend cannot reach the backend

**Symptom:** API calls return `ECONNREFUSED` or `net::ERR_CONNECTION_REFUSED`.

**Cause:** The Vite proxy is misconfigured or the backend is not running.

**Fix:** Verify `frontend/vite.config.ts` contains:

```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws':  { target: 'ws://localhost:8000', ws: true },
  }
}
```

If the backend runs on a different port, update the target URLs accordingly.

---

### TypeScript build errors

**Symptom:** `npm run build` fails with TypeScript errors.

**Common causes:**

| Error | Fix |
|-------|-----|
| `erasableSyntaxOnly` is not a recognized compiler option | Remove `erasableSyntaxOnly` and `noUncheckedSideEffectImports` from `tsconfig.node.json` (not supported in TypeScript < 5.8) |
| `Type 'X' is not assignable to type 'Y'` | Check that you are using the correct prop types from `frontend/src/types/index.ts` |
| Cannot find module `@/...` | Ensure `frontend/tsconfig.json` has the path alias configured |

---

### Microphone permission denied

**Symptom:** Recording does not start; browser shows a permission error.

**Fix:**

1. Click the lock icon in the browser address bar.
2. Set **Microphone** to **Allow**.
3. Reload the page.

> **Note:** Chrome and Firefox require a secure context (HTTPS or `localhost`)
> for microphone access. The development server on `localhost:5173` satisfies this.

---


## Voice Model Import


### 400 Bad Request on ZIP upload

**Symptom:** Importing a voice ZIP returns a 400 error.

**Causes and fixes:**

| Cause | Fix |
|-------|-----|
| Missing required files | ZIP must contain exactly: `{voice_id}_gpt.ckpt`, `{voice_id}_sovits.pth`, `metadata.json`, `reference.wav` — all at the root level (no subdirectories) |
| Wrong `base_model_version` | `metadata.json` must have `"base_model_version": "GPT-SoVITS v2"` — other versions are not supported |
| Files nested in a subdirectory | Re-create the ZIP with files at the root: `zip -j output.zip path/to/model/*` |

---

### 413 Request Entity Too Large

**Symptom:** Upload fails with a 413 error.

**Cause:** The ZIP exceeds `MAX_UPLOAD_SIZE_MB` (default 500 MB).

**Fix:** Increase the limit in `.env`:

```bash
MAX_UPLOAD_SIZE_MB=1000
```

---

### 409 Conflict — voice ID already imported

**Symptom:** Import returns 409.

**Cause:** A voice with the same `voice_id` (UUID from `metadata.json`) has
already been imported by this user.

**Fix:**

- If you retrained the model and want to replace it, first delete the existing
  voice via the **Voice Management** page, then re-upload.
- If you want to import the same model again, generate a new UUID in `metadata.json`
  before packaging the ZIP.

---


## Production / HTTPS


### CUDA not available inside Docker

**Symptom:** `torch.cuda.is_available()` returns `False` inside the container.

**Diagnosis:**

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

If this fails, install the NVIDIA Container Toolkit:

```bash
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list \
  | tee /etc/apt/sources.list.d/nvidia-docker.list
apt update && apt install -y nvidia-container-toolkit
systemctl restart docker
```

Then ensure `docker-compose.yml` has the `deploy.resources` GPU reservation:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

---

### WebSocket blocked by browser (mixed content)

**Symptom:** The app is served over HTTPS but WebSocket connections fail with a
mixed-content error in the browser console.

**Cause:** The page is loaded over HTTPS, so the browser blocks unencrypted `ws://`
connections as mixed content.

**Status:** This is handled automatically since v0.4.3. `useWebSocket` derives the
protocol from `window.location.protocol` — it connects with `wss://` when the page is
served over HTTPS and `ws://` otherwise. No manual change is required.

If you see this error on an older build, verify that `frontend/src/hooks/useWebSocket.ts`
contains the protocol-aware URL:

```typescript
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/${conversationId}?token=${token}`
```

Also ensure Nginx terminates TLS and proxies the `/ws/` location with `proxy_http_version 1.1`
and the required `Upgrade` / `Connection` headers (see [Nginx drops WebSocket connections](#nginx-drops-websocket-connections)).

---


## Known Limitations

| Limitation | Notes |
|-----------|-------|
| Audio replay is session-only | TTS audio is stored in browser memory for the current session only. Replay is not available after a page reload. |
| No JWT revocation | Tokens remain valid until they expire. Changing `JWT_SECRET_KEY` invalidates all tokens immediately. |
| No CAPTCHA on registration | Automated account creation is only limited by the API rate limiter. |
| WebSocket token in URL | The JWT is passed as a `?token=` query parameter. Ensure Nginx access logs are restricted to prevent token leakage via log files. |
| GPT-SoVITS v2 only | Only `base_model_version: "GPT-SoVITS v2"` is supported. Models trained with v1 or other versions are rejected at upload. |
| Windows junctions not auto-created on Linux | The `G2PWModel` and `fast_langdetect` paths use Windows junctions in the current setup. On Linux, `setup/download_models.py` creates symlinks instead. |
| iOS virtual keyboard overlap | On iOS Safari the bottom input bar may be partially hidden when the virtual keyboard opens. The layout uses `100vh` which does not account for the keyboard. Workaround: scroll the page down, or switch to landscape mode. |
