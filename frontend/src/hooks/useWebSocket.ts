/**
 * WebSocket Hook
 * 自动重连，解析服务端消息，处理音频播放
 * Auto-reconnect, parse server messages, and handle audio playback.
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

/** 重连间隔（毫秒） / Reconnection delay intervals (milliseconds) */
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
  // Track the latest streamingText via ref to avoid stale closures in handleMessage
  const streamingTextRef = useRef('')
  const streamingText = useChatStore((s) => s.streamingText)
  streamingTextRef.current = streamingText

  // 追踪本轮所有 TTS 音频块（用于 done 时存入 messageAudioData 供重播）
  // Track all TTS audio chunks for the current turn (stored on 'done' for later replay)
  const currentAudioChunksRef = useRef<string[]>([])
  // 顺序音频播放队列（分句 TTS 场景：按 seq 顺序入队，依次播放）
  // Sequential audio playback queue (for sentence-by-sentence TTS: enqueued by seq, played in order)
  const audioQueueRef = useRef<string[]>([])
  const isPlayingAudioRef = useRef(false)

  /** 播放单段 base64 WAV，返回 Promise（音频结束后 resolve） / Play a single base64 WAV segment, returns a Promise that resolves when playback ends */
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

  /** 逐段消费音频队列，保证顺序不重叠 / Drain the audio queue segment by segment, ensuring ordered non-overlapping playback */
  const drainAudioQueue = useCallback(async () => {
    if (isPlayingAudioRef.current) return
    isPlayingAudioRef.current = true
    while (audioQueueRef.current.length > 0) {
      const data = audioQueueRef.current.shift()!
      await playAudioData(data)
    }
    isPlayingAudioRef.current = false
  }, [playAudioData])

  /** 将音频加入队列并触发播放 / Enqueue an audio segment and trigger playback */
  const enqueueAudio = useCallback((base64Data: string) => {
    audioQueueRef.current.push(base64Data)
    drainAudioQueue()
  }, [drainAudioQueue])

  /** 清空音频队列（切换对话/出错时调用） / Clear the audio queue (called on conversation switch or error) */
  const clearAudioQueue = useCallback(() => {
    audioQueueRef.current = []
    isPlayingAudioRef.current = false
  }, [])

  // 处理服务端消息 / Handle incoming server messages
  const handleMessage = useCallback(
    (msg: WsMessage) => {
      switch (msg.type) {
        case 'transcript':
          // STT 识别结果：添加用户消息到本地（乐观更新）
          // STT result: add user message locally (optimistic update)
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
          // LLM streaming text: accumulate into streamingText
          appendStreamingText(msg.text)
          break

        case 'audio_chunk':
          // 分句 TTS 音频：入队顺序播放（保证多句不重叠、不乱序）
          // Sentence-level TTS audio: enqueue for ordered playback (no overlap or out-of-order)
          addAudioChunk(msg.data)
          currentAudioChunksRef.current.push(msg.data)  // 累积所有块供重播 / Accumulate all chunks for replay
          enqueueAudio(msg.data)
          break

        case 'done': {
          // 本轮完成：将 streamingText 转为正式消息
          // Turn complete: convert streamingText into a persisted message
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
          // Bind all audio chunks to the message for full replay
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
          // Auto-generated conversation title from the server after the first turn
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
      // streamingText is intentionally omitted; streamingTextRef is used to avoid stale closure
    ]
  )

  // 建立 WebSocket 连接 / Establish the WebSocket connection
  const connect = useCallback(() => {
    if (!conversationId || !token) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/${conversationId}?token=${token}`
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
      // 仅在当前 ws 仍是活跃引用时才更新状态，防止旧连接的 close 事件
      // 覆盖新连接已建立后的 isConnected=true
      // Only update state if this ws is still the active reference,
      // preventing a stale close event from overwriting isConnected=true of a newer connection
      if (wsRef.current === ws) {
        wsRef.current = null
        setIsConnected(false)
      }
      console.log(`WebSocket 断开：code=${event.code}`)

      // 非正常关闭时自动重连 / Auto-reconnect on abnormal close codes
      if (event.code !== 1000 && event.code !== 4001 && event.code !== 4004) {
        const idx = Math.min(reconnectCountRef.current, RECONNECT_INTERVALS.length - 1)
        const delay = RECONNECT_INTERVALS[idx]
        reconnectCountRef.current++
        console.log(`${delay}ms 后重连...（第${reconnectCountRef.current}次）`)
        reconnectTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = (err) => {
      // 仅在此 ws 仍是活跃连接时打印错误，避免切换对话后旧连接的
      // "closed before connection is established" 噪音日志
      // Only log errors if this ws is still the active connection,
      // suppressing noisy "closed before connection is established" logs from stale connections
      if (wsRef.current === ws) {
        console.error('WebSocket 错误:', err)
      }
    }
  }, [conversationId, token, handleMessage])

  // 对话切换时重新连接，并清空旧音频队列
  // Re-connect and clear the audio queue when the active conversation changes
  useEffect(() => {
    // 清空音频队列，避免上一个对话的音频在新对话中继续播放
    // Clear the audio queue to prevent audio from the previous conversation from playing in the new one
    clearAudioQueue()
    currentAudioChunksRef.current = []

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    reconnectCountRef.current = 0

    // 安全关闭旧连接：CONNECTING 状态下等握手完成再关，避免触发
    // "WebSocket is closed before the connection is established" 浏览器错误
    // Safely close the old connection: if CONNECTING, wait for the handshake to complete before closing
    // to avoid triggering a "WebSocket is closed before the connection is established" browser error
    const oldWs = wsRef.current
    wsRef.current = null
    if (oldWs) {
      if (oldWs.readyState === WebSocket.CONNECTING) {
        oldWs.addEventListener('open', () => oldWs.close(1000), { once: true })
      } else {
        oldWs.close(1000)
      }
    }

    if (conversationId && token) {
      connect()
    }

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      clearAudioQueue()
      const ws = wsRef.current
      wsRef.current = null
      if (ws) {
        if (ws.readyState === WebSocket.CONNECTING) {
          ws.addEventListener('open', () => ws.close(1000), { once: true })
        } else {
          ws.close(1000)
        }
      }
    }
  }, [conversationId])  // eslint-disable-line react-hooks/exhaustive-deps

  /** 发送音频二进制帧（CONNECTING 时自动等握手完成再发） / Send a binary audio frame (auto-waits for handshake if CONNECTING) */
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
      // CONNECTING：握手完成后立即发送。
      // 使用捕获的 ws 而非 wsRef.current，避免连接切换后消息发到错误对话。
      // CONNECTING: send immediately after the handshake completes.
      // Use the captured ws instead of wsRef.current to avoid sending to the wrong conversation after a switch.
      ws.addEventListener('open', () => { ws.send(audioBlob) }, { once: true })
    }
  }, [setProcessing, clearStreamingText])

  /** 发送文字消息（CONNECTING 时自动等握手完成再发） / Send a text message (auto-waits for handshake if CONNECTING) */
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
      // CONNECTING：同上，使用捕获的 ws / CONNECTING: same as above, use the captured ws
      ws.addEventListener('open', () => {
        ws.send(JSON.stringify({ type: 'text', content: text }))
      }, { once: true })
    }
  }, [setProcessing, clearStreamingText])

  /** 手动断开 / Manually disconnect */
  const disconnect = useCallback(() => {
    wsRef.current?.close(1000)
    wsRef.current = null
    setIsConnected(false)
  }, [])

  return { isConnected, wsError, sendAudio, sendText, disconnect }
}
