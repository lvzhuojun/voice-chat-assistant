/**
 * 消息气泡组件
 * 用户消息：右对齐+紫色渐变
 * AI消息：左对齐+磨砂玻璃+头像+音频播放条
 */

import { Mic } from 'lucide-react'
import { motion } from 'framer-motion'
import AudioPlayer from './AudioPlayer'
import type { Message } from '@/types'

interface MessageBubbleProps {
  message: Message
  audioData?: string  // base64 WAV（AI 消息专用）
}

export default function MessageBubble({ message, audioData }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.25 }}
        className="flex justify-end mb-4"
      >
        <div className="max-w-[88%] md:max-w-[70%]">
          <div className="bg-brand-gradient text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-glow-purple/30">
            {message.content}
          </div>
          <p className="text-right text-xs text-text-muted mt-1">
            {new Date(message.created_at).toLocaleTimeString('zh-CN', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
      className="flex gap-3 mb-4"
    >
      {/* AI 头像 */}
      <div className="w-8 h-8 rounded-xl bg-brand-gradient flex items-center justify-center flex-shrink-0 mt-1 shadow-glow-purple/20">
        <Mic className="w-4 h-4 text-white" />
      </div>

      <div className="max-w-[88%] md:max-w-[70%]">
        {/* 消息气泡 */}
        <div className="glass-card px-4 py-3 text-sm text-text-primary leading-relaxed rounded-2xl rounded-tl-sm">
          {message.content}
        </div>
        {/* 音频播放条 */}
        {audioData && <AudioPlayer audioData={audioData} />}
        <p className="text-xs text-text-muted mt-1">
          {new Date(message.created_at).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </motion.div>
  )
}

/** 流式 AI 消息（打字机光标动画） */
export function StreamingBubble({ text }: { text: string }) {
  if (!text) return null

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex gap-3 mb-4"
    >
      <div className="w-8 h-8 rounded-xl bg-brand-gradient flex items-center justify-center flex-shrink-0 mt-1">
        <Mic className="w-4 h-4 text-white" />
      </div>
      <div className="max-w-[88%] md:max-w-[70%]">
        <div className="glass-card px-4 py-3 text-sm text-text-primary leading-relaxed rounded-2xl rounded-tl-sm">
          {text}
          <span className="inline-block w-0.5 h-4 bg-brand-purple ml-0.5 animate-pulse" />
        </div>
      </div>
    </motion.div>
  )
}
