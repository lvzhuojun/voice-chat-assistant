/**
 * 全局 TypeScript 类型定义
 * Global TypeScript type definitions.
 */

// ─────────────────────────────────────────────
// 用户相关 / User-related
// ─────────────────────────────────────────────

/** 用户信息 / User information */
export interface User {
  id: number
  email: string
  username: string
  created_at: string
  is_active: boolean
}

/** 登录/注册响应 / Login / register response */
export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// ─────────────────────────────────────────────
// 音色相关 / Voice model-related
// ─────────────────────────────────────────────

/** TTS 推理引擎类型 / TTS inference engine type */
export type TtsEngine = 'gptsovits' | 'cosyvoice2'

/** 音色列表项 / Voice model list item */
export interface VoiceModel {
  id: number
  voice_id: string
  voice_name: string
  language: string
  tts_engine: TtsEngine
  created_at: string
  is_active: boolean
  metadata_json?: Record<string, unknown>
}

/** 音色详情（含文件路径） / Voice model detail (includes file paths) */
export interface VoiceModelDetail extends VoiceModel {
  gpt_model_path: string
  sovits_model_path: string
  reference_wav_path: string
}

// ─────────────────────────────────────────────
// 对话相关 / Conversation-related
// ─────────────────────────────────────────────

/** 对话 / Conversation */
export interface Conversation {
  id: number
  title: string
  voice_model_id: number | null
  created_at: string
  updated_at: string
  message_count?: number
}

/** 消息角色 / Message role */
export type MessageRole = 'user' | 'assistant'

/** 消息 / Message */
export interface Message {
  id: number
  conversation_id: number
  role: MessageRole
  content: string
  audio_url?: string | null
  created_at: string
}

// ─────────────────────────────────────────────
// WebSocket 消息类型 / WebSocket message types
// ─────────────────────────────────────────────

/** WebSocket 服务端 → 客户端消息 / WebSocket server-to-client messages */
export type WsMessage =
  | { type: 'transcript'; text: string }
  | { type: 'llm_chunk'; text: string }
  | { type: 'audio_chunk'; data: string; seq?: number }  // base64 WAV，seq 为分句序号 / base64 WAV, seq is the sentence index
  | { type: 'done'; message_id: string }
  | { type: 'error'; message: string }
  | { type: 'title_updated'; title: string }  // 首轮后自动生成的对话标题 / Auto-generated conversation title after the first turn

/** WebSocket 客户端 → 服务端文字消息 / WebSocket client-to-server text message */
export interface WsTextMessage {
  type: 'text'
  content: string
}

// ─────────────────────────────────────────────
// UI 状态 / UI state
// ─────────────────────────────────────────────

/** 录音状态 / Recording state */
export type RecordingState = 'idle' | 'recording' | 'processing'

/** 上传状态 / Upload progress state */
export interface UploadProgress {
  filename: string
  progress: number   // 0-100
  status: 'uploading' | 'success' | 'error'
  error?: string
}
