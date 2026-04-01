# API Reference

Base URL: `http://localhost:8000`

All authenticated endpoints require the header:

```
Authorization: Bearer <jwt_token>
```

Interactive docs are available at **http://localhost:8000/docs** (Swagger UI).

---

## Table of Contents

- [Authentication](#authentication)
  - [POST /api/auth/register](#post-apiauthregister)
  - [POST /api/auth/login](#post-apiauthlogin)
  - [GET /api/auth/me](#get-apiauthme)
- [Voice Management](#voice-management)
  - [POST /api/voices/import](#post-apivoicesimport)
  - [GET /api/voices](#get-apivoices)
  - [GET /api/voices/current/info](#get-apivoicescurrentinfo)
  - [GET /api/voices/{id}](#get-apivoicesid)
  - [DELETE /api/voices/{id}](#delete-apivoicesid)
  - [POST /api/voices/{id}/select](#post-apivoicesidselect)
  - [POST /api/voices/{id}/test](#post-apivoicesidtest)
- [Conversations](#conversations)
  - [GET /api/conversations](#get-apiconversations)
  - [POST /api/conversations](#post-apiconversations)
  - [DELETE /api/conversations/{id}](#delete-apiconversationsid)
  - [GET /api/conversations/{id}/messages](#get-apiconversationsidmessages)
- [WebSocket](#websocket)
  - [WS /ws/chat/{conversation_id}](#ws-wschatconversation_id)
- [System](#system)
  - [GET /api/health](#get-apihealth)

---

## Authentication

### POST /api/auth/register

Register a new user.

**Request body** (`application/json`):

```json
{
  "email": "user@example.com",
  "password": "yourpassword",
  "username": "Alice"
}
```

**Response** `201 Created`:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "Alice",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400 Bad Request` | Email already registered |
| `422 Unprocessable Entity` | Validation error (invalid email, short password, etc.) |

---

### POST /api/auth/login

Log in with email and password.

**Request body** (`application/json`):

```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response** `200 OK`: same shape as `/register`.

**Error responses:**

| Status | Condition |
|--------|-----------|
| `401 Unauthorized` | Wrong email or password |

---

### GET /api/auth/me

Get the current authenticated user. **Requires auth.**

**Response** `200 OK`:

```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "Alice",
  "created_at": "2024-01-01T00:00:00Z",
  "is_active": true
}
```

---

## Voice Management

### POST /api/voices/import

Upload a voice ZIP package. **Requires auth.**

The ZIP must contain these four files at the root level (no subdirectories):

```
<voice_id>_gpt.ckpt
<voice_id>_sovits.pth
metadata.json
reference.wav
```

**Request** `multipart/form-data`:

| Field | Type | Description |
|-------|------|-------------|
| `file` | File (`.zip`) | Voice model archive |

**Response** `201 Created`:

```json
{
  "id": 1,
  "voice_id": "550e8400-e29b-41d4-a716-446655440000",
  "voice_name": "My Voice",
  "language": "zh",
  "gpt_model_path": "storage/voice_models/1/550e8400-.../..._gpt.ckpt",
  "sovits_model_path": "storage/voice_models/1/550e8400-.../..._sovits.pth",
  "reference_wav_path": "storage/voice_models/1/550e8400-.../reference.wav",
  "metadata_json": { "..." : "..." },
  "created_at": "2024-01-01T00:00:00Z",
  "is_active": true
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400 Bad Request` | ZIP missing required files, or `base_model_version` is not `GPT-SoVITS v2` |
| `409 Conflict` | Voice ID already imported for this user |

---

### GET /api/voices

List all voice models belonging to the current user. **Requires auth.**

**Response** `200 OK`:

```json
[
  {
    "id": 1,
    "voice_id": "550e8400-...",
    "voice_name": "My Voice",
    "language": "zh",
    "created_at": "2024-01-01T00:00:00Z",
    "is_active": true,
    "metadata_json": { "..." : "..." }
  }
]
```

---

### GET /api/voices/current/info

Get the voice currently selected by the user (read from Redis). Falls back to the most recently imported voice if none is selected. **Requires auth.**

**Response** `200 OK`: same shape as a single item in `GET /api/voices`.

**Error responses:**

| Status | Condition |
|--------|-----------|
| `404 Not Found` | User has no imported voices |

---

### GET /api/voices/{id}

Get full details of a single voice model. **Requires auth.**

`{id}` is the integer database ID returned by the import endpoint.

**Response** `200 OK`: same shape as `POST /api/voices/import` response.

**Error responses:**

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Voice not found or belongs to another user |

---

### DELETE /api/voices/{id}

Delete a voice model (removes database record and model files). **Requires auth.**

**Response** `200 OK`:

```json
{ "message": "音色已删除" }
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Voice not found or belongs to another user |

---

### POST /api/voices/{id}/select

Set the active voice for the current user (stored in Redis). **Requires auth.**

**Response** `200 OK`:

```json
{ "message": "音色已设置", "voice_id": "550e8400-..." }
```

---

### POST /api/voices/{id}/test

Synthesize a short test sentence with the specified voice and return a WAV file. **Requires auth.**

**Response** `200 OK`: `audio/wav` binary.

**Error responses:**

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Voice not found |
| `503 Service Unavailable` | TTS engine not ready |

---

## Conversations

### GET /api/conversations

List conversations for the current user, newest first. **Requires auth.**

**Response** `200 OK`:

```json
[
  {
    "id": 1,
    "title": "New conversation",
    "voice_model_id": 1,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:01:00Z",
    "message_count": 5
  }
]
```

---

### POST /api/conversations

Create a new conversation. **Requires auth.**

**Request body** (`application/json`):

```json
{
  "title": "New conversation",
  "voice_model_id": 1
}
```

**Response** `201 Created`: same shape as one item in `GET /api/conversations`.

---

### DELETE /api/conversations/{id}

Delete a conversation and all its messages. **Requires auth.**

**Response** `200 OK`:

```json
{ "message": "对话已删除" }
```

---

### GET /api/conversations/{id}/messages

List all messages in a conversation. **Requires auth.**

**Response** `200 OK`:

```json
[
  {
    "id": 1,
    "conversation_id": 1,
    "role": "user",
    "content": "你好",
    "audio_url": null,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": 2,
    "conversation_id": 1,
    "role": "assistant",
    "content": "你好！有什么可以帮助你的？",
    "audio_url": "/api/audio/abc123.wav",
    "created_at": "2024-01-01T00:00:01Z"
  }
]
```

`role` is either `"user"` or `"assistant"`.

---

## WebSocket

### WS /ws/chat/{conversation\_id}

Full-duplex voice conversation channel.

**Connection URL:**

```
ws://localhost:8000/ws/chat/{conversation_id}?token={jwt_token}
```

The JWT is passed as a query parameter because browser `WebSocket` does not support custom headers.

#### Client → Server

| Frame type | Format | Description |
|------------|--------|-------------|
| Binary | raw bytes | WebM or WAV audio data |
| Text | `{"type":"text","content":"..."}` | Direct text input (skips STT) |

#### Server → Client

| `type` | Full message | Description |
|--------|-------------|-------------|
| `transcript` | `{"type":"transcript","text":"..."}` | STT recognition result |
| `llm_chunk` | `{"type":"llm_chunk","text":"..."}` | One LLM streaming token |
| `audio_chunk` | `{"type":"audio_chunk","data":"<base64>"}` | One TTS audio chunk |
| `done` | `{"type":"done","message_id":"..."}` | Turn complete, message persisted |
| `error` | `{"type":"error","message":"..."}` | Error during processing |

#### Typical turn sequence

```
Client  ──[binary audio]──▶  Server
Server  ◀──transcript──────  Server  (after STT)
Server  ◀──llm_chunk × N───  Server  (LLM streaming)
Server  ◀──audio_chunk × N─  Server  (TTS streaming)
Server  ◀──done────────────  Server  (turn finished)
```

---

## System

### GET /api/health

Health check with system status. No authentication required.

**Response** `200 OK`:

```json
{
  "status": "ok",
  "gpu": {
    "available": true,
    "name": "NVIDIA GeForce RTX 5060",
    "memory_total_mb": 8192,
    "memory_used_mb": 2048
  },
  "whisper_loaded": true,
  "tts_models_loaded": 1,
  "voice_count": 3
}
```

| Field | Description |
|-------|-------------|
| `status` | `"ok"` or `"degraded"` |
| `gpu.available` | Whether CUDA is available |
| `whisper_loaded` | Whether faster-whisper model is in memory |
| `tts_models_loaded` | Number of GPT-SoVITS models currently in LRU cache |
| `voice_count` | Total voice models in the database |
