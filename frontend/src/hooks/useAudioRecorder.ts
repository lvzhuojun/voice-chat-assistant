/**
 * 音频录制 Hook
 * 使用 MediaRecorder API，输出 WebM 格式
 */

import { useState, useRef, useCallback } from 'react'
import type { RecordingState } from '@/types'

interface UseAudioRecorderReturn {
  recordingState: RecordingState
  startRecording: () => Promise<void>
  stopRecording: () => Promise<Blob | null>
  error: string | null
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [recordingState, setRecordingState] = useState<RecordingState>('idle')
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)

  /** 开始录音 */
  const startRecording = useCallback(async () => {
    setError(null)
    try {
      // 请求麦克风权限
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,    // 回声消除
          noiseSuppression: true,    // 噪声抑制
          sampleRate: 16000,         // 16kHz（Whisper 最优采样率）
        },
      })
      streamRef.current = stream
      chunksRef.current = []

      // 创建 MediaRecorder（WebM 格式，浏览器默认支持）
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder

      // 收集音频块
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      // 每 250ms 触发一次 ondataavailable（实时收集）
      recorder.start(250)
      setRecordingState('recording')
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message.includes('Permission denied')
            ? '麦克风权限被拒绝，请在浏览器设置中允许麦克风访问'
            : err.message
          : '无法访问麦克风'
      setError(msg)
      setRecordingState('idle')
    }
  }, [])

  /** 停止录音，返回音频 Blob */
  const stopRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current
      if (!recorder || recorder.state === 'inactive') {
        resolve(null)
        return
      }

      setRecordingState('processing')

      recorder.onstop = () => {
        // 合并所有音频块
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        chunksRef.current = []

        // 释放麦克风资源
        streamRef.current?.getTracks().forEach((t) => t.stop())
        streamRef.current = null

        setRecordingState('idle')
        resolve(blob)
      }

      recorder.stop()
    })
  }, [])

  return { recordingState, startRecording, stopRecording, error }
}
