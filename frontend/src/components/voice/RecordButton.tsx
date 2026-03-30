/**
 * 录音按钮组件
 * 默认：紫色渐变大圆形按钮
 * 录音中：红色脉冲动画 + 3 个同心圆声波扩散
 */

import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Loader2 } from 'lucide-react'
import type { RecordingState } from '@/types'

interface RecordButtonProps {
  state: RecordingState
  onMouseDown: () => void
  onMouseUp: () => void
  onTouchStart: () => void
  onTouchEnd: () => void
}

export default function RecordButton({
  state,
  onMouseDown,
  onMouseUp,
  onTouchStart,
  onTouchEnd,
}: RecordButtonProps) {
  const isRecording = state === 'recording'
  const isProcessing = state === 'processing'

  return (
    <div className="relative flex items-center justify-center">
      {/* 声波同心圆（录音时显示） */}
      <AnimatePresence>
        {isRecording && (
          <>
            {[1, 2, 3].map((i) => (
              <motion.div
                key={i}
                initial={{ scale: 1, opacity: 0.6 }}
                animate={{ scale: 2.5, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: 1.5,
                  delay: (i - 1) * 0.4,
                  repeat: Infinity,
                  ease: 'easeOut',
                }}
                className="absolute w-16 h-16 rounded-full border-2 border-red-400/60"
              />
            ))}
          </>
        )}
      </AnimatePresence>

      {/* 主按钮 */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        disabled={isProcessing}
        className={`relative z-10 w-16 h-16 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 select-none ${
          isProcessing
            ? 'bg-white/10 cursor-not-allowed'
            : isRecording
            ? 'bg-red-500 shadow-[0_0_24px_rgba(239,68,68,0.5)]'
            : 'bg-brand-gradient shadow-glow-purple cursor-pointer'
        }`}
      >
        {isProcessing ? (
          <Loader2 className="w-7 h-7 text-white/60 animate-spin" />
        ) : isRecording ? (
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 0.6, repeat: Infinity }}
          >
            <MicOff className="w-7 h-7 text-white" />
          </motion.div>
        ) : (
          <Mic className="w-7 h-7 text-white" />
        )}
      </motion.button>
    </div>
  )
}
