/**
 * 音色管理 API
 */

import client from './client'
import type { VoiceModel, VoiceModelDetail } from '@/types'

/** 获取音色列表 */
export const listVoices = () => client.get<VoiceModel[]>('/voices')

/** 获取音色详情 */
export const getVoice = (id: number) => client.get<VoiceModelDetail>(`/voices/${id}`)

/** 上传导入音色 ZIP（带进度回调，engine 默认 gptsovits） */
export const importVoice = (
  file: File,
  onProgress?: (percent: number) => void,
  engine: 'gptsovits' | 'cosyvoice2' = 'gptsovits',
) => {
  const form = new FormData()
  form.append('file', file)
  return client.post<VoiceModelDetail>(`/voices/import?engine=${engine}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
}

/** 删除音色 */
export const deleteVoice = (id: number) =>
  client.delete<{ message: string }>(`/voices/${id}`)

/** 设置当前音色 */
export const selectVoice = (id: number) =>
  client.post<{ message: string; voice_id: string }>(`/voices/${id}/select`)

/** 获取当前选中音色（未设置时后端返回 null，不会出现 404） */
export const getCurrentVoice = () =>
  client.get<VoiceModel | null>('/voices/current/info')
