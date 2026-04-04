/**
 * 音色管理页面
 * 拖拽上传 ZIP + 卡片网格 + 选中发光边框 + 删除确认弹窗
 */

import { useEffect, useState, useCallback, forwardRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import {
  Mic,
  Trash2,
  CheckCircle2,
  Upload,
  Loader2,
  ArrowLeft,
  Globe,
  Calendar,
  Layers,
  AlertTriangle,
} from 'lucide-react'
import { useVoiceStore } from '@/store/voiceStore'
import * as voiceApi from '@/api/voices'
import type { VoiceModel, UploadProgress } from '@/types'

/** 删除确认弹窗 */
function DeleteConfirmDialog({
  voice,
  onConfirm,
  onCancel,
}: {
  voice: VoiceModel
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onCancel}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="glass-card p-6 max-w-sm mx-4 w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">删除音色</h3>
            <p className="text-sm text-text-secondary">此操作不可撤销</p>
          </div>
        </div>
        <p className="text-text-secondary text-sm mb-6">
          确认删除音色 <span className="text-text-primary font-medium">「{voice.voice_name}」</span>？
          相关模型文件将被永久删除。
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 rounded-xl border border-white/10 text-text-secondary hover:bg-white/5 transition-all duration-150 text-sm font-medium"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 py-2.5 rounded-xl bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 transition-all duration-150 text-sm font-medium"
          >
            确认删除
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

interface VoiceCardProps {
  voice: VoiceModel
  isSelected: boolean
  onSelect: () => void
  onDelete: () => void
}

/** 音色卡片（forwardRef 供 framer-motion AnimatePresence popLayout 测量） */
const VoiceCard = forwardRef<HTMLDivElement, VoiceCardProps>(
function VoiceCard({ voice, isSelected, onSelect, onDelete }, ref) {
  const metadata = voice.metadata_json as Record<string, unknown> | undefined
  const gptEpochs = metadata?.training_epochs_gpt as number | undefined
  const sovitsEpochs = metadata?.training_epochs_sovits as number | undefined

  return (
    <motion.div
      ref={ref}
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.2 }}
      className={`relative glass-card p-5 cursor-pointer transition-all duration-200 group ${
        isSelected
          ? 'border-brand-purple/60 shadow-glow-purple'
          : 'hover:border-white/20 hover:bg-white/[0.07]'
      }`}
      style={isSelected ? { boxShadow: '0 0 0 1px rgba(124,58,237,0.5), 0 0 24px rgba(124,58,237,0.2)' } : {}}
      onClick={onSelect}
    >
      {/* 选中标记 */}
      {isSelected && (
        <div className="absolute top-3 right-3">
          <CheckCircle2 className="w-5 h-5 text-brand-purple" />
        </div>
      )}

      {/* 删除按钮 */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        className="absolute top-3 right-3 w-7 h-7 rounded-lg bg-red-500/0 hover:bg-red-500/20 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-150"
        style={isSelected ? { display: 'none' } : {}}
      >
        <Trash2 className="w-3.5 h-3.5 text-red-400" />
      </button>

      {/* 图标 */}
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${
        isSelected ? 'bg-brand-gradient' : 'bg-white/10'
      }`}>
        <Mic className={`w-5 h-5 ${isSelected ? 'text-white' : 'text-text-secondary'}`} />
      </div>

      {/* 名称 */}
      <h3 className="font-semibold text-text-primary truncate mb-2">{voice.voice_name}</h3>

      {/* 标签行 */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <span className="inline-flex items-center gap-1 text-xs bg-white/10 text-text-secondary px-2 py-0.5 rounded-full">
          <Globe className="w-3 h-3" />
          {voice.language === 'zh' ? '中文' : voice.language === 'en' ? '英文' : voice.language}
        </span>
        <span className="inline-flex items-center gap-1 text-xs bg-brand-purple/10 text-brand-purple px-2 py-0.5 rounded-full">
          GPT-SoVITS v2
        </span>
      </div>

      {/* 模型信息 */}
      {(gptEpochs || sovitsEpochs) && (
        <div className="flex items-center gap-1 text-xs text-text-muted mb-2">
          <Layers className="w-3 h-3" />
          <span>GPT: {gptEpochs ?? '-'}轮 · SoVITS: {sovitsEpochs ?? '-'}轮</span>
        </div>
      )}

      {/* 创建时间 */}
      <div className="flex items-center gap-1 text-xs text-text-muted">
        <Calendar className="w-3 h-3" />
        <span>{new Date(voice.created_at).toLocaleDateString('zh-CN')}</span>
      </div>

      {/* 底部按钮 */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onSelect()
        }}
        className={`w-full mt-4 py-2 rounded-xl text-xs font-medium transition-all duration-150 ${
          isSelected
            ? 'bg-brand-gradient text-white'
            : 'bg-white/5 text-text-secondary hover:bg-white/10 hover:text-text-primary border border-white/10'
        }`}
      >
        {isSelected ? '✓ 当前使用' : '设为当前'}
      </button>
    </motion.div>
  )
})

export default function VoicePage() {
  const navigate = useNavigate()
  const { voices, currentVoice, setVoices, setCurrentVoice, addVoice, removeVoice, isLoading, setLoading } =
    useVoiceStore()

  const [deleteTarget, setDeleteTarget] = useState<VoiceModel | null>(null)
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null)
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null)

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // 加载音色列表
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [voicesRes, currentRes] = await Promise.allSettled([
          voiceApi.listVoices(),
          voiceApi.getCurrentVoice(),
        ])
        if (voicesRes.status === 'fulfilled') setVoices(voicesRes.value.data)
        if (currentRes.status === 'fulfilled') setCurrentVoice(currentRes.value.data)
      } catch {
        // 忽略
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [setVoices, setCurrentVoice, setLoading])

  // 处理文件上传
  const handleUpload = useCallback(async (file: File) => {
    setUploadProgress({ filename: file.name, progress: 0, status: 'uploading' })
    try {
      const res = await voiceApi.importVoice(file, (p) => {
        setUploadProgress((prev) => prev ? { ...prev, progress: p } : null)
      })
      setUploadProgress({ filename: file.name, progress: 100, status: 'success' })
      addVoice(res.data)

      // 若当前无选中音色，自动选择刚上传的音色
      if (!currentVoice) {
        try {
          await voiceApi.selectVoice(res.data.id)
          setCurrentVoice(res.data)
          showToast(`音色「${res.data.voice_name}」导入成功，已自动设为当前音色`)
        } catch {
          showToast(`音色「${res.data.voice_name}」导入成功`)
        }
      } else {
        showToast(`音色「${res.data.voice_name}」导入成功`)
      }

      setTimeout(() => setUploadProgress(null), 2000)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        '上传失败，请检查 ZIP 格式'
      setUploadProgress({ filename: file.name, progress: 0, status: 'error', error: msg })
      showToast(msg, 'error')
      setTimeout(() => setUploadProgress(null), 4000)
    }
  }, [addVoice, currentVoice, setCurrentVoice])

  // Dropzone 配置
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => files[0] && handleUpload(files[0]),
    accept: { 'application/zip': ['.zip'] },
    multiple: false,
    maxSize: 2 * 1024 * 1024 * 1024, // 2GB
  })

  // 选择音色
  const handleSelect = async (voice: VoiceModel) => {
    try {
      await voiceApi.selectVoice(voice.id)
      setCurrentVoice(voice)
      showToast(`已切换到音色「${voice.voice_name}」`)
    } catch {
      showToast('切换失败，请重试', 'error')
    }
  }

  // 删除音色
  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await voiceApi.deleteVoice(deleteTarget.id)
      removeVoice(deleteTarget.id)
      showToast(`音色「${deleteTarget.voice_name}」已删除`)
    } catch {
      showToast('删除失败，请重试', 'error')
    } finally {
      setDeleteTarget(null)
    }
  }

  return (
    <div className="min-h-screen" style={{ background: '#0a0a0f' }}>
      {/* 背景光晕 */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-purple/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-brand-blue/10 rounded-full blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-8">
        {/* 顶部导航 */}
        <div className="flex items-center gap-4 mb-8">
          <button
            onClick={() => navigate('/chat')}
            className="w-9 h-9 rounded-xl glass-card flex items-center justify-center hover:bg-white/10 transition-all duration-150"
          >
            <ArrowLeft className="w-4 h-4 text-text-secondary" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">音色管理</h1>
            <p className="text-text-secondary text-sm">管理并选择您的 GPT-SoVITS 音色</p>
          </div>
        </div>

        {/* 上传区域 */}
        <div
          {...getRootProps()}
          className={`glass-card p-8 mb-8 border-dashed border-2 cursor-pointer transition-all duration-200 flex flex-col items-center gap-3 ${
            isDragActive
              ? 'border-brand-purple/60 bg-brand-purple/5'
              : 'border-white/15 hover:border-white/25 hover:bg-white/[0.03]'
          }`}
        >
          <input {...getInputProps()} />
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-200 ${
            isDragActive ? 'bg-brand-gradient' : 'bg-white/10'
          }`}>
            <Upload className={`w-6 h-6 ${isDragActive ? 'text-white' : 'text-text-secondary'}`} />
          </div>
          <div className="text-center">
            <p className="text-text-primary font-medium">
              {isDragActive ? '松开即可上传' : '拖拽 ZIP 文件到这里'}
            </p>
            <p className="text-text-secondary text-sm mt-1">
              或点击选择文件 · 支持来自 voice-cloning-service 导出的音色包
            </p>
          </div>
        </div>

        {/* 上传进度 */}
        <AnimatePresence>
          {uploadProgress && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="glass-card p-4 mb-6"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-primary truncate max-w-xs">
                  {uploadProgress.filename}
                </span>
                <span className={`text-xs font-medium ${
                  uploadProgress.status === 'error' ? 'text-red-400' :
                  uploadProgress.status === 'success' ? 'text-green-400' :
                  'text-text-secondary'
                }`}>
                  {uploadProgress.status === 'uploading' ? `${uploadProgress.progress}%` :
                   uploadProgress.status === 'success' ? '上传成功' : '上传失败'}
                </span>
              </div>
              {uploadProgress.status === 'uploading' && (
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-gradient rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress.progress}%` }}
                  />
                </div>
              )}
              {uploadProgress.error && (
                <p className="text-xs text-red-400 mt-1">{uploadProgress.error}</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* 音色列表 */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-brand-purple" />
          </div>
        ) : voices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
              <Mic className="w-8 h-8 text-text-muted" />
            </div>
            <p className="text-text-primary font-medium">还没有音色</p>
            <p className="text-text-secondary text-sm mt-1">上传来自 voice-cloning-service 的 ZIP 包开始使用</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <p className="text-text-secondary text-sm">{voices.length} 个音色</p>
              {currentVoice && (
                <span className="text-xs text-brand-purple bg-brand-purple/10 px-3 py-1 rounded-full">
                  当前：{currentVoice.voice_name}
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <AnimatePresence mode="popLayout">
                {voices.map((voice) => (
                  <VoiceCard
                    key={voice.id}
                    voice={voice}
                    isSelected={currentVoice?.id === voice.id}
                    onSelect={() => handleSelect(voice)}
                    onDelete={() => setDeleteTarget(voice)}
                  />
                ))}
              </AnimatePresence>
            </div>
          </>
        )}
      </div>

      {/* 删除确认弹窗 */}
      <AnimatePresence>
        {deleteTarget && (
          <DeleteConfirmDialog
            voice={deleteTarget}
            onConfirm={handleDelete}
            onCancel={() => setDeleteTarget(null)}
          />
        )}
      </AnimatePresence>

      {/* Toast 提示 */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: 20, x: '-50%' }}
            className={`fixed bottom-6 left-1/2 px-5 py-3 rounded-xl text-sm font-medium shadow-card z-50 ${
              toast.type === 'error'
                ? 'bg-red-500/20 border border-red-500/30 text-red-300'
                : 'bg-green-500/20 border border-green-500/30 text-green-300'
            }`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
