<template>
  <div class="ai-chat-mobile">
    <!-- 顶部导航栏 -->
    <van-nav-bar title="AI智能助手" left-text="清空" left-arrow @click-left="handleClear">
      <template #right>
        <van-icon name="ellipsis" size="20" @click="showMenu = true" />
      </template>
    </van-nav-bar>

    <!-- 聊天消息区域 -->
    <div class="chat-messages" ref="messagesRef">
      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="empty-state">
        <van-icon name="chat-o" size="60" color="#c8c9cc" />
        <p class="empty-title">AI助手随时为您服务</p>
        <p class="empty-desc">我可以帮您分析库存、生成报表、提供采购建议</p>
        <div class="quick-btns">
          <van-button
            v-for="cmd in quickCommands"
            :key="cmd.text"
            size="small"
            round
            plain
            type="primary"
            @click="sendMessage(cmd.text)"
          >
            {{ cmd.label }}
          </van-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="msg in messages"
        :key="msg.id"
        :class="['msg-item', `msg-${msg.role}`]"
      >
        <!-- 头像 -->
        <div :class="['msg-avatar', `avatar-${msg.role}`]">
          <van-icon
            :name="msg.role === 'user' ? 'manager-o' : 'service-o'"
            size="18"
            color="#fff"
          />
        </div>

        <!-- 消息气泡 -->
        <div class="msg-content">
          <div class="msg-bubble">
            <template v-if="msg.role === 'assistant'">
              <!-- Markdown 简易渲染 -->
              <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <!-- 流式加载动画 -->
              <div v-if="msg.isStreaming && !msg.content" class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </template>
            <template v-else>
              {{ msg.content }}
            </template>
          </div>
          <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
        </div>
      </div>

      <!-- 停止生成按钮 -->
      <div v-if="isLoading" class="stop-generation">
        <van-button
          size="small"
          round
          plain
          type="default"
          icon="cross"
          @click="stopGeneration"
        >
          停止生成
        </van-button>
      </div>
    </div>

    <!-- 底部输入区域 -->
    <div class="chat-footer">
      <!-- 快捷命令芯片 -->
      <div class="quick-chips">
        <span
          v-for="chip in quickChips"
          :key="chip"
          class="chip"
          @click="sendMessage(chip)"
        >
          {{ chip }}
        </span>
      </div>

      <!-- 输入栏 -->
      <div class="input-bar">
        <van-field
          v-model="inputText"
          placeholder="输入消息..."
          type="textarea"
          rows="1"
          autosize
          maxlength="500"
          show-word-limit
          @keyup.enter.exact="handleSend"
          class="chat-input"
        />
        <van-button
          type="primary"
          size="small"
          icon="guide-o"
          :disabled="!inputText.trim() || isLoading"
          :loading="isLoading"
          @click="handleSend"
          round
          class="send-btn"
        >
          发送
        </van-button>
      </div>
    </div>

    <!-- 更多菜单 -->
    <van-action-sheet
      v-model:show="showMenu"
      :actions="menuActions"
      cancel-text="取消"
      close-on-click-action
      @select="handleMenuAction"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useAIChat } from '@/composables/useAIChat'
import dayjs from 'dayjs'

const { messages, isLoading, sendMessage, clearHistory, stopGeneration } = useAIChat()

const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const showMenu = ref(false)

const quickCommands = [
  { label: '库存概况', text: '请给我一份库存概况报告' },
  { label: '缺货分析', text: '哪些商品库存不足，需要紧急补货？' },
  { label: '采购建议', text: '请根据当前库存情况给出采购建议' },
  { label: '销售预测', text: '帮我预测下个月的销量趋势' },
]

const quickChips = ['库存概况', '缺货分析', '采购建议']

const menuActions = [
  { name: '清空聊天记录', color: '#ee0a24' },
  { name: '导出对话', color: '#1989fa' },
]

function formatTime(timestamp: Date): string {
  return dayjs(timestamp).format('HH:mm')
}

/**
 * 简易 Markdown 渲染
 * 支持: 标题、粗体、列表、代码块、行内代码
 */
function renderMarkdown(content: string): string {
  if (!content) return ''

  let html = content
    // 转义 HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 代码块 (```...```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code-block"><code>$2</code></pre>')

  // 标题 (### ## #)
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')

  // 粗体 (**...**)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // 斜体 (*...*)
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // 行内代码 (`...`)
  html = html.replace(/`(.+?)`/g, '<code class="md-inline-code">$1</code>')

  // 无序列表 (- item)
  html = html.replace(/^- (.+)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/(<li class="md-li">.*<\/li>)/s, '<ul class="md-ul">$1</ul>')

  // 有序列表 (1. item)
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="md-li">$1</li>')

  // 换行
  html = html.replace(/\n/g, '<br/>')

  return html
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  sendMessage(text)
}

function handleClear() {
  if (messages.value.length === 0) return
  showConfirmDialog({
    title: '清空聊天记录',
    message: '确定要清空所有聊天记录吗？此操作不可恢复。',
  })
    .then(() => {
      clearHistory()
      showToast('已清空')
    })
    .catch(() => {
      // 用户取消
    })
}

