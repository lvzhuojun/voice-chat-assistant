# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed

- **`useWebSocket` — `isConnected` flicker on conversation switch** — `setIsConnected(false)`
  moved inside the `wsRef.current === ws` guard in `onclose`. Previously the old connection's
  async close event fired after the new connection had already set `isConnected=true`, causing
  a brief grey indicator and potential state inconsistency.
- **`useWebSocket` — audio/text sent to wrong WebSocket in CONNECTING state** — The `open`
  event listener in `sendAudio`/`sendText` now uses the captured `ws` variable instead of
  `wsRef.current`. If a conversation switch happened between the send call and the open event,
  `wsRef.current` would have pointed to the new conversation's socket.
- **`useWebSocket` — hardcoded `ws://` breaks HTTPS/WSS deployments** — URL now derives
  protocol from `window.location.protocol`: `wss:` when the page is served over HTTPS,
  `ws:` otherwise. Previously any TLS-terminated deployment would fail silently.
- **`AudioPlayer` — stale metadata callbacks after `audioData` change** — Added `cancelled`
  flag and collected `tmp` Audio elements in the `useEffect` cleanup so that `onloadedmetadata`
  / `onerror` callbacks from a previous `audioData` value cannot write to stale refs or call
  `setTotalDuration` after the component has moved to new data.
- **`updateConversationTitle` — title sent as query param instead of request body** — Frontend
  now sends `{ title }` as JSON body; backend endpoint changed from `title: str` query
  parameter to `ConversationTitleUpdateRequest` Pydantic body model with `min_length=1`
  and `max_length=255` validation. The old query-param approach bypassed all Pydantic
  validators and was non-RESTful.
- **`client.ts` — `401` redirect matched any path containing `/login`** — Changed
  `pathname.includes('/login')` to `pathname === '/login'` to prevent false matches on paths
  like `/admin/login-settings`.
- **`ws.py` — `Callable` used as unresolved string forward reference** — Added
  `Callable, Awaitable` to the `from typing import ...` line; `_try_generate_title` signature
  now uses the proper `Callable[[dict], Awaitable[None]]` type instead of the string literal
  `"Callable"`.
- **`ChatPage` — mobile sidebar stays open after creating a new conversation** — Added
  `setIsSidebarOpen(false)` to `handleNewConversation` so the drawer closes automatically
  after the new conversation is created on narrow viewports.
- **`stt_engine` — FFmpeg subprocess and Whisper inference blocked the asyncio event loop** —
  `convert_audio_to_wav` is now `async`; the `subprocess.run` call is wrapped in
  `asyncio.to_thread`; Whisper `model.transcribe()` is executed inside `asyncio.to_thread`
  via an inner `_run_transcribe` helper. All three previously ran synchronously on the event
  loop thread, starving other coroutines during STT (typically 1–5 s per request).
- **`tts_engine` — GPT-SoVITS inference blocked the asyncio event loop** — The synchronous
  `tts.run()` generator loop (GPU inference, typically 2–10 s per sentence) is now executed
  inside `asyncio.to_thread` via `_run_inference`. Other WebSocket connections no longer
  stall while TTS is running.
- **`stt_engine` — Chinese segments joined with spaces** — Whisper segments are now
  concatenated with `"".join(...)` instead of `" ".join(...)`. Each segment already carries
  its own leading/trailing punctuation; the extra space produced garbled output for Chinese
  (e.g., "你好 世界" instead of "你好世界").

### Added

- `docs/TROUBLESHOOTING.md` — comprehensive consolidated troubleshooting guide
  covering installation (Windows _lzma / G2PWModel / fast_langdetect), backend
  startup, database, STT, TTS, WebSocket, frontend, voice import, and production
  deployment issues.

### Changed

- `docs/API.md` — added `seq` field to `audio_chunk` WebSocket message (was
  documented in `ARCHITECTURE.md` but missing from API reference); added rate
  limiting notice; clarified multi-chunk turn sequence.
- `docs/DEPLOY.md` — replaced literal `strongpassword` in the `DATABASE_URL`
  example with `<your-db-password>` placeholder (security rule compliance);
  added note about `download_models.py` configuring G2PWModel junction and
  `fast_langdetect` model.
- `README.md`, `README.zh.md` — added `docs/TROUBLESHOOTING.md` to the
  documentation table.
- `docs/DOC_STANDARD.md` — promoted `docs/TROUBLESHOOTING.md` to mandatory
  document inventory.

---

## [0.4.2] — 2026-04-04

### Fixed

- **WebSocket race condition on conversation switch** — `ws.onclose` now guards
  with `if (wsRef.current === ws)` before clearing the reference. Previously,
  the old connection's async close event fired after a new WebSocket was already
  stored, wiping the new reference and causing "WebSocket disconnected" errors
  when sending the first message in a new conversation.
