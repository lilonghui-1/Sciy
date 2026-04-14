<template>
  <div class="ai-chat-view">
    <div class="chat-container">
      <!-- Message List -->
      <div class="message-list" ref="messageListRef">
        <!-- Empty State -->
        <div v-if="messages.length === 0" class="empty-chat">
          <el-icon :size="80" color="#c0c4cc"><ChatDotRound /></el-icon>
          <h3>AI库存助手</h3>
          <p>您好！我是AI库存管理助手，可以帮您查询库存信息、分析数据、生成报告等。</p>
          <div class="quick-commands">
            <el-button
              v-for="cmd in quickCommands"
              :key="cmd.text"
              @click="handleQuickCommand(cmd.text)"
              type="primary"
              plain
              round
              size="small"
            >
              {{ cmd.label }}
            </el-button>
          </div>
        </div>

        <!-- Messages -->
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message-item', `message-${msg.role}`]"
        >
          <div class="message-avatar">
            <el-avatar
              v-if="msg.role === 'user'"
              :size="36"
              style="background-color: #409eff"
            >
              <el-icon><User /></el-icon>
            </el-avatar>
            <el-avatar
              v-else
              :size="36"
              style="background-color: #67c23a"
            >
              <el-icon><Monitor /></el-icon>
            </el-avatar>
          </div>
          <div class="message-content">
            <div class="message-bubble" v-html="renderMarkdown(msg.content)"></div>
            <div class="message-time">
              {{ formatTime(msg.timestamp) }}
            </div>
          </div>
        </div>

        <!-- Typing Indicator -->
        <div v-if="isLoading && messages.length > 0 && !lastAssistantContent" class="typing-indicator">
          <el-avatar :size="36" style="background-color: #67c23a; margin-right: 10px; flex-shrink: 0">
            <el-icon><Monitor /></el-icon>
          </el-avatar>
          <div class="typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="chat-input">
        <div class="quick-bar" v-if="messages.length > 0">
          <el-button
            v-for="cmd in quickCommands"
            :key="cmd.text"
            @click="handleQuickCommand(cmd.text)"
            size="small"
            plain
            round
          >
            {{ cmd.label }}
          </el-button>
        </div>
        <div class="input-row">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="请输入您的问题..."
            @keydown.enter.exact.prevent="handleSend"
            resize="none"
            :disabled="isLoading"
          />
          <div class="input-actions">
            <el-button
              @click="clearHistory"
              type="danger"
              plain
              size="small"
              :icon="Delete"
              :disabled="isLoading"
            >
              清空记录
            </el-button>
            <el-button
              v-if="isLoading"
              @click="stopGeneration"
              type="warning"
              plain
              size="small"
            >
              停止生成
            </el-button>
            <el-button
              @click="handleSend"
              type="primary"
              :disabled="!inputText.trim() || isLoading"
              :icon="Promotion"
            >
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { ChatDotRound, User, Monitor, Delete, Promotion } from '@element-plus/icons-vue'
import { useAIChat } from '@/composables/useAIChat'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

const { messages, isLoading, sendMessage, clearHistory, stopGeneration } = useAIChat()

const inputText = ref('')
const messageListRef = ref<HTMLElement | null>(null)

const quickCommands = [
  { label: '库存概况分析', text: '请帮我分析当前库存概况，包括总库存价值、各类别占比、异常情况等' },
  { label: '滞销品分析', text: '请分析当前哪些产品属于滞销品，给出滞销品清单和处理建议' },
  { label: '缺货风险评估', text: '请评估当前所有产品的缺货风险，列出高风险产品并给出补货优先级' },
  { label: '生成采购建议', text: '请根据当前库存水平和预测需求，生成一份采购建议清单' },
]

const lastAssistantContent = computed(() => {
  const last = messages.value[messages.value.length - 1]
  return last?.role === 'assistant' ? last.content : ''
})

function renderMarkdown(content: string): string {
  if (!content) return ''
  return md.render(content)
}

function formatTime(timestamp: Date): string {
  const date = new Date(timestamp)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()

  if (isToday) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  sendMessage(text)
}

