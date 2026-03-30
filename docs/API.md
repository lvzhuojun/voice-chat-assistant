# API 文档

Base URL: `http://localhost:8000`

所有需要认证的接口在 Header 中携带：`Authorization: Bearer {jwt_token}`

---

## 认证接口

### POST /api/auth/register

注册新用户。

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword",
  "username": "用户名"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "用户名",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### POST /api/auth/login

用户登录。

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response:** 同注册接口

---

### GET /api/auth/me

获取当前用户信息。需要认证。

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "用户名",
  "created_at": "2024-01-01T00:00:00Z",
  "is_active": true
}
```

---

## 音色管理接口

### POST /api/voices/import

上传音色 ZIP 包（含 _gpt.ckpt、_sovits.pth、metadata.json、reference.wav）。需要认证。

**Request:** `multipart/form-data`
- `file`: ZIP 文件

**Response:**
```json
{
  "id": 1,
  "voice_id": "550e8400-...",
  "voice_name": "My Voice",
  "language": "zh",
  "gpt_model_path": "storage/voice_models/1/550e8400.../..._gpt.ckpt",
  "sovits_model_path": "storage/voice_models/1/550e8400.../..._sovits.pth",
  "reference_wav_path": "storage/voice_models/1/550e8400.../reference.wav",
  "metadata_json": {...},
  "created_at": "2024-01-01T00:00:00Z",
  "is_active": true
}
```

---

### GET /api/voices

获取当前用户的音色列表。需要认证。

**Response:**
```json
[
  {
    "id": 1,
    "voice_id": "...",
    "voice_name": "My Voice",
    "language": "zh",
    "created_at": "2024-01-01T00:00:00Z",
    "is_active": true,
    "metadata_json": {...}
  }
]
```

---

### GET /api/voices/{id}

获取音色详情。需要认证。

---

### DELETE /api/voices/{id}

删除音色（删除文件和数据库记录）。需要认证。

**Response:**
```json
{"message": "音色已删除"}
```

---

### POST /api/voices/{id}/select

设置当前使用的音色（存入 Redis）。需要认证。

**Response:**
```json
{"message": "音色已设置", "voice_id": "..."}
```

---

## 对话接口

### GET /api/conversations

获取当前用户的对话列表。需要认证。

**Response:**
```json
[
  {
    "id": 1,
    "title": "新对话",
    "voice_model_id": 1,
    "created_at": "...",
    "updated_at": "...",
    "message_count": 5
  }
]
```

---

### POST /api/conversations

创建新对话。需要认证。

**Request Body:**
```json
{
  "title": "新对话",
  "voice_model_id": 1
}
```

---

### GET /api/conversations/{id}/messages

获取对话消息列表。需要认证。

**Response:**
```json
[
  {
    "id": 1,
    "conversation_id": 1,
    "role": "user",
    "content": "你好",
    "audio_url": null,
    "created_at": "..."
  },
  {
    "id": 2,
    "conversation_id": 1,
    "role": "assistant",
    "content": "你好！有什么可以帮助你的？",
    "audio_url": "/api/audio/xxx.wav",
    "created_at": "..."
  }
]
```

---

### DELETE /api/conversations/{id}

删除对话及其所有消息。需要认证。

---

## WebSocket

### WS /ws/chat/{conversation_id}?token={jwt}

全双工语音对话。

**客户端 → 服务端：**

| 类型 | 格式 | 说明 |
|------|------|------|
| 音频 | 二进制帧 | WebM/WAV 音频数据 |
| 文字 | `{"type":"text","content":"..."}` | 文字输入 |

**服务端 → 客户端：**

| type | 数据 | 说明 |
|------|------|------|
| `transcript` | `{"type":"transcript","text":"..."}` | STT 识别结果 |
| `llm_chunk` | `{"type":"llm_chunk","text":"..."}` | LLM 流式文字 |
| `audio_chunk` | `{"type":"audio_chunk","data":"base64..."}` | TTS 音频块 |
| `done` | `{"type":"done","message_id":"..."}` | 本轮完成 |
| `error` | `{"type":"error","message":"..."}` | 错误信息 |

---

## 系统接口

### GET /api/health

健康检查，含系统状态信息。

**Response:**
```json
{
  "status": "ok",
  "gpu": {
    "available": true,
    "name": "NVIDIA GeForce RTX 5060",
    "memory_total": 8192,
    "memory_used": 2048
  },
  "whisper_loaded": true,
  "tts_models_loaded": 1,
  "voice_count": 3
}
```
