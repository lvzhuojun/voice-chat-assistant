/**
 * 音频播放条组件
 * 显示在 AI 消息下方，支持播放/暂停和进度显示
 */

import { useState, useRef, useEffect } from 'react'
import { Play, Pause, Volume2 } from 'lucide-react'

interface AudioPlayerProps {
  /** base64 编码的 WAV 音频数据 */
  audioData?: string
}

export default function AudioPlayer({ audioData }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  // 当 audioData 变化时创建音频元素
  useEffect(() => {
    if (!audioData) return

    // 清理旧的 blob URL
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current)
    }

    try {
      const binary = atob(audioData)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
      }
      const blob = new Blob([bytes], { type: 'audio/wav' })
      const url = URL.createObjectURL(blob)
      blobUrlRef.current = url

      const audio = new Audio(url)
      audioRef.current = audio

      audio.onloadedmetadata = () => setDuration(audio.duration)
      audio.ontimeupdate = () => {
        if (audio.duration) {
          setProgress((audio.currentTime / audio.duration) * 100)
        }
      }
      audio.onended = () => {
        setIsPlaying(false)
        setProgress(0)
      }
    } catch (err) {
      console.error('音频加载失败:', err)
    }

    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
      }
    }
  }, [audioData])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
      setIsPlaying(false)
    } else {
      audio.play()
      setIsPlaying(true)
    }
  }

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    audio.currentTime = ratio * audio.duration
    setProgress(ratio * 100)
  }

  if (!audioData) return null

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
        <span>{formatTime(duration)}</span>
      </div>
    </div>
  )
}