function handleMenuAction(action: { name: string }) {
  if (action.name === '清空聊天记录') {
    handleClear()
  } else if (action.name === '导出对话') {
    exportChat()
  }
}

function exportChat() {
  if (messages.value.length === 0) {
    showToast('暂无对话记录')
    return
  }

  const text = messages.value
    .map((msg) => {
      const role = msg.role === 'user' ? '我' : 'AI'
      return `[${dayjs(msg.timestamp).format('YYYY-MM-DD HH:mm:ss')}] ${role}:\n${msg.content}`
    })
    .join('\n\n---\n\n')

  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AI对话_${dayjs().format('YYYYMMDD_HHmmss')}.txt`
  a.click()
  URL.revokeObjectURL(url)
  showToast('导出成功')
}

// 自动滚动到底部
watch(
  () => messages.value.length,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

// 监听最后一条消息内容变化（流式输出时滚动）
watch(
  () => {
    const last = messages.value[messages.value.length - 1]
    return last?.content?.length || 0
  },
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}
</script>

<style scoped lang="scss">
.ai-chat-mobile {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f7f8fa;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  -webkit-overflow-scrolling: touch;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60%;
  color: #969799;

  .empty-title {
    margin: 12px 0 4px;
    font-size: 16px;
    font-weight: 500;
    color: #323233;
  }

  .empty-desc {
    margin: 0 0 20px;
    font-size: 13px;
    color: #969799;
    text-align: center;
    padding: 0 40px;
  }

  .quick-btns {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }
}

.msg-item {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;

  &.msg-user {
    flex-direction: row-reverse;

    .msg-avatar {
      background: #409eff;
    }

    .msg-content {
      align-items: flex-end;
    }

    .msg-bubble {
      background: #409eff;
      color: #fff;
      border-radius: 16px 2px 16px 16px;
    }

    .msg-time {
      text-align: right;
    }
  }

  &.msg-assistant {
    .msg-avatar {
      background: #07c160;
    }

    .msg-bubble {
      background: #fff;
      color: #323233;
      border-radius: 2px 16px 16px 16px;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
    }
  }
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.msg-content {
  display: flex;
  flex-direction: column;
  max-width: 78%;
  min-width: 0;
}

.msg-bubble {
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;

  .markdown-body {
    :deep(.md-h2) {
      font-size: 16px;
      font-weight: 700;
      margin: 8px 0 4px;
    }

    :deep(.md-h3) {
      font-size: 15px;
      font-weight: 600;
      margin: 6px 0 4px;
    }

    :deep(.md-h4) {
      font-size: 14px;
      font-weight: 600;
      margin: 4px 0 2px;
    }

    :deep(.md-code-block) {
      background: #f5f5f5;
      border-radius: 6px;
      padding: 10px;
      margin: 6px 0;
      overflow-x: auto;
      font-size: 12px;
      font-family: 'Courier New', monospace;
      line-height: 1.4;
    }

    :deep(.md-inline-code) {
      background: #f0f0f0;
      padding: 1px 4px;
      border-radius: 3px;
      font-size: 12px;
      font-family: 'Courier New', monospace;
    }

    :deep(.md-ul) {
      padding-left: 16px;
      margin: 4px 0;

      .md-li {
        list-style: disc;
        margin: 2px 0;
      }
    }

    :deep(strong) {
      font-weight: 700;
    }

    :deep(em) {
      font-style: italic;
    }
  }
}

.loading-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;

  span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #969799;
    animation: dotBounce 1.4s infinite ease-in-out both;

    &:nth-child(1) {
      animation-delay: -0.32s;
    }

    &:nth-child(2) {
      animation-delay: -0.16s;
    }

    &:nth-child(3) {
      animation-delay: 0;
    }
  }
}

@keyframes dotBounce {
  0%,
  80%,
  100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.msg-time {
  font-size: 11px;
  color: #c8c9cc;
  margin-top: 4px;
  padding: 0 2px;
}

.stop-generation {
  display: flex;
  justify-content: center;
  padding: 8px 0 12px;
}

.chat-footer {
  background: #fff;
  border-top: 1px solid #ebedf0;
  padding: 8px 12px 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));

  .quick-chips {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;

    &::-webkit-scrollbar {
      display: none;
    }

    .chip {
      flex-shrink: 0;
      padding: 4px 12px;
      border-radius: 14px;
      font-size: 12px;
      color: #409eff;
      background: rgba(64, 158, 255, 0.08);
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s;

      &:active {
        background: rgba(64, 158, 255, 0.15);
      }
    }
  }

  .input-bar {
    display: flex;
    align-items: flex-end;
    gap: 8px;

    .chat-input {
      flex: 1;
      padding: 6px 10px;
      background: #f7f8fa;
      border-radius: 18px;

      :deep(.van-field__control) {
        font-size: 14px;
      }
    }

    .send-btn {
      flex-shrink: 0;
      height: 36px;
      padding: 0 14px;
    }
  }
}
</style>
