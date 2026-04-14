<template>
  <div class="dashboard-view">
    <!-- KPI Cards -->
    <el-row :gutter="20" class="kpi-row">
      <el-col :span="6">
        <el-card shadow="hover" class="kpi-card kpi-products">
          <div class="kpi-icon">
            <el-icon :size="40"><Goods /></el-icon>
          </div>
          <div class="kpi-info">
            <div class="kpi-value">{{ kpiData.totalProducts }}</div>
            <div class="kpi-label">总产品数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="kpi-card kpi-value">
          <div class="kpi-icon">
            <el-icon :size="40"><Money /></el-icon>
          </div>
          <div class="kpi-info">
            <div class="kpi-value">{{ formatMoney(kpiData.totalInventoryValue) }}</div>
            <div class="kpi-label">库存总价值</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="kpi-card kpi-alerts">
          <div class="kpi-icon">
            <el-icon :size="40"><Bell /></el-icon>
          </div>
          <div class="kpi-info">
            <div class="kpi-value">{{ kpiData.activeAlerts }}</div>
            <div class="kpi-label">活跃告警数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="kpi-card kpi-lowstock">
          <div class="kpi-icon">
            <el-icon :size="40"><Warning /></el-icon>
          </div>
          <div class="kpi-info">
            <div class="kpi-value">{{ kpiData.lowStockItems }}</div>
            <div class="kpi-label">低库存产品数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>库存趋势（近30天）</span>
              <el-tag v-if="wsConnected" type="success" size="small" effect="plain">
                实时连接
              </el-tag>
              <el-tag v-else type="info" size="small" effect="plain">
                未连接
              </el-tag>
            </div>
          </template>
          <v-chart
            class="trend-chart"
            :option="trendChartOption"
            :loading="trendLoading"
            autoresize
          />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>告警分布</span>
          </template>
          <v-chart
            class="pie-chart"
            :option="pieChartOption"
            :loading="pieLoading"
            autoresize
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Alerts Table -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近告警</span>
              <el-button type="primary" link @click="fetchAlertEvents">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <el-table
            :data="recentAlerts"
            v-loading="alertsLoading"
            stripe
            style="width: 100%"
          >
            <el-table-column prop="created_at" label="时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="rule_name" label="规则名称" width="160" />
            <el-table-column prop="product_name" label="产品名称" width="160" />
            <el-table-column prop="severity" label="严重程度" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="getSeverityTagType(row.severity)"
                  size="small"
                  effect="dark"
                >
                  {{ getSeverityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="告警消息" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="getStatusTagType(row.status)"
                  size="small"
                >
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import {
  Goods,
  Money,
  Bell,
  Warning,
  Refresh,
} from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart as PieChartType } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import request from '@/api/request'
import { useWebSocket } from '@/composables/useWebSocket'

use([
  CanvasRenderer,
  LineChart,
  PieChartType,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

// --- Types ---
interface KpiData {
  totalProducts: number
  totalInventoryValue: number
  activeAlerts: number
  lowStockItems: number
}

interface AlertEvent {
  id: number
  rule_id: number
  rule_name: string
  product_id: number
  product_name: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info' | 'warning'
  message: string
  status: 'new' | 'acknowledged' | 'resolved'
  acknowledged: boolean
  created_at: string
}

interface TrendDataPoint {
  date: string
  total_quantity: number
  total_value: number
}

// --- State ---
const kpiData = reactive<KpiData>({
  totalProducts: 0,
  totalInventoryValue: 0,
  activeAlerts: 0,
  lowStockItems: 0,
})

const recentAlerts = ref<AlertEvent[]>([])
const trendLoading = ref(false)
const pieLoading = ref(false)
const alertsLoading = ref(false)
const trendData = ref<TrendDataPoint[]>([])

const wsConnected = ref(false)

// --- WebSocket ---
const { connect: wsConnect, disconnect: wsDisconnect, isConnected } = useWebSocket({
  url: `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/alerts`,
  onMessage: (data: any) => {
    // 收到实时告警，刷新数据
    if (data.type === 'alert' || data.type === 'alert_event') {
      fetchAlertEvents()
      fetchOverview()
    }
  },
  onOpen: () => {
    wsConnected.value = true
  },
  onClose: () => {
    wsConnected.value = false
  },
})

// --- ECharts Options ---
const trendChartOption = computed(() => {
  const dates = trendData.value.map((d) => d.date)
  const quantities = trendData.value.map((d) => d.total_quantity)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: {
        formatter: (val: string) => {
          const parts = val.split('-')
          return `${parts[1]}-${parts[2]}`
        },
      },
    },
    yAxis: {
      type: 'value',
      name: '库存数量',
    },
    series: [
      {
        name: '库存数量',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: quantities,
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64,158,255,0.3)' },
              { offset: 1, color: 'rgba(64,158,255,0.02)' },
            ],
          },
        },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      },
    ],
  }
})

