# Architecture

[中文 README](README.zh.md) | [English README](README.md)

---

## Table of Contents

- [System Overview](#system-overview)
- [WebSocket Message Flow](#websocket-message-flow)
- [Voice Model File Layout](#voice-model-file-layout)
- [Database Schema](#database-schema)
- [Production Deployment](#production-deployment)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React)                           │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │LoginPage │  │ChatPage  │  │VoicePage │  │RegisterPage    │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│        │             │              │                             │
│  ┌─────▼─────────────▼──────────────▼────────────────────────┐  │
│  │           Zustand Stores  (auth / chat / voice)            │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │  axios / WebSocket                 │
└──────────────────────────────┼─────────────────────────────────┘
                               │
                   ┌───────────▼──────────┐
                   │     Nginx (80/443)    │
                   │  reverse proxy + WS  │
                   └───────────┬──────────┘
                               │
             ┌─────────────────┼──────────────────┐
             │                 │                  │
   ┌─────────▼──────┐  ┌───────▼──────┐  ┌───────▼───────┐
   │  REST API       │  │  WebSocket   │  │  Static Files  │
   │  /api/*         │  │  /ws/chat/*  │  │  (frontend)    │
   └─────────┬──────┘  └───────┬──────┘  └───────────────┘
             │                 │
   ┌─────────▼─────────────────▼──────────────────────────┐
   │                     FastAPI                            │
   │                                                        │
   │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
   │  │ auth.py  │  │voices.py │  │ conversations.py   │  │
   │  └──────────┘  └──────────┘  └────────────────────┘  │
   │                                                        │
   │  ┌─────────────────────────────────────────────────┐  │
   │  │                  Pipeline                        │  │
   │  │                                                   │  │
   │  │  raw audio                                        │  │
   │  │      │                                            │  │
   │  │  ┌───▼────────────────┐                          │  │
   │  │  │  STT Engine        │  faster-whisper (CUDA)   │  │
   │  │  │  WebM → WAV → text │                          │  │
   │  │  └───┬────────────────┘                          │  │
   │  │      │ transcript text                            │  │
   │  │  ┌───▼────────────────┐                          │  │
   │  │  │  LLM Client        │  OpenAI-compatible       │  │
   │  │  │  streaming reply   │  (mock if no key)        │  │
   │  │  └───┬────────────────┘                          │  │
   │  │      │ reply text                                 │  │
   │  │  ┌───▼────────────────┐                          │  │
   │  │  │  TTS Engine        │  GPT-SoVITS v2 (CUDA)   │  │
   │  │  │  text → audio      │  LRU cache (max 3)       │  │
   │  │  └───┬────────────────┘                          │  │
   │  │      │ WAV chunks                                 │  │
   │  └──────┼───────────────────────────────────────────┘  │
   │         │ push over WebSocket                           │
   └─────────┼──────────────────────────────────────────────┘
             │
   ┌─────────┼──────────────────────────────────────────────┐
   │         │            Storage Layer                       │
   │  ┌──────▼─────┐  ┌───────────────┐  ┌──────────────┐  │
   │  │ PostgreSQL  │  │     Redis     │  │  Filesystem  │  │
   │  │ users       │  │ sessions      │  │ model files  │  │
   │  │ voices      │  │ context       │  │ audio cache  │  │
   │  │ messages    │  │ active voice  │  │              │  │
   │  └────────────┘  └───────────────┘  └──────────────┘  │
   └───────────────────────────────────────────────────────┘
```

---

## WebSocket Message Flow

```
User holds record button
        │
        ▼
[Browser]  MediaRecorder  →  WebM binary frames
        │
        │ (binary WebSocket frames)
        ▼
[Server]   ws.py  receives audio chunks
        │
        ▼
[STT]      faster-whisper transcribes
        │
        │  {"type": "transcript", "text": "..."}
        ▼
[Browser]  displays transcript

[LLM]      streaming request
        │
        │  {"type": "llm_chunk", "text": "..."}  × N
        ▼
[Browser]  typewriter effect

[LLM stream] sentence boundary detected → TTS triggered per sentence
        │
        │  (sentence 1 ready)
        ▼
[TTS]      GPT-SoVITS synthesis — sentence 1
        │
        │  {"type": "audio_chunk", "data": "<base64>", "seq": 0}
        ▼
[Browser]  audio queue — plays sentence 1 immediately

[TTS]      GPT-SoVITS synthesis — sentence 2, 3, ...
        │
        │  {"type": "audio_chunk", "data": "<base64>", "seq": N}
        ▼
[Browser]  audio queue — plays in order, no overlap

        │
        ▼
{"type": "done", "message_id": "..."}
        │
        ▼ (first turn only, title was "新对话")
{"type": "title_updated", "title": "..."}
```

### WebSocket Message Types

| Direction | Type | Payload | Description |
|-----------|------|---------|-------------|
| Client → Server | binary | `<audio bytes>` | WebM/WAV audio frame |
| Client → Server | text | `{"type":"text","content":"..."}` | Text input |
| Server → Client | `transcript` | `{"type":"transcript","text":"..."}` | STT result |
| Server → Client | `llm_chunk` | `{"type":"llm_chunk","text":"..."}` | LLM streaming token |
| Server → Client | `audio_chunk` | `{"type":"audio_chunk","data":"<b64>","seq":0}` | TTS audio chunk (sentence index) |
| Server → Client | `done` | `{"type":"done","message_id":"..."}` | Turn complete |
| Server → Client | `title_updated` | `{"type":"title_updated","title":"..."}` | Auto-generated title (first turn only) |
| Server → Client | `error` | `{"type":"error","message":"..."}` | Error |

---

## Voice Model File Layout

Files produced by `voice-cloning-service` (Project 1) and stored here after import:

```
storage/voice_models/
└── {user_id}/
    └── {voice_id}/
        ├── {voice_id}_gpt.ckpt      # GPT model weights
        ├── {voice_id}_sovits.pth    # SoVITS model weights
        ├── metadata.json            # Name, language, training params
        └── reference.wav           # Reference audio (required for inference)
```

Required pretrained models (shared, not per-voice):

```
storage/pretrained_models/GPT-SoVITS/
├── chinese-hubert-base/
└── chinese-roberta-wwm-ext-large/
```

---

## Database Schema

```
users ──┬── voice_models  (voice_models.user_id → users.id)
        └── conversations (conversations.user_id → users.id)
                │
                ├── voice_model_id → voice_models.id
                └── messages      (messages.conversation_id → conversations.id)
```

**Key tables:**

| Table | Primary columns |
|-------|----------------|
| `users` | `id`, `email`, `username`, `hashed_password`, `is_active` |
| `voice_models` | `id`, `voice_id` (UUID), `voice_name`, `language`, `gpt_model_path`, `sovits_model_path`, `reference_wav_path`, `user_id` |
| `conversations` | `id`, `title`, `user_id`, `voice_model_id` |
| `messages` | `id`, `conversation_id`, `role` (user/assistant), `content`, `audio_url` |

---

## Production Deployment

```
Internet
    │
    ▼
[Nginx]  :80 / :443
    ├── /          ──────── frontend static files
    ├── /api/*     ──────── FastAPI backend :8000
    └── /ws/*      ──────── FastAPI backend :8000  (WebSocket upgrade)

[Docker Compose services]
    ├── frontend   (nginx + built React)
    ├── backend    (conda + PyTorch + FastAPI)
    ├── postgres   (PostgreSQL 14)
    └── redis      (Redis 7)
```

See [docs/DEPLOY.md](docs/DEPLOY.md) for the full production deployment guide.
