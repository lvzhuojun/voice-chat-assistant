/**
 * 对话管理 API
 */

import client from './client'
import type { Conversation, Message } from '@/types'

/** 获取对话列表 */
export const listConversations = () => client.get<Conversation[]>('/conversations')

/** 创建对话 */
export const createConversation = (data: {
  title?: string
  voice_model_id?: number | null
}) => client.post<Conversation>('/conversations', data)

/** 获取对话消息列表 */
export const getMessages = (conversationId: number) =>
  client.get<Message[]>(`/conversations/${conversationId}/messages`)

/** 删除对话 */
export const deleteConversation = (id: number) =>
  client.delete<{ message: string }>(`/conversations/${id}`)

/** 更新对话标题 */
export const updateConversationTitle = (id: number, title: string) =>
  client.patch<Conversation>(`/conversations/${id}/title`, { title })
