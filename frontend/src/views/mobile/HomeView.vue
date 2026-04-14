<template>
  <div class="home-view">
    <!-- 顶部标题栏 -->
    <div class="home-header">
      <div class="header-top">
        <h2 class="app-title">库存智能管理</h2>
        <van-tag :type="wsConnected ? 'success' : 'danger'" plain size="medium">
          {{ wsConnected ? '已连接' : '未连接' }}
        </van-tag>
      </div>
      <p class="header-date">{{ currentDate }}</p>
    </div>

    <!-- 下拉刷新 -->
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh" success-text="刷新成功">
      <!-- 汇总卡片 2x2 网格 -->
      <van-grid :column-num="2" :border="false" :gutter="10" class="summary-grid">
        <van-grid-item>
          <div class="summary-card card-products">
            <div class="card-icon">
              <van-icon name="goods-collect" size="24" />
            </div>
            <div class="card-info">
              <div class="card-value">{{ summary.totalProducts }}</div>
              <div class="card-label">总产品数</div>
            </div>
          </div>
        </van-grid-item>
        <van-grid-item>
          <div class="summary-card card-value">
            <div class="card-icon">
              <van-icon name="balance-o" size="24" />
            </div>
            <div class="card-info">
              <div class="card-value">{{ formatMoney(summary.totalValue) }}</div>
              <div class="card-label">库存总值</div>
            </div>
          </div>
        </van-grid-item>
        <van-grid-item>
          <div class="summary-card card-alerts">
            <div class="card-icon">
              <van-icon name="bell" size="24" />
            </div>
            <div class="card-info">
              <div class="card-value">{{ summary.pendingAlerts }}</div>
              <div class="card-label">待处理告警</div>
            </div>
          </div>
        </van-grid-item>
        <van-grid-item>
          <div class="summary-card card-lowstock">
            <div class="card-icon">
              <van-icon name="warning-o" size="24" />
            </div>
            <div class="card-info">
              <div class="card-value">{{ summary.lowStockItems }}</div>
              <div class="card-label">低库存数</div>
            </div>
          </div>
        </van-grid-item>
      </van-grid>

      <!-- 快捷操作按钮 -->
      <div class="section">
        <div class="section-header">
          <h3>快捷操作</h3>
        </div>
        <van-grid :column-num="4" :border="false" class="action-grid">
          <van-grid-item icon="scan" text="扫码查询" @click="$router.push('/mobile/scan')" />
          <van-grid-item icon="orders-o" text="库存盘点" @click="$router.push('/mobile/check')" />
          <van-grid-item icon="bell" text="查看告警" @click="$router.push('/mobile/alerts')" />
          <van-grid-item icon="chat-o" text="AI助手" @click="$router.push('/mobile/chat')" />
        </van-grid>
      </div>

      <!-- 最近告警列表 -->
      <div class="section">
        <div class="section-header">
          <h3>最近告警</h3>
          <span class="view-all" @click="$router.push('/mobile/alerts')">查看全部</span>
        </div>
        <van-cell-group inset>
          <van-cell
            v-for="alert in recentAlerts"
            :key="alert.id"
            :title="alert.rule_name || alert.message"
            :label="formatTime(alert.created_at)"
            is-link
          >
            <template #icon>
              <van-icon
                :name="getSeverityIcon(alert.severity)"
                :color="getSeverityColor(alert.severity)"
                size="20"
                class="alert-icon"
              />
            </template>
            <template #value>
              <van-tag
                :type="alert.severity === 'critical' ? 'danger' : alert.severity === 'warning' ? 'warning' : 'primary'"
                size="medium"
              >
                {{ getSeverityLabel(alert.severity) }}
              </van-tag>
            </template>
          </van-cell>
          <van-cell v-if="recentAlerts.length === 0" title="暂无告警" center>
            <template #icon>
              <van-icon name="smile-o" size="20" color="#969799" class="alert-icon" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import dayjs from 'dayjs'
import { useWebSocket } from '@/composables/useWebSocket'
import { getAlertEvents } from '@/api/alerts'
import type { AlertEvent } from '@/api/alerts'
import request from '@/api/request'

interface SummaryData {
  totalProducts: number
  totalValue: number
  pendingAlerts: number
  lowStockItems: number
}

const router = useRouter()
const refreshing = ref(false)
const summary = reactive<SummaryData>({
  totalProducts: 0,
  totalValue: 0,
  pendingAlerts: 0,
  lowStockItems: 0,
})

const currentDate = computed(() => {
  return dayjs().format('YYYY年MM月DD日 dddd')
})

interface AlertItem {
  id: number
  severity: 'info' | 'warning' | 'critical'
  rule_name: string
  message: string
  product_name: string
  created_at: string
}

const recentAlerts = ref<AlertItem[]>([])