- **Audio replay only played the last TTS sentence** — `useWebSocket` now
  accumulates all `audio_chunk` data in `currentAudioChunksRef` (previously
  only the last chunk was retained). The full array is saved to `messageAudioData`
  on `done`, enabling complete replay of multi-sentence responses.
- **`ERR_FILE_NOT_FOUND` on conversation switch** — `AudioPlayer` now pauses and
  clears `audio.src` before revoking blob URLs in the cleanup effect, preventing
  the browser from attempting to access a revoked URL.

### Changed

- `chatStore.messageAudioData` type changed from `Record<number, string>` to
  `Record<number, string[]>` to store all TTS audio chunks per message.
- `AudioPlayer` now accepts `audioData?: string[]` (array of base64 WAV chunks)
  and plays them sequentially with accurate total-duration and seek support.
- `MessageBubble` prop `audioData` type updated to `string[]`.

---

## [0.4.1] — 2026-04-02

### Fixed

- **WebSocket server errors not visible to users** — Added `wsError` state and a
  notice bar in `ChatPage` that displays server-side error messages (e.g.,
  "没有可用的音色") for 5 seconds then auto-dismisses.
- **"WebSocket not connected" during CONNECTING state** — `sendText` and
  `sendAudio` now detect `readyState === CONNECTING` and queue the payload via
  `addEventListener('open', ..., { once: true })` instead of immediately
  dropping the message.
- **Console errors for `GET /api/voices/current/info` 404** — `getCurrentVoice`
  now catches 404 internally and returns `{ data: null }`, preventing red
  console errors when no voice has been selected yet.
- **framer-motion `forwardRef` warning on VoiceCard** — Wrapped `VoiceCard` with
  `forwardRef` and forwarded `ref` to the root `motion.div` to satisfy
  `AnimatePresence mode="popLayout"` requirements.
- **Registration password validation mismatch** — Frontend now enforces the same
  rules as the backend: minimum 8 characters, must contain both letters and digits.
- **First-upload voice auto-selection** — When a user imports their first voice
  model and has no current voice set, the imported voice is automatically selected.

---

## [0.4.0] — 2026-04-01

### Added

- Comprehensive security audit and hardening pass.
- Open-source compliance review: removed absolute paths, personal data references,
  and non-public configuration from all tracked files.

### Fixed

- Various API alignment issues identified during audit.
- Environment configuration standardized across all startup scripts.

---

## [0.3.0] — 2026-03-28

### Added

- **VAD auto-stop recording** — Silence detection (1.5 s) automatically stops
  recording after speech ends; users no longer need to hold the button.
- **Mobile-responsive layout** — Slide-in sidebar drawer on mobile, hamburger
  menu, touch-optimized spacing for viewport widths below 768 px.

---

## [0.2.0] — 2026-03-25

### Added

- **Rate limiting** — `slowapi` rate limiter applied to all API endpoints to
  prevent abuse.
- **Docker production hardening** — `docker-compose.prod.yml` with resource
  limits, restart policies, and health checks.

---

## [0.1.0] — 2026-03-20

### Added

- Initial release of voice-chat-assistant (Project 2 of the voice-cloning pipeline).
- **Full-duplex WebSocket** pipeline: binary audio in → STT → LLM → TTS → audio out.
- **STT** — faster-whisper `medium` on CUDA; WebM → WAV conversion via ffmpeg.
- **LLM** — OpenAI-compatible streaming API; mock fallback when no key is set.
- **TTS** — GPT-SoVITS v2 with LRU model cache (max 3 voices in VRAM).
- **Sentence-level streaming TTS** — LLM output split at punctuation; each
  sentence synthesized and streamed immediately to reduce first-audio latency.
- **Ordered audio queue** — Promise-based sequential playback in the browser;
  no overlap, no out-of-order playback.
- **Real-time waveform** — Live 5-bar waveform on the record button, driven by
  `AnalyserNode` at 60 fps.
- **Auto conversation title** — LLM generates a concise title after the first
  turn; sidebar updated via `title_updated` WebSocket event.
- **Voice management** — Import voices as ZIP packages; switch active voice per
  conversation; LRU eviction when VRAM limit is reached.
- **JWT authentication** — Register / login; password complexity enforced
  (≥ 8 chars, letters + digits); all resources are user-scoped.
- **PostgreSQL persistence** — Conversations and messages stored in PostgreSQL
  via SQLAlchemy async + Alembic migrations.
- **Redis** — Active voice selection and LLM context (last 10 turns) stored
  in Redis.
- **Docker Compose** — PostgreSQL 16 + Redis 7 via `docker/docker-compose.yml`.
- **Windows startup scripts** — `start.bat` / `start.ps1` orchestrate Docker,
  migrations, backend, and frontend in one command.
