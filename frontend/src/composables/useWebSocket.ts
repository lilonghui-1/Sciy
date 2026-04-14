import { ref, onUnmounted } from 'vue'

export interface WebSocketOptions {
  url: string
  onMessage?: (data: any) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

export function useWebSocket(options: WebSocketOptions) {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
  } = options

  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const lastMessage = ref<any>(null)
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  function connect() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      return
    }

    const token = localStorage.getItem('token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsBaseUrl = url.startsWith('ws') ? url : `${protocol}//${window.location.host}${url}`
    const wsUrl = token ? `${wsBaseUrl}?token=${token}` : wsBaseUrl

    try {
      ws.value = new WebSocket(wsUrl)

      ws.value.onopen = () => {
        isConnected.value = true
        reconnectAttempts.value = 0
        startHeartbeat()
        onOpen?.()
      }

      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          lastMessage.value = data
          onMessage?.(data)
        } catch {
          lastMessage.value = event.data
          onMessage?.(event.data)
        }
      }

      ws.value.onclose = (event) => {
        isConnected.value = false
        stopHeartbeat()
        onClose?.()
        // 非正常关闭时尝试重连
        if (!event.wasClean) {
          attemptReconnect()
        }
      }

      ws.value.onerror = (error) => {
        onError?.(error)
      }
    } catch (error) {
      console.error('WebSocket连接失败:', error)
      attemptReconnect()
    }
  }

  function attemptReconnect() {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      console.warn('WebSocket重连次数已达上限')
      return
    }

    reconnectAttempts.value++
    console.log(`WebSocket尝试第${reconnectAttempts.value}次重连...`)

    reconnectTimer = setTimeout(() => {
      connect()
    }, reconnectInterval)
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      send({ type: 'ping', timestamp: Date.now() })
    }, heartbeatInterval)
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopHeartbeat()
    reconnectAttempts.value = maxReconnectAttempts // 阻止自动重连
    if (ws.value) {
      ws.value.close(1000, '用户主动断开')
      ws.value = null
    }
    isConnected.value = false
  }

  function send(data: any) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      ws.value.send(message)
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    ws,
    isConnected,
    reconnectAttempts,
    lastMessage,
    connect,
    disconnect,
    send,
  }
}
