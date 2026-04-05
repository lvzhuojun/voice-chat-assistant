/**
 * 音频播放条组件
 * 显示在 AI 消息下方，支持播放/暂停和进度显示
 * 支持多段 base64 WAV 顺序播放（分句 TTS 场景）
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Play, Pause, Volume2 } from 'lucide-react'

interface AudioPlayerProps {
  /** base64 编码的 WAV 音频数据块列表 */
  audioData?: string[]
}

export default function AudioPlayer({ audioData }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [totalDuration, setTotalDuration] = useState(0)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const blobUrlsRef = useRef<string[]>([])
  const chunkDurationsRef = useRef<number[]>([])
  const currentIndexRef = useRef(0)
  const elapsedBeforeCurrentRef = useRef(0)  // 当前块之前所有块的累计时长
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  /** 停止当前播放并清理 Audio 元素 */
  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current = null
    }
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current)
      progressTimerRef.current = null
    }
  }, [])

  // 当 audioData 变化时重建 blob URL 列表
  useEffect(() => {
    stopAudio()
    setIsPlaying(false)
    setProgress(0)
    setTotalDuration(0)

    // 释放旧的 blob URL
    blobUrlsRef.current.forEach((u) => URL.revokeObjectURL(u))
    blobUrlsRef.current = []
    chunkDurationsRef.current = []
    currentIndexRef.current = 0
    elapsedBeforeCurrentRef.current = 0

    if (!audioData?.length) return

    // 解码所有块为 blob URL
    const urls: string[] = []
    for (const data of audioData) {
      try {
        const binary = atob(data)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
        const blob = new Blob([bytes], { type: 'audio/wav' })
        urls.push(URL.createObjectURL(blob))
      } catch {
        urls.push('')
      }
    }
    blobUrlsRef.current = urls

    // 预加载各块时长以计算总时长
    let loaded = 0
    const durations = new Array<number>(urls.length).fill(0)
    urls.forEach((url, i) => {
      if (!url) { loaded++; return }
      const tmp = new Audio(url)
      tmp.onloadedmetadata = () => {
        durations[i] = tmp.duration || 0
        loaded++
        if (loaded === urls.length) {
          chunkDurationsRef.current = durations
          setTotalDuration(durations.reduce((a, b) => a + b, 0))
        }
      }
      tmp.onerror = () => { loaded++; if (loaded === urls.length) chunkDurationsRef.current = durations }
    })

    return () => {
      stopAudio()
      blobUrlsRef.current.forEach((u) => URL.revokeObjectURL(u))
      blobUrlsRef.current = []
    }
  }, [audioData, stopAudio])

  /** 从指定块索引开始播放 */
  const playFrom = useCallback((index: number) => {
    stopAudio()

    if (index >= blobUrlsRef.current.length) {
      setIsPlaying(false)
      setProgress(0)
      currentIndexRef.current = 0
      elapsedBeforeCurrentRef.current = 0
      return
    }

    const url = blobUrlsRef.current[index]
    if (!url) { playFrom(index + 1); return }

    const audio = new Audio(url)
    audioRef.current = audio
    currentIndexRef.current = index

    // 计算此块之前的累计时长
    const elapsed = chunkDurationsRef.current.slice(0, index).reduce((a, b) => a + b, 0)
    elapsedBeforeCurrentRef.current = elapsed

    audio.play().catch(() => {})

    // 定时更新进度条
    progressTimerRef.current = setInterval(() => {
      const total = totalDuration || chunkDurationsRef.current.reduce((a, b) => a + b, 0)
      if (!total) return
      const current = elapsedBeforeCurrentRef.current + (audioRef.current?.currentTime ?? 0)
      setProgress((current / total) * 100)
    }, 100)

    audio.onended = () => {
      if (progressTimerRef.current) clearInterval(progressTimerRef.current)
      playFrom(index + 1)
    }
    audio.onerror = () => {
      if (progressTimerRef.current) clearInterval(progressTimerRef.current)
      playFrom(index + 1)
    }
  }, [stopAudio, totalDuration])

  const togglePlay = () => {
    if (isPlaying) {
      audioRef.current?.pause()
      if (progressTimerRef.current) clearInterval(progressTimerRef.current)
      setIsPlaying(false)
    } else {
      // 如果已播放完（currentIndex 越界），从头开始
      const idx = currentIndexRef.current < blobUrlsRef.current.length
        ? currentIndexRef.current
        : 0
      setIsPlaying(true)
      playFrom(idx)
    }
  }

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const total = totalDuration
    if (!total) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const targetTime = ratio * total

    // 找出目标时间所在的块
    let cumulative = 0
    for (let i = 0; i < chunkDurationsRef.current.length; i++) {
      cumulative += chunkDurationsRef.current[i]
      if (targetTime <= cumulative || i === chunkDurationsRef.current.length - 1) {
        const offsetInChunk = targetTime - (cumulative - chunkDurationsRef.current[i])
        if (isPlaying) {
          playFrom(i)
          setTimeout(() => {
            if (audioRef.current) audioRef.current.currentTime = offsetInChunk
          }, 50)
        } else {
          currentIndexRef.current = i
          elapsedBeforeCurrentRef.current = cumulative - chunkDurationsRef.current[i]
        }
        setProgress(ratio * 100)
        break
      }
    }
  }

  if (!audioData?.length) return null

  const formatTime = (s: number) => {
    if (!s || isNaN(s)) return '0:00'
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="flex items-center gap-2 mt-2 bg-white/5 rounded-lg px-3 py-2 max-w-xs">
      {/* 播放/暂停按钮 */}
      <button
        onClick={togglePlay}
        className="w-7 h-7 rounded-full bg-brand-purple/20 hover:bg-brand-purple/40 flex items-center justify-center transition-all duration-150 flex-shrink-0"
      >
        {isPlaying ? (
          <Pause className="w-3.5 h-3.5 text-brand-purple" />
        ) : (
          <Play className="w-3.5 h-3.5 text-brand-purple ml-0.5" />
        )}
      </button>

      {/* 进度条 */}
      <div
        className="flex-1 h-1.5 bg-white/10 rounded-full cursor-pointer overflow-hidden"
        onClick={handleSeek}
      >
        <div
          className="h-full bg-brand-gradient rounded-full transition-all duration-100"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* 时长 */}
      <div className="flex items-center gap-1 text-xs text-text-muted flex-shrink-0">
        <Volume2 className="w-3 h-3" />
        <span>{formatTime(totalDuration)}</span>
      </div>
    </div>
  )
}
