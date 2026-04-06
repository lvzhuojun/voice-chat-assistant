/**
 * 对话状态 Store（Zustand）
 * Conversation state store (Zustand).
 */

import { create } from 'zustand'
import type { Conversation, Message } from '@/types'

interface ChatState {
  conversations: Conversation[]
  activeConversationId: number | null
  messages: Message[]
  streamingText: string          // LLM 流式文字（打字机效果）/ LLM streaming text (typewriter effect)
  isProcessing: boolean          // 正在处理（STT/LLM/TTS）/ Currently processing (STT/LLM/TTS)
  pendingAudioChunks: string[]   // 等待播放的 base64 音频块 / Pending base64 audio chunks awaiting playback
  messageAudioData: Record<number, string[]>  // messageId → base64 WAV 块列表（供重播）/ messageId → list of base64 WAV chunks (for replay)

  setConversations: (convs: Conversation[]) => void
  addConversation: (conv: Conversation) => void
  removeConversation: (id: number) => void
  setActiveConversation: (id: number | null) => void
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  appendStreamingText: (text: string) => void
  clearStreamingText: () => void
  setProcessing: (processing: boolean) => void
  addAudioChunk: (chunk: string) => void
  clearAudioChunks: () => void
  setMessageAudio: (messageId: number, data: string[]) => void
  updateConversationTitle: (id: number, title: string) => void
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  streamingText: '',
  isProcessing: false,
  pendingAudioChunks: [],
  messageAudioData: {},

  setConversations: (conversations) => set({ conversations }),
  addConversation: (conv) =>
    set((state) => ({ conversations: [conv, ...state.conversations] })),
  removeConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    })),
  setActiveConversation: (id) =>
    set({
      activeConversationId: id,
      isProcessing: false,
      streamingText: '',
      pendingAudioChunks: [],
      messages: [],
    }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  appendStreamingText: (text) =>
    set((state) => ({ streamingText: state.streamingText + text })),
  clearStreamingText: () => set({ streamingText: '' }),
  setProcessing: (processing) => set({ isProcessing: processing }),
  addAudioChunk: (chunk) =>
    set((state) => ({
      pendingAudioChunks: [...state.pendingAudioChunks, chunk],
    })),
  clearAudioChunks: () => set({ pendingAudioChunks: [] }),
  setMessageAudio: (messageId, data) =>
    set((state) => ({
      messageAudioData: { ...state.messageAudioData, [messageId]: data },
    })),
  updateConversationTitle: (id, title) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    })),
}))