function handleQuickCommand(text: string) {
  sendMessage(text)
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// Auto-scroll on new messages
watch(
  () => messages.value.length,
  () => {
    scrollToBottom()
  }
)

// Auto-scroll on content change (streaming)
watch(
  () => lastAssistantContent.value,
  () => {
    scrollToBottom()
  }
)
</script>

<style scoped lang="scss">
.ai-chat-view {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;

  h3 {
    margin: 16px 0 8px;
    font-size: 20px;
    color: #303133;
  }

  p {
    font-size: 14px;
    max-width: 400px;
    text-align: center;
    line-height: 1.6;
  }

  .quick-commands {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 24px;
    justify-content: center;
  }
}

.message-item {
  display: flex;
  margin-bottom: 20px;

  &.message-user {
    flex-direction: row-reverse;

    .message-content {
      align-items: flex-end;
    }

    .message-bubble {
      background-color: #409eff;
      color: #fff;
      border-radius: 12px 2px 12px 12px;
    }

    .message-time {
      text-align: right;
    }
  }

  &.message-assistant {
    .message-bubble {
      background-color: #f4f4f5;
      color: #303133;
      border-radius: 2px 12px 12px 12px;
    }
  }

  .message-avatar {
    margin: 0 10px;
    flex-shrink: 0;
  }

  .message-content {
    display: flex;
    flex-direction: column;
    max-width: 70%;
  }

  .message-bubble {
    padding: 12px 16px;
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;

    :deep(p) {
      margin: 0 0 8px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
      margin: 12px 0 8px;
      font-weight: 600;
    }

    :deep(h1) { font-size: 18px; }
    :deep(h2) { font-size: 16px; }
    :deep(h3) { font-size: 15px; }

    :deep(ul), :deep(ol) {
      padding-left: 20px;
      margin: 8px 0;
    }

    :deep(li) {
      margin: 4px 0;
    }

    :deep(pre) {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 13px;
      margin: 8px 0;
    }

    :deep(code) {
      font-family: 'Fira Code', 'Consolas', 'Monaco', monospace;
    }

    :deep(:not(pre) > code) {
      background: #f0f0f0;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 13px;
      color: #c7254e;
    }

    :deep(blockquote) {
      border-left: 4px solid #dcdfe6;
      padding-left: 12px;
      margin: 8px 0;
      color: #909399;
    }

    :deep(table) {
      border-collapse: collapse;
      width: 100%;
      margin: 8px 0;

      th, td {
        border: 1px solid #dcdfe6;
        padding: 8px 12px;
        text-align: left;
        font-size: 13px;
      }

      th {
        background-color: #f5f7fa;
        font-weight: 600;
      }
    }

    :deep(a) {
      color: #409eff;
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }

    :deep(hr) {
      border: none;
      border-top: 1px solid #e4e7ed;
      margin: 12px 0;
    }

    :deep(strong) {
      font-weight: 600;
    }
  }

  .message-time {
    font-size: 12px;
    color: #c0c4cc;
    margin-top: 4px;
  }
}

.typing-indicator {
  display: flex;
  align-items: center;
  margin-bottom: 20px;

  .typing-dots {
    display: flex;
    gap: 4px;
    padding: 12px 16px;
    background: #f4f4f5;
    border-radius: 2px 12px 12px 12px;

    span {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: #c0c4cc;
      animation: typing 1.4s infinite ease-in-out;

      &:nth-child(2) {
        animation-delay: 0.2s;
      }

      &:nth-child(3) {
        animation-delay: 0.4s;
      }
    }
  }
}

@keyframes typing {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-8px);
    opacity: 1;
  }
}

.chat-input {
  border-top: 1px solid #e6e6e6;
  padding: 12px 16px;
  background: #fafafa;

  .quick-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #ebeef5;
  }

  .input-row {
    display: flex;
    gap: 12px;
    align-items: flex-end;

    .el-textarea {
      flex: 1;
    }
  }

  .input-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex-shrink: 0;
  }
}
</style>