// WebSocket 实时连接
const {
  isConnected: wsConnected,
  connect: wsConnect,
  disconnect: wsDisconnect,
} = useWebSocket({
  url: '/ws/inventory',
  onMessage: (data) => {
    handleWsMessage(data)
  },
  onOpen: () => {
    console.log('WebSocket已连接')
  },
  onClose: () => {
    console.log('WebSocket已断开')
  },
})

function handleWsMessage(data: any) {
  if (data.type === 'alert') {
    showToast({
      message: `新告警: ${data.message || data.product_name || '库存异常'}`,
      position: 'top',
      type: 'warning',
    })
    // 刷新告警列表
    fetchRecentAlerts()
    // 更新待处理告警数
    summary.pendingAlerts++
  } else if (data.type === 'inventory_update') {
    fetchSummary()
  } else if (data.type === 'sync_complete') {
    showToast({
      message: '数据同步完成',
      position: 'top',
      type: 'success',
    })
    fetchSummary()
  }
}

function getSeverityIcon(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'warning'
    case 'warning':
      return 'info-o'
    default:
      return 'comment-o'
  }
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return '#ee0a24'
    case 'warning':
      return '#ff976a'
    default:
      return '#1989fa'
  }
}

function getSeverityLabel(severity: string): string {
  switch (severity) {
    case 'critical':
      return '严重'
    case 'warning':
      return '警告'
    default:
      return '提示'
  }
}

function formatTime(time: string): string {
  return dayjs(time).format('MM-DD HH:mm')
}

function formatMoney(value: number): string {
  if (value >= 100000000) {
    return `¥${(value / 100000000).toFixed(2)}亿`
  }
  if (value >= 10000) {
    return `¥${(value / 10000).toFixed(1)}万`
  }
  return `¥${value.toLocaleString()}`
}

async function fetchSummary() {
  try {
    const data = await request.get<any, {
      total_products: number
      total_value: number
      pending_alerts: number
      low_stock_items: number
    }>('/dashboard/summary')
    summary.totalProducts = data.total_products || 0
    summary.totalValue = data.total_value || 0
    summary.pendingAlerts = data.pending_alerts || 0
    summary.lowStockItems = data.low_stock_items || 0
  } catch {
    // 静默处理，使用默认值
  }
}

async function fetchRecentAlerts() {
  try {
    const data = await getAlertEvents({
      page: 1,
      page_size: 5,
      acknowledged: false,
    })
    recentAlerts.value = data.items.map((item: AlertEvent) => ({
      id: item.id,
      severity: item.severity,
      rule_name: item.rule_name,
      message: item.message,
      product_name: item.product_name,
      created_at: item.created_at,
    }))
  } catch {
    // 静默处理
  }
}

async function onRefresh() {
  try {
    await Promise.all([fetchSummary(), fetchRecentAlerts()])
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  fetchSummary()
  fetchRecentAlerts()
  wsConnect()
})

onUnmounted(() => {
  wsDisconnect()
})
</script>

<style scoped lang="scss">
.home-view {
  padding: 16px;
  background-color: #f7f8fa;
  min-height: 100%;
}

.home-header {
  padding: 10px 0 20px;

  .header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .app-title {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: #323233;
  }

  .header-date {
    margin: 6px 0 0;
    font-size: 13px;
    color: #969799;
  }
}

.summary-grid {
  margin-bottom: 16px;
  padding: 0;

  :deep(.van-grid-item__content) {
    padding: 0;
  }
}

.summary-card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  width: 100%;

  .card-icon {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 10px;
    flex-shrink: 0;
  }

  .card-info {
    flex: 1;
    min-width: 0;

    .card-value {
      font-size: 20px;
      font-weight: 700;
      color: #323233;
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .card-label {
      font-size: 12px;
      color: #969799;
      margin-top: 2px;
    }
  }

  &.card-products .card-icon {
    background: rgba(64, 158, 255, 0.1);
    color: #409eff;
  }

  &.card-value .card-icon {
    background: rgba(103, 194, 58, 0.1);
    color: #67c23a;
  }

  &.card-alerts .card-icon {
    background: rgba(230, 162, 60, 0.1);
    color: #e6a23c;
  }

  &.card-lowstock .card-icon {
    background: rgba(245, 108, 108, 0.1);
    color: #f56c6c;
  }
}

.section {
  margin-bottom: 20px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding: 0 4px;

    h3 {
      margin: 0;
      font-size: 16px;
      color: #323233;
      font-weight: 600;
    }

    .view-all {
      font-size: 13px;
      color: #409eff;
      cursor: pointer;
    }
  }
}

.action-grid {
  background: #fff;
  border-radius: 12px;
  padding: 8px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

  :deep(.van-grid-item__icon) {
    color: #409eff;
    font-size: 24px;
  }

  :deep(.van-grid-item__text) {
    margin-top: 8px;
    font-size: 12px;
    color: #323233;
  }
}

.alert-icon {
  margin-right: 10px;
  line-height: inherit;
}
</style>
