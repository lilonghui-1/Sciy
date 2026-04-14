import { ref, onUnmounted } from 'vue'
import { sendChatMessage } from '@/api/ai'
import type { ChatMessage } from '@/api/ai'

export interface MessageItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

export function useAIChat() {
  const messages = ref<MessageItem[]>([])
  const isLoading = ref(false)
  const currentController = ref<AbortController | null>(null)

  function generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).slice(2)
  }

  async function sendMessage(content: string) {
    if (!content.trim() || isLoading.value) return

    // 添加用户消息
    const userMessage: MessageItem = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }
    messages.value.push(userMessage)

    // 添加AI占位消息（流式状态）
    const assistantMessage: MessageItem = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    }
    messages.value.push(assistantMessage)

    isLoading.value = true

    // 构建发送给API的消息历史
    const chatMessages: ChatMessage[] = messages.value
      .filter((m) => m.role !== 'system')
      .slice(0, -1) // 排除当前空的AI消息
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))

    currentController.value = sendChatMessage(
      chatMessages,
      // onChunk
      (text: string) => {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content += text
        }
      },
      // onDone
      () => {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.isStreaming = false
        }
        isLoading.value = false
        currentController.value = null
      },
      // onError
      (error: Error) => {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.content = `抱歉，发生了错误：${error.message}`
          lastMsg.isStreaming = false
        }
        isLoading.value = false
        currentController.value = null
      }
    )
  }

  function clearHistory() {
    if (currentController.value) {
      currentController.value.abort()
      currentController.value = null
    }
    messages.value = []
    isLoading.value = false
  }

  function stopGeneration() {
    if (currentController.value) {
      currentController.value.abort()
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        lastMsg.isStreaming = false
        if (!lastMsg.content) {
          lastMsg.content = '（已停止生成）'
        }
      }
      currentController.value = null
      isLoading.value = false
    }
  }

  function deleteMessage(id: string) {
    const index = messages.value.findIndex((m) => m.id === id)
    if (index !== -1) {
      messages.value.splice(index, 1)
    }
  }

  onUnmounted(() => {
    if (currentController.value) {
      currentController.value.abort()
    }
  })

  return {
    messages,
    isLoading,
    sendMessage,
    clearHistory,
    stopGeneration,
    deleteMessage,
  }
}
