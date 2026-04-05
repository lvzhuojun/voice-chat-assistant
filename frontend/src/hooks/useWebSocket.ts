/**
 * WebSocket Hook
 * 自动重连，解析服务端消息，处理音频播放
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useChatStore } from '@/store/chatStore'
import type { WsMessage } from '@/types'

interface UseWebSocketProps {
  conversationId: number | null
}

interface UseWebSocketReturn {
  isConnected: boolean
  wsError: string | null
  sendAudio: (audioBlob: Blob) => void
  sendText: (text: string) => void
  disconnect: () => void
}

/** 重连间隔（毫秒） */
const RECONNECT_INTERVALS = [1000, 2000, 5000, 10000]

export function useWebSocket({ conversationId }: UseWebSocketProps): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wsErrorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [wsError, setWsError] = useState<string | null>(null)

  const { token } = useAuthStore()
  const {
    appendStreamingText,
    clearStreamingText,
    addMessage,
    setProcessing,
    addAudioChunk,
    clearAudioChunks,
    setMessageAudio,
    updateConversationTitle,
  } = useChatStore()

  // 用 ref 追踪最新 streamingText，避免 handleMessage 产生 stale closure
  const streamingTextRef = useRef('')
  const streamingText = useChatStore((s) => s.streamingText)
  streamingTextRef.current = streamingText

  // 追踪本轮所有 TTS 音频块（用于 done 时存入 messageAudioData 供重播）
  const currentAudioChunksRef = useRef<string[]>([])
  // 顺序音频播放队列（分句 TTS 场景：按 seq 顺序入队，依次播放）
  const audioQueueRef = useRef<string[]>([])
  const isPlayingAudioRef = useRef(false)

  /** 播放单段 base64 WAV，返回 Promise（音频结束后 resolve） */
  const playAudioData = useCallback((base64Data: string): Promise<void> => {
    return new Promise((resolve) => {
      try {
        const binary = atob(base64Data)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i)
        }
        const blob = new Blob([bytes], { type: 'audio/wav' })
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audio.onended = () => { URL.revokeObjectURL(url); resolve() }
        audio.onerror = () => { URL.revokeObjectURL(url); resolve() }
        audio.play().catch(() => resolve())
      } catch (err) {
        console.error('音频播放失败:', err)
        resolve()
      }
    })
  }, [])

  /** 逐段消费音频队列，保证顺序不重叠 */
  const drainAudioQueue = useCallback(async () => {
    if (isPlayingAudioRef.current) return
    isPlayingAudioRef.current = true
    while (audioQueueRef.current.length > 0) {
      const data = audioQueueRef.current.shift()!
      await playAudioData(data)
    }
    isPlayingAudioRef.current = false
  }, [playAudioData])

  /** 将音频加入队列并触发播放 */
  const enqueueAudio = useCallback((base64Data: string) => {
    audioQueueRef.current.push(base64Data)
    drainAudioQueue()
  }, [drainAudioQueue])

  /** 清空音频队列（切换对话/出错时调用） */
  const clearAudioQueue = useCallback(() => {
    audioQueueRef.current = []
    isPlayingAudioRef.current = false
  }, [])

  // 处理服务端消息
  const handleMessage = useCallback(
    (msg: WsMessage) => {
      switch (msg.type) {
        case 'transcript':
          // STT 识别结果：添加用户消息到本地（乐观更新）
          addMessage({
            id: Date.now(),
            conversation_id: conversationId!,
            role: 'user',
            content: msg.text,
            created_at: new Date().toISOString(),
          })
          break

        case 'llm_chunk':
          // LLM 流式文字：累积到 streamingText
          appendStreamingText(msg.text)
          break

        case 'audio_chunk':
          // 分句 TTS 音频：入队顺序播放（保证多句不重叠、不乱序）
          addAudioChunk(msg.data)
          currentAudioChunksRef.current.push(msg.data)  // 累积所有块供重播
          enqueueAudio(msg.data)
          break

        case 'done': {
          // 本轮完成：将 streamingText 转为正式消息
          const messageId = parseInt(msg.message_id)
          if (streamingTextRef.current) {
            addMessage({
              id: messageId,
              conversation_id: conversationId!,
              role: 'assistant',
              content: streamingTextRef.current,
              created_at: new Date().toISOString(),
            })
          }
          // 将所有音频块与消息绑定（供完整重播）
          if (currentAudioChunksRef.current.length > 0) {
            setMessageAudio(messageId, [...currentAudioChunksRef.current])
            currentAudioChunksRef.current = []
          }
          clearStreamingText()
          clearAudioChunks()
          setProcessing(false)
          break
        }

        case 'title_updated':
          // 首轮完成后服务端自动生成的标题
          if (conversationId) {
            updateConversationTitle(conversationId, msg.title)
          }
          break

        case 'error':
          console.error('WebSocket 服务端错误:', msg.message)
          clearStreamingText()
          setProcessing(false)
          setWsError(msg.message)
          if (wsErrorTimerRef.current) clearTimeout(wsErrorTimerRef.current)
          wsErrorTimerRef.current = setTimeout(() => setWsError(null), 5000)
          break
      }
    },
    [
      conversationId,
      addMessage,
      appendStreamingText,
      addAudioChunk,
      clearStreamingText,
      clearAudioChunks,
      setProcessing,
      setMessageAudio,
      updateConversationTitle,
      enqueueAudio,
      // streamingText 不放这里，改用 streamingTextRef 避免 stale closure
    ]
  )

  // 建立 WebSocket 连接
  const connect = useCallback(() => {
    if (!conversationId || !token) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const wsUrl = `ws://${window.location.host}/ws/chat/${conversationId}?token=${token}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      reconnectCountRef.current = 0
      console.log(`WebSocket 已连接：conv=${conversationId}`)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        handleMessage(msg)
      } catch (err) {
        console.error('WebSocket 消息解析失败:', err)
      }
    }

    ws.onclose = (event) => {
      setIsConnected(false)
      // 仅在当前 ws 仍是活跃引用时才清空，防止切换对话时新 ws 被意外覆盖
      if (wsRef.current === ws) {
        wsRef.current = null
      }
      console.log(`WebSocket 断开：code=${event.code}`)

      // 非正常关闭时自动重连
      if (event.code !== 1000 && event.code !== 4001 && event.code !== 4004) {
        const idx = Math.min(reconnectCountRef.current, RECONNECT_INTERVALS.length - 1)
        const delay = RECONNECT_INTERVALS[idx]
        reconnectCountRef.current++
        console.log(`${delay}ms 后重连...（第${reconnectCountRef.current}次）`)
        reconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket 错误:', err)
    }
  }, [conversationId, token, handleMessage])

  // 对话切换时重新连接，并清空旧音频队列
  useEffect(() => {
    // 清空音频队列，避免上一个对话的音频在新对话中继续播放
    clearAudioQueue()
    currentAudioChunksRef.current = []

    if (wsRef.current) {
      wsRef.current.close(1000)
      wsRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    reconnectCountRef.current = 0

    if (conversationId && token) {
      connect()
    }

    return () => {
      wsRef.current?.close(1000)
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      clearAudioQueue()
    }
  }, [conversationId])  // eslint-disable-line react-hooks/exhaustive-deps

  /** 发送音频二进制帧（CONNECTING 时自动等握手完成再发） */
  const sendAudio = useCallback((audioBlob: Blob) => {
    const ws = wsRef.current
    if (!ws || ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED) {
      console.warn('WebSocket 已断开，无法发送音频')
      return
    }
    setProcessing(true)
    clearStreamingText()
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(audioBlob)
    } else {
      // CONNECTING：握手完成后立即发送
      ws.addEventListener('open', () => {
        wsRef.current?.send(audioBlob)
      }, { once: true })
    }
  }, [setProcessing, clearStreamingText])

  /** 发送文字消息（CONNECTING 时自动等握手完成再发） */
  const sendText = useCallback((text: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED) {
      console.warn('WebSocket 已断开，无法发送文字')
      return
    }
    setProcessing(true)
    clearStreamingText()
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'text', content: text }))
    } else {
      // CONNECTING：握手完成后立即发送
      ws.addEventListener('open', () => {
        wsRef.current?.send(JSON.stringify({ type: 'text', content: text }))
      }, { once: true })
    }
  }, [setProcessing, clearStreamingText])

  /** 手动断开 */
  const disconnect = useCallback(() => {
    wsRef.current?.close(1000)
    wsRef.current = null
    setIsConnected(false)
  }, [])

  return { isConnected, wsError, sendAudio, sendText, disconnect }
}
