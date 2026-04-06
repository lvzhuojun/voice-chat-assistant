/**
 * 音频录制 Hook
 * Audio recording hook.
 * 使用 MediaRecorder API，输出 WebM 格式
 * Uses the MediaRecorder API and outputs WebM format.
 * 支持 VAD（语音活动检测）：检测到持续静音后自动停止录音
 * Supports VAD (Voice Activity Detection): auto-stops recording after sustained silence.
 */

import { useState, useRef, useCallback } from 'react'
import type { RecordingState } from '@/types'

// ── VAD 参数 / VAD parameters ────────────────────────────────────
/** 判定为"有声"的音量阈值（0~1） / Volume threshold for speech detection (0–1) */
const VAD_SPEECH_THRESHOLD = 0.06
/** 说话后静音持续多久自动停止（ms） / Duration of silence after speech before auto-stop (ms) */
const VAD_SILENCE_MS = 1500
/**
 * 触发 VAD 前至少需要说话的最短时长（ms），避免环境噪音误触发
 * Minimum speech duration before VAD can trigger auto-stop (ms), prevents false triggers from ambient noise.
 */
const VAD_MIN_SPEECH_MS = 400

interface UseAudioRecorderOptions {
  /** VAD 自动停止后的回调，接收录制好的音频 Blob / Callback after VAD auto-stop, receives the recorded audio Blob */
  onAutoStop?: (blob: Blob) => void
}

interface UseAudioRecorderReturn {
  recordingState: RecordingState
  audioLevel: number       // 0~1，录音时的实时音量（用于波形动画）/ Real-time audio level during recording, 0–1 (used for waveform animation)
  startRecording: () => Promise<void>
  stopRecording: () => Promise<Blob | null>
  error: string | null
}

export function useAudioRecorder(
  { onAutoStop }: UseAudioRecorderOptions = {},
): UseAudioRecorderReturn {
  const [recordingState, setRecordingState] = useState<RecordingState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [audioLevel, setAudioLevel] = useState(0)

  // 媒体相关 refs / Media-related refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animFrameRef = useRef<number | null>(null)

  // VAD 状态 refs / VAD state refs
  const hasSpeechRef = useRef(false)
  const speechStartTimeRef = useRef<number | null>(null)
  const silenceStartTimeRef = useRef<number | null>(null)
  const isAutoStoppingRef = useRef(false)

  // 始终持有最新的 onAutoStop 回调，避免 stale closure
  // Always hold the latest onAutoStop callback to avoid stale closures
  const onAutoStopRef = useRef(onAutoStop)
  onAutoStopRef.current = onAutoStop

  /**
   * 内部停止并收集音频的核心逻辑。
   * Core logic for stopping recording and collecting the audio blob.
   * stopRecording（手动）和 VAD 自动停止都调用此函数，确保逻辑一致。
   * Called by both manual stopRecording and VAD auto-stop to ensure consistent behavior.
   */
  const _stopAndCollect = useCallback((onDone: (blob: Blob | null) => void) => {
    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state === 'inactive') {
      onDone(null)
      return
    }

    setRecordingState('processing')

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      chunksRef.current = []

      // 停止波形动画 / Stop waveform animation
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
      // 释放 AudioContext / Release AudioContext
      audioContextRef.current?.close()
      audioContextRef.current = null
      analyserRef.current = null
      setAudioLevel(0)

      // 释放麦克风 / Release microphone tracks
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null

      // 重置 VAD 状态 / Reset VAD state
      hasSpeechRef.current = false
      speechStartTimeRef.current = null
      silenceStartTimeRef.current = null
      isAutoStoppingRef.current = false

      setRecordingState('idle')
      onDone(blob)
    }

    recorder.stop()
  }, [])

  /** 开始录音 / Start recording */
  const startRecording = useCallback(async () => {
    setError(null)

    // 重置 VAD / Reset VAD state
    hasSpeechRef.current = false
    speechStartTimeRef.current = null
    silenceStartTimeRef.current = null
    isAutoStoppingRef.current = false

    try {
      // 请求麦克风权限 / Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      })
      streamRef.current = stream
      chunksRef.current = []

      // 建立音频分析器 / Set up audio analyser
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 128
      source.connect(analyser)
      audioContextRef.current = audioCtx
      analyserRef.current = analyser

      const freqData = new Uint8Array(analyser.frequencyBinCount)

      const updateLevel = () => {
        analyser.getByteFrequencyData(freqData)
        const avg = freqData.reduce((a, b) => a + b, 0) / freqData.length
        const level = avg / 255
        setAudioLevel(level)

        // ── VAD 逻辑 / VAD logic ──────────────────────────────
        const now = Date.now()

        if (level >= VAD_SPEECH_THRESHOLD) {
          // 有声音：记录说话开始时间，清除静音计时
          // Speech detected: record speech start time and clear silence timer
          if (!hasSpeechRef.current) {
            hasSpeechRef.current = true
            speechStartTimeRef.current = now
          }
          silenceStartTimeRef.current = null
        } else if (hasSpeechRef.current && speechStartTimeRef.current) {
          // 说话后出现静音，且已说话足够长
          // Silence after speech, and speech was long enough
          const speechDuration = now - speechStartTimeRef.current
          if (speechDuration >= VAD_MIN_SPEECH_MS) {
            if (silenceStartTimeRef.current === null) {
              silenceStartTimeRef.current = now
            } else if (
              now - silenceStartTimeRef.current >= VAD_SILENCE_MS &&
              !isAutoStoppingRef.current
            ) {
              // 静音超过阈值 → 自动停止 / Silence exceeded threshold → auto-stop
              isAutoStoppingRef.current = true
              _stopAndCollect((blob) => {
                if (blob && blob.size > 1000) {
                  onAutoStopRef.current?.(blob)
                }
              })
              return  // 退出 RAF 循环 / Exit the requestAnimationFrame loop
            }
          }
        }

        animFrameRef.current = requestAnimationFrame(updateLevel)
      }
      updateLevel()

      // 创建 MediaRecorder / Create MediaRecorder
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.start(250)
      setRecordingState('recording')
    } catch (err: unknown) {
      // 清理部分初始化的音频资源，避免泄漏
      // Clean up partially initialized audio resources to prevent leaks
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
      audioContextRef.current?.close()
      audioContextRef.current = null
      analyserRef.current = null
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      setAudioLevel(0)

      const msg =
        err instanceof Error
          ? err.message.includes('Permission denied') || err.message.includes('NotAllowedError')
            ? '麦克风权限被拒绝，请在浏览器设置中允许麦克风访问'
            : err.message
          : '无法访问麦克风'
      setError(msg)
      setRecordingState('idle')
    }
  }, [_stopAndCollect])

  /** 手动停止录音，返回音频 Blob / Manually stop recording and return the audio Blob */
  const stopRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => _stopAndCollect(resolve))
  }, [_stopAndCollect])

  return { recordingState, audioLevel, startRecording, stopRecording, error }
}
