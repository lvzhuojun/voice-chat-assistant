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
  const [isConnected, setIsConnected] = useState(false)

  const { token } = useAuthStore()
  const {
    appendStreamingText,
    clearStreamingText,
    addMessage,
    setProcessing,
    addAudioChunk,
    clearAudioChunks,
    messages,
    streamingText,
  } = useChatStore()

  // 播放 base64 WAV 音频
  const playAudioChunk = useCallback(async (base64Data: string) => {
    try {
      const binary = atob(base64Data)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i)
      }
      const blob = new Blob([bytes], { type: 'audio/wav' })
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => URL.revokeObjectURL(url)
      await audio.play()
    } catch (err) {
      console.error('音频播放失败:', err)
    }
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
          // TTS 音频块：播放
          addAudioChunk(msg.data)
          playAudioChunk(msg.data)
          break

        case 'done':
          // 本轮完成：将 streamingText 转为正式消息
          if (streamingText) {
            addMessage({
              id: parseInt(msg.message_id),
              conversation_id: conversationId!,
              role: 'assistant',
              content: streamingText,
              created_at: new Date().toISOString(),
            })
          }
          clearStreamingText()
          clearAudioChunks()
          setProcessing(false)
          break

        case 'error':
          console.error('WebSocket 服务端错误:', msg.message)
          clearStreamingText()
          setProcessing(false)
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
      playAudioChunk,
      streamingText,
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
      wsRef.current = null
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

  // 对话切换时重新连接
  useEffect(() => {
    // 关闭旧连接
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
    }
  }, [conversationId])  // eslint-disable-line react-hooks/exhaustive-deps

  /** 发送音频二进制帧 */
  const sendAudio = useCallback((audioBlob: Blob) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket 未连接，无法发送音频')
      return
    }
    setProcessing(true)
    clearStreamingText()
    ws.send(audioBlob)
  }, [setProcessing, clearStreamingText])

  /** 发送文字消息 */
  const sendText = useCallback((text: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket 未连接，无法发送文字')
      return
    }
    setProcessing(true)
    clearStreamingText()
    ws.send(JSON.stringify({ type: 'text', content: text }))
  }, [setProcessing, clearStreamingText])

  /** 手动断开 */
  const disconnect = useCallback(() => {
    wsRef.current?.close(1000)
    wsRef.current = null
    setIsConnected(false)
  }, [])

  return { isConnected, sendAudio, sendText, disconnect }
}