const pieChartOption = computed(() => {
  // 统计告警分布
  const severityMap: Record<string, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  }
  recentAlerts.value.forEach((a) => {
    const s = a.severity as string
    if (severityMap[s] !== undefined) {
      severityMap[s]++
    } else if (s === 'warning') {
      severityMap['high']++
    } else if (s === 'info') {
      severityMap['low']++
    }
  })

  const data = [
    { value: severityMap.critical, name: '严重', itemStyle: { color: '#f56c6c' } },
    { value: severityMap.high, name: '高', itemStyle: { color: '#e6a23c' } },
    { value: severityMap.medium, name: '中', itemStyle: { color: '#409eff' } },
    { value: severityMap.low, name: '低', itemStyle: { color: '#67c23a' } },
  ].filter((d) => d.value > 0)

  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle',
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        avoidLabelOverlap: false,
        label: {
          show: true,
          formatter: '{b}\n{d}%',
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold',
          },
        },
        data,
      },
    ],
  }
})

// --- API Calls ---
async function fetchOverview() {
  try {
    const res: any = await request.get('/inventory/snapshots/overview')
    kpiData.totalProducts = res.total_products ?? res.totalProducts ?? 0
    kpiData.totalInventoryValue = res.total_inventory_value ?? res.totalInventoryValue ?? 0
    kpiData.activeAlerts = res.active_alerts ?? res.activeAlerts ?? 0
    kpiData.lowStockItems = res.low_stock_items ?? res.lowStockItems ?? 0
  } catch (err) {
    console.error('获取概览数据失败:', err)
  }
}

async function fetchTrendData() {
  trendLoading.value = true
  try {
    const res: any = await request.get('/inventory/snapshots/trend', {
      params: { days: 30 },
    })
    trendData.value = res.items ?? res.data ?? res ?? []
  } catch (err) {
    console.error('获取趋势数据失败:', err)
    // 生成模拟趋势数据作为后备
    generateMockTrendData()
  } finally {
    trendLoading.value = false
  }
}

function generateMockTrendData() {
  const now = new Date()
  const data: TrendDataPoint[] = []
  let base = 5000
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    base += Math.floor(Math.random() * 400 - 180)
    data.push({
      date: d.toISOString().split('T')[0],
      total_quantity: base,
      total_value: base * 15.6,
    })
  }
  trendData.value = data
}

async function fetchAlertEvents() {
  alertsLoading.value = true
  try {
    const res: any = await request.get('/alerts/events', {
      params: { page_size: 10, sort_by: 'created_at', sort_order: 'desc' },
    })
    recentAlerts.value = res.items ?? res.data ?? res ?? []
  } catch (err) {
    console.error('获取告警事件失败:', err)
  } finally {
    alertsLoading.value = false
  }
}

// --- Helpers ---
function formatMoney(value: number): string {
  if (value >= 100000000) {
    return `¥${(value / 100000000).toFixed(2)}亿`
  }
  if (value >= 10000) {
    return `¥${(value / 10000).toFixed(2)}万`
  }
  return `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDateTime(dt: string): string {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function getSeverityTagType(severity: string): 'danger' | 'warning' | 'info' | 'success' {
  const map: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
    critical: 'danger',
    high: 'warning',
    medium: 'info',
    low: 'success',
    warning: 'warning',
    info: 'success',
  }
  return map[severity] || 'info'
}

function getSeverityLabel(severity: string): string {
  const map: Record<string, string> = {
    critical: '严重',
    high: '高',
    medium: '中',
    low: '低',
    warning: '警告',
    info: '信息',
  }
  return map[severity] || severity
}

function getStatusTagType(status: string): 'danger' | 'warning' | 'success' {
  const map: Record<string, 'danger' | 'warning' | 'success'> = {
    new: 'danger',
    acknowledged: 'warning',
    resolved: 'success',
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    new: '新告警',
    acknowledged: '已确认',
    resolved: '已解决',
  }
  return map[status] || status
}

// --- Lifecycle ---
onMounted(() => {
  fetchOverview()
  fetchTrendData()
  fetchAlertEvents()
  wsConnect()
})

onUnmounted(() => {
  wsDisconnect()
})
</script>

<style scoped lang="scss">
.dashboard-view {
  padding: 0;
}

.kpi-row {
  .kpi-card {
    display: flex;
    align-items: center;
    padding: 20px;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.3s;

    &:hover {
      transform: translateY(-4px);
    }

    .kpi-icon {
      width: 70px;
      height: 70px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-right: 16px;
      flex-shrink: 0;
    }

    .kpi-info {
      flex: 1;

      .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #303133;
        line-height: 1.2;
      }

      .kpi-label {
        font-size: 14px;
        color: #909399;
        margin-top: 4px;
      }
    }

    &.kpi-products .kpi-icon {
      background: rgba(64, 158, 255, 0.1);
      color: #409eff;
    }

    &.kpi-value .kpi-icon {
      background: rgba(103, 194, 58, 0.1);
      color: #67c23a;
    }

    &.kpi-alerts .kpi-icon {
      background: rgba(230, 162, 60, 0.1);
      color: #e6a23c;
    }

    &.kpi-lowstock .kpi-icon {
      background: rgba(245, 108, 108, 0.1);
      color: #f56c6c;
    }
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trend-chart {
  height: 320px;
  width: 100%;
}

.pie-chart {
  height: 320px;
  width: 100%;
}
</style>
