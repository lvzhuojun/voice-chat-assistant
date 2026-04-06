/**
 * 全局 TypeScript 类型定义
 */

// ─────────────────────────────────────────────
// 用户相关
// ─────────────────────────────────────────────

/** 用户信息 */
export interface User {
  id: number
  email: string
  username: string
  created_at: string
  is_active: boolean
}

/** 登录/注册响应 */
export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// ─────────────────────────────────────────────
// 音色相关
// ─────────────────────────────────────────────

/** TTS 推理引擎类型 */
export type TtsEngine = 'gptsovits' | 'cosyvoice2'

/** 音色列表项 */
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

/** 音色详情（含文件路径） */
export interface VoiceModelDetail extends VoiceModel {
  gpt_model_path: string
  sovits_model_path: string
  reference_wav_path: string
}

// ─────────────────────────────────────────────
// 对话相关
// ─────────────────────────────────────────────

/** 对话 */
export interface Conversation {
  id: number
  title: string
  voice_model_id: number | null
  created_at: string
  updated_at: string
  message_count?: number
}

/** 消息角色 */
export type MessageRole = 'user' | 'assistant'

/** 消息 */
export interface Message {
  id: number
  conversation_id: number
  role: MessageRole
  content: string
  audio_url?: string | null
  created_at: string
}

// ─────────────────────────────────────────────
// WebSocket 消息类型
// ─────────────────────────────────────────────

/** WebSocket 服务端 → 客户端消息 */
export type WsMessage =
  | { type: 'transcript'; text: string }
  | { type: 'llm_chunk'; text: string }
  | { type: 'audio_chunk'; data: string; seq?: number }  // base64 WAV，seq 为分句序号
  | { type: 'done'; message_id: string }
  | { type: 'error'; message: string }
  | { type: 'title_updated'; title: string }  // 首轮后自动生成的对话标题

/** WebSocket 客户端 → 服务端文字消息 */
export interface WsTextMessage {
  type: 'text'
  content: string
}

// ─────────────────────────────────────────────
// UI 状态
// ─────────────────────────────────────────────

/** 录音状态 */
export type RecordingState = 'idle' | 'recording' | 'processing'

/** 上传状态 */
export interface UploadProgress {
  filename: string
  progress: number   // 0-100
  status: 'uploading' | 'success' | 'error'
  error?: string
}
