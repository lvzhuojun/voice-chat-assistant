/**
 * 对话主界面
 * Main chat interface
 * 布局：左侧 260px 侧边栏 + 右侧主区域
 * Layout: 260px left sidebar + right main area
 * 功能：语音录制/文字输入 + WebSocket 实时对话 + 消息历史
 * Features: voice recording / text input + WebSocket real-time chat + message history
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mic,
  Menu,
  X,
  Plus,
  MessageSquare,
  Trash2,
  LogOut,
  Send,
  Keyboard,
  ChevronRight,
  Loader2,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useVoiceStore } from '@/store/voiceStore'
import { useChatStore } from '@/store/chatStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAudioRecorder } from '@/hooks/useAudioRecorder'
import * as conversationApi from '@/api/conversations'
import * as voiceApi from '@/api/voices'
import MessageBubble, { StreamingBubble } from '@/components/chat/MessageBubble'
import RecordButton from '@/components/voice/RecordButton'
import type { Conversation, Message } from '@/types'

export default function ChatPage() {
  const navigate = useNavigate()
  const { user, clearAuth } = useAuthStore()
  const { currentVoice, setCurrentVoice, voices, setVoices } = useVoiceStore()
  const {
    conversations,
    activeConversationId,
    messages,
    streamingText,
    isProcessing,
    messageAudioData,
    setConversations,
    addConversation,
    removeConversation,
    setActiveConversation,
    setMessages,
    addMessage,
  } = useChatStore()

  const [textInput, setTextInput] = useState('')
  const [inputMode, setInputMode] = useState<'voice' | 'text'>('voice')
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [notice, setNotice] = useState<{ msg: string; type: 'error' | 'info' } | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { isConnected, wsError, sendAudio, sendText } = useWebSocket({
    conversationId: activeConversationId,
  })

  const { recordingState, audioLevel, startRecording, stopRecording } = useAudioRecorder({
    onAutoStop: sendAudio,
  })

  // 初始化：加载对话列表 + 当前音色
  // Initialization: load conversation list and current voice model
  useEffect(() => {
    const init = async () => {
      try {
        const [convRes, voiceRes, voicesRes] = await Promise.allSettled([
          conversationApi.listConversations(),
          voiceApi.getCurrentVoice(),
          voiceApi.listVoices(),
        ])
        if (convRes.status === 'fulfilled') {
          setConversations(convRes.value.data)
          // 自动选中第一个对话 / Automatically select the first conversation
          if (convRes.value.data.length > 0 && !activeConversationId) {
            setActiveConversation(convRes.value.data[0].id)
          }
        }
        if (voiceRes.status === 'fulfilled') setCurrentVoice(voiceRes.value.data)
        if (voicesRes.status === 'fulfilled') setVoices(voicesRes.value.data)
      } catch {
        // 忽略 / Ignore errors silently
      }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 切换对话时加载消息 / Load messages when the active conversation changes
  useEffect(() => {
    if (!activeConversationId) return
    setIsLoadingMessages(true)
    setMessages([])
    conversationApi
      .getMessages(activeConversationId)
      .then((res) => setMessages(res.data))
      .catch(() => {})
      .finally(() => setIsLoadingMessages(false))
  }, [activeConversationId]) // eslint-disable-line react-hooks/exhaustive-deps

  // 消息列表更新时自动滚到底部 / Auto-scroll to the bottom when the message list updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  // 将 WebSocket 服务端错误同步到通知栏
  // Sync WebSocket server errors to the notification bar
  useEffect(() => {
    if (!wsError) return
    setNotice({ msg: wsError, type: 'error' })
    const t = setTimeout(() => setNotice(null), 5000)
    return () => clearTimeout(t)
  }, [wsError])

  // 新建对话 / Create a new conversation
  const handleNewConversation = async () => {
    try {
      const res = await conversationApi.createConversation({
        title: '新对话',
        voice_model_id: currentVoice?.id ?? null,
      })
      addConversation(res.data)
      setActiveConversation(res.data.id)
      setIsSidebarOpen(false)
    } catch {
      console.error('新建对话失败')
    }
  }

  // 删除对话 / Delete a conversation
  const handleDeleteConversation = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    try {
      await conversationApi.deleteConversation(id)
      removeConversation(id)
      if (activeConversationId === id) {
        const remaining = conversations.filter((c) => c.id !== id)
        setActiveConversation(remaining[0]?.id ?? null)
      }
    } catch {
      console.error('删除对话失败')
    }
  }

  // 开始录音 / Start recording
  const handleRecordStart = async () => {
    if (!activeConversationId) {
      try {
        await handleNewConversation()
      } catch {
        return  // 对话创建失败，不启动录音 / Abort if conversation creation failed
      }
    }
    await startRecording()
  }

  // 停止录音，发送音频 / Stop recording and send the audio blob
  const handleRecordStop = async () => {
    const blob = await stopRecording()
    if (blob && blob.size > 1000) {
      sendAudio(blob)
    }
  }

  // 发送文字消息 / Send a text message
  const handleSendText = () => {
    if (!textInput.trim() || !activeConversationId) return
    // 本地显示用户消息 / Optimistically display the user message locally
    addMessage({
      id: Date.now(),
      conversation_id: activeConversationId,
      role: 'user',
      content: textInput.trim(),
      created_at: new Date().toISOString(),
    })
    sendText(textInput.trim())
    setTextInput('')
  }

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  // 当前对话信息 / Current active conversation object
  const activeConversation = conversations.find((c) => c.id === activeConversationId)

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: '#0a0a0f' }}>
      {/* ── 移动端遮罩层 / Mobile backdrop overlay ───────────────── */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/60 z-40 md:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* ── 左侧侧边栏 / Left sidebar ─────────────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 flex flex-col w-[280px]
          border-r border-white/[0.06] bg-[#0a0a0f]
          transition-transform duration-300 ease-in-out
          ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0 md:w-[260px] md:flex-shrink-0
        `}
      >
        {/* Logo + 新建按钮 / Logo + new conversation button */}
        <div className="p-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-xl bg-brand-gradient flex items-center justify-center">
              <Mic className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-text-primary flex-1">Voice Chat</span>
            {/* 关闭按钮（移动端）/ Close button (mobile only) */}
            <button
              className="md:hidden w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/10 transition-all"
              onClick={() => setIsSidebarOpen(false)}
            >
              <X className="w-4 h-4 text-text-muted" />
            </button>
          </div>
          <button
            onClick={handleNewConversation}
            className="w-full btn-gradient text-white text-sm font-medium rounded-xl py-2.5 flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            新建对话
          </button>
        </div>

        {/* 对话列表 / Conversation list */}
        <div className="flex-1 overflow-y-auto py-2 px-2">
          <p className="text-xs text-text-muted px-2 mb-2 mt-1">最近对话</p>
          <AnimatePresence>
            {conversations.map((conv) => (
              <motion.div
                key={conv.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.15 }}
                onClick={() => { setActiveConversation(conv.id); setIsSidebarOpen(false) }}
                className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 mb-0.5 ${
                  activeConversationId === conv.id
                    ? 'bg-brand-purple/20 text-text-primary'
                    : 'text-text-secondary hover:bg-white/[0.05] hover:text-text-primary'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 opacity-60" />
                <span className="flex-1 text-sm truncate">{conv.title}</span>
                <button
                  onClick={(e) => handleDeleteConversation(e, conv.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 hover:text-red-400 p-0.5"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
          {conversations.length === 0 && (
            <p className="text-xs text-text-muted text-center py-4">暂无对话，点击上方新建</p>
          )}
        </div>

        {/* 底部：音色卡片 + 用户信息 / Bottom: voice card + user info */}
        <div className="border-t border-white/[0.06] p-3 space-y-2">
          {/* 当前音色 / Current voice model */}
          <button
            onClick={() => navigate('/voices')}
            className="w-full glass-card p-3 flex items-center gap-2 hover:bg-white/[0.08] transition-all duration-150 text-left"
          >
            <div className="w-7 h-7 rounded-lg bg-brand-gradient flex items-center justify-center flex-shrink-0">
              <Mic className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-text-muted">当前音色</p>
              <p className="text-sm text-text-primary truncate font-medium">
                {currentVoice?.voice_name ?? '未选择'}
              </p>
            </div>
            <ChevronRight className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
          </button>

          {/* 用户信息 + 登出 / User info + logout */}
          <div className="flex items-center gap-2 px-1">
            <div className="w-7 h-7 rounded-full bg-brand-gradient flex items-center justify-center flex-shrink-0">
              <span className="text-white text-xs font-bold">
                {user?.username?.[0]?.toUpperCase() ?? 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-text-primary truncate font-medium">{user?.username}</p>
              <p className="text-xs text-text-muted truncate">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="w-7 h-7 rounded-lg hover:bg-white/10 flex items-center justify-center transition-all duration-150 flex-shrink-0"
              title="退出登录"
            >
              <LogOut className="w-3.5 h-3.5 text-text-muted hover:text-red-400 transition-colors" />
            </button>
          </div>
        </div>
      </aside>

      {/* ── 右侧主区域 / Right main area ──────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 / Top bar */}
        <div className="h-14 border-b border-white/[0.06] flex items-center px-4 md:px-6 gap-3 flex-shrink-0">
          {/* 汉堡按钮（移动端）/ Hamburger menu button (mobile only) */}
          <button
            className="md:hidden w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-all flex-shrink-0"
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu className="w-5 h-5 text-text-secondary" />
          </button>
          <h2 className="font-semibold text-text-primary flex-1 truncate">
            {activeConversation?.title ?? '选择或新建对话'}
          </h2>
          {currentVoice && (
            <span className="text-xs bg-brand-purple/10 text-brand-purple px-2.5 py-1 rounded-full border border-brand-purple/20 flex items-center gap-1">
              <Mic className="w-3 h-3" />
              {currentVoice.voice_name}
            </span>
          )}
          {isConnected ? (
            <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" title="已连接" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-white/20 flex-shrink-0" title="未连接" />
          )}
        </div>

        {/* 消息区域 / Message area */}
        <div className="flex-1 overflow-y-auto px-3 py-4 md:px-6 md:py-6">
          {!activeConversationId ? (
            // 空状态 / Empty state
            <div className="flex flex-col items-center justify-center h-full text-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="w-20 h-20 rounded-2xl bg-brand-gradient flex items-center justify-center mb-6 shadow-glow-purple"
              >
                <Mic className="w-10 h-10 text-white" />
              </motion.div>
              <h3 className="text-xl font-bold text-text-primary mb-2">开始语音对话</h3>
              <p className="text-text-secondary text-sm max-w-sm">
                点击「新建对话」开始，按住录音按钮说话，或切换文字模式输入
              </p>
            </div>
          ) : isLoadingMessages ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-brand-purple" />
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  audioData={msg.role === 'assistant' ? messageAudioData[msg.id] : undefined}
                />
              ))}
              {streamingText && <StreamingBubble text={streamingText} />}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 通知栏（WS 错误 / 连接提示）/ Notification bar (WebSocket errors / connection hints) */}
        <AnimatePresence>
          {notice && (
            <motion.div
              key="notice"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className={`px-4 md:px-6 py-2 text-sm flex-shrink-0 ${
                notice.type === 'error'
                  ? 'text-red-400 bg-red-500/10 border-t border-red-500/20'
                  : 'text-yellow-400 bg-yellow-500/10 border-t border-yellow-500/20'
              }`}
            >
              {notice.msg}
            </motion.div>
          )}
        </AnimatePresence>

        {/* 底部输入区 / Bottom input area */}
        <div className="border-t border-white/[0.06] px-4 py-4 md:px-6 md:py-5 flex-shrink-0">
          {inputMode === 'voice' ? (
            // 语音模式 / Voice input mode
            <div className="flex items-center justify-center gap-8">
              <div className="text-center text-xs text-text-muted w-24">
                {recordingState === 'idle' && '按住说话'}
                {recordingState === 'recording' && (
                  <span className="text-red-400 font-medium">录音中…</span>
                )}
                {recordingState === 'processing' && (
                  <span className="text-brand-purple">处理中…</span>
                )}
              </div>

              <RecordButton
                state={recordingState}
                audioLevel={audioLevel}
                onMouseDown={handleRecordStart}
                onMouseUp={handleRecordStop}
                onTouchStart={handleRecordStart}
                onTouchEnd={handleRecordStop}
              />

              {/* 切换文字输入 / Switch to text input mode */}
              <button
                onClick={() => setInputMode('text')}
                className="w-10 h-10 rounded-xl glass-card flex items-center justify-center hover:bg-white/10 transition-all duration-150"
                title="切换文字输入"
              >
                <Keyboard className="w-4 h-4 text-text-secondary" />
              </button>
            </div>
          ) : (
            // 文字模式 / Text input mode
            <div className="flex items-center gap-3">
              <button
                onClick={() => setInputMode('voice')}
                className="w-10 h-10 rounded-xl glass-card flex items-center justify-center hover:bg-white/10 transition-all duration-150 flex-shrink-0"
                title="切换语音输入"
              >
                <Mic className="w-4 h-4 text-text-secondary" />
              </button>
              <input
                ref={inputRef}
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendText()}
                placeholder="输入消息…（Enter 发送）"
                disabled={isProcessing || !activeConversationId}
                maxLength={500}
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted text-sm focus:outline-none focus:border-brand-purple/60 focus:ring-1 focus:ring-brand-purple/40 transition-all duration-150 disabled:opacity-50"
                autoFocus
              />
              <button
                onClick={handleSendText}
                disabled={!textInput.trim() || isProcessing || !activeConversationId}
                className="w-10 h-10 rounded-xl btn-gradient flex items-center justify-center flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isProcessing ? (
                  <Loader2 className="w-4 h-4 text-white animate-spin" />
                ) : (
                  <Send className="w-4 h-4 text-white" />
                )}
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
