/**
 * 录音按钮组件
 * Recording button component
 * 默认：紫色渐变大圆形按钮
 * Default state: large circular button with purple gradient
 * 录音中：红色脉冲动画 + 3 个同心圆声波扩散
 * Recording state: red pulse animation with 3 concentric expanding ring waves
 */

import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Loader2 } from 'lucide-react'
import type { RecordingState } from '@/types'

interface RecordButtonProps {
  state: RecordingState
  audioLevel?: number     // 0~1，录音时实时音量（用于波形动画）/ 0–1, real-time audio level during recording (used for waveform animation)
  onMouseDown: () => void
  onMouseUp: () => void
  onTouchStart: () => void
  onTouchEnd: () => void
}

// 波形条的相对高度因子（中间高、两边低，形成山形轮廓）
// Relative height factors for waveform bars (taller in the middle, shorter on the sides — mountain silhouette)
const BAR_FACTORS = [0.45, 0.7, 1.0, 0.7, 0.45]

export default function RecordButton({
  state,
  audioLevel = 0,
  onMouseDown,
  onMouseUp,
  onTouchStart,
  onTouchEnd,
}: RecordButtonProps) {
  const isRecording = state === 'recording'
  const isProcessing = state === 'processing'

  return (
    <div className="relative flex items-center justify-center">
      {/* 声波同心圆（录音时显示）/ Concentric sound-wave rings (visible while recording) */}
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

      {/* 主按钮 / Main button */}
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
          /* 实时波形：5 根柱子随音量动态变高，最低 20% 最高 100%
             Real-time waveform: 5 bars that grow dynamically with volume, min 20% max 100% */
          <div className="flex items-end gap-[3px] h-7 pb-0.5">
            {BAR_FACTORS.map((factor, i) => {
              const heightPct = Math.round(
                Math.max(20, Math.min(100, audioLevel * 100 * factor * 1.8))
              )
              return (
                <div
                  key={i}
                  className="w-[3px] rounded-full bg-white transition-all"
                  style={{
                    height: `${heightPct}%`,
                    transitionDuration: '60ms',
                  }}
                />
              )
            })}
          </div>
        ) : (
          <Mic className="w-7 h-7 text-white" />
        )}
      </motion.button>
    </div>
  )
}
