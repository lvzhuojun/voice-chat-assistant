/**
 * 音色管理 API
 * Voice model management API.
 */

import client from './client'
import type { VoiceModel, VoiceModelDetail } from '@/types'

/** 获取音色列表 / Fetch the list of voice models */
export const listVoices = () => client.get<VoiceModel[]>('/voices')

/** 获取音色详情 / Fetch voice model details */
export const getVoice = (id: number) => client.get<VoiceModelDetail>(`/voices/${id}`)

/** 上传导入音色 ZIP（带进度回调，engine 默认 gptsovits） / Import a voice model from a ZIP file (with progress callback; engine defaults to gptsovits) */
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

/** 删除音色 / Delete a voice model */
export const deleteVoice = (id: number) =>
  client.delete<{ message: string }>(`/voices/${id}`)

/** 设置当前音色 / Select the active voice model */
export const selectVoice = (id: number) =>
  client.post<{ message: string; voice_id: string }>(`/voices/${id}/select`)

/**
 * 获取当前选中音色（未设置时后端返回 null，不会出现 404）
 * Fetch the currently selected voice model (returns null from the backend when none is set, no 404).
 */
export const getCurrentVoice = () =>
  client.get<VoiceModel | null>('/voices/current/info')
