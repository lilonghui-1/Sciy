<template>
  <div class="forecasts-view">
    <div class="page-header">
      <h2>预测分析</h2>
    </div>

    <!-- Controls -->
    <el-card shadow="never" class="control-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select
            v-model="selectedProduct"
            placeholder="选择产品"
            filterable
            remote
            :remote-method="searchProducts"
            :loading="productSearchLoading"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="p in productOptions"
              :key="p.id"
              :label="`${p.sku} - ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select
            v-model="selectedWarehouse"
            placeholder="选择仓库"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="wh in warehouses"
              :key="wh.id"
              :label="wh.name"
              :value="wh.id"
            />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="forecastDays" style="width: 100%">
            <el-option label="7天" :value="7" />
            <el-option label="14天" :value="14" />
            <el-option label="30天" :value="30" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="selectedModel" placeholder="预测模型" style="width: 100%">
            <el-option label="自动选择" value="auto" />
            <el-option label="SMA (简单移动平均)" value="sma" />
            <el-option label="EMA (指数移动平均)" value="ema" />
            <el-option label="Holt-Winters" value="holt_winters" />
            <el-option label="ARIMA" value="arima" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button
            type="primary"
            :icon="TrendCharts"
            :loading="forecastRunning"
            :disabled="!selectedProduct"
            @click="handleRunForecast"
          >
            运行预测
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Chart -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>需求预测图表</span>
          <el-tag v-if="forecastResult" type="success" size="small" effect="plain">
            模型: {{ forecastResult.model_name || selectedModel }}
          </el-tag>
        </div>
      </template>
      <v-chart
        v-if="hasChartData"
        class="forecast-chart"
        :option="forecastChartOption"
        :loading="forecastRunning"
        autoresize
      />
      <div v-else class="chart-placeholder">
        <el-icon :size="60" color="#c0c4cc"><TrendCharts /></el-icon>
        <p>选择产品后运行预测，图表将在此处展示</p>
      </div>
    </el-card>

    <!-- Safety Stock & Reorder Point Cards -->
    <el-row :gutter="20" style="margin-top: 16px" v-if="forecastResult">
      <el-col :span="8">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">安全库存</div>
          <div class="metric-value text-primary">{{ forecastResult.safety_stock ?? '-' }}</div>
          <div class="metric-desc">基于预测需求波动计算</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">再订货点</div>
          <div class="metric-value text-warning">{{ forecastResult.reorder_point ?? '-' }}</div>
          <div class="metric-desc">安全库存 + 提前期内需求</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">预测准确率</div>
          <div class="metric-value text-success">{{ forecastResult.accuracy ?? '-' }}</div>
          <div class="metric-desc">基于历史数据回测</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Forecast Results Table -->
    <el-card shadow="never" style="margin-top: 16px" v-if="forecastItems.length > 0">
      <template #header>
        <span>预测结果明细</span>
      </template>
      <el-table :data="forecastItems" stripe style="width: 100%">
        <el-table-column prop="forecast_date" label="预测日期" width="120" />
        <el-table-column prop="predicted_demand" label="预测需求" width="100" align="right" />
        <el-table-column prop="lower_bound" label="置信下限" width="100" align="right" />
        <el-table-column prop="upper_bound" label="置信上限" width="100" align="right" />
        <el-table-column prop="confidence" label="置信度" width="100" align="center">
          <template #default="{ row }">
            {{ (row.confidence * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="使用模型" width="140" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  runForecast,
  getForecasts,
  type ForecastData,
  type RunForecastResult,
} from '@/api/forecasts'
import { getProducts, type Product } from '@/api/products'
import request from '@/api/request'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

// --- Types ---
interface Warehouse {
  id: number
  name: string
}

interface HistoricalDemand {
  date: string
  demand: number
}

// --- State ---
const selectedProduct = ref<number | undefined>()
const selectedWarehouse = ref<number | undefined>()
const forecastDays = ref(14)
const selectedModel = ref('auto')
const forecastRunning = ref(false)

const productOptions = ref<Product[]>([])
const productSearchLoading = ref(false)
const warehouses = ref<Warehouse[]>([])

const forecastResult = ref<RunForecastResult | null>(null)
const forecastItems = ref<ForecastData[]>([])
const historicalData = ref<HistoricalDemand[]>([])

// --- Chart ---
const hasChartData = computed(() => {
  return historicalData.value.length > 0 || forecastItems.value.length > 0
})

const forecastChartOption = computed(() => {
  const histDates = historicalData.value.map((d) => d.date)
  const histDemands = historicalData.value.map((d) => d.demand)

  const forecastDates = forecastItems.value.map((f) => f.forecast_date)
  const predictedDemands = forecastItems.value.map((f) => f.predicted_demand)
  const lowerBounds = forecastItems.value.map((f) => f.lower_bound)
  const upperBounds = forecastItems.value.map((f) => f.upper_bound)

  // Combine dates
  const allDates = [...histDates, ...forecastDates]

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['实际需求', '预测需求', '置信区间'],
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
      data: allDates,
      axisLabel: {
        formatter: (val: string) => {
          const parts = val.split('-')
          return `${parts[1]}-${parts[2]}`
        },
      },
    },
    yAxis: {
      type: 'value',
      name: '需求量',
    },
    series: [
      {
        name: '实际需求',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: histDemands,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      },
      {
        name: '预测需求',
        type: 'line',
        smooth: true,
        symbol: 'diamond',
        symbolSize: 6,
        data: [
          ...Array(histDates.length).fill(null),
          ...predictedDemands,
        ],
        lineStyle: { color: '#e6a23c', width: 2, type: 'dashed' },
        itemStyle: { color: '#e6a23c' },
      },
      {
        name: '置信区间',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: [
          ...Array(histDates.length).fill(null),
          ...upperBounds,
        ],
        lineStyle: { opacity: 0 },
        areaStyle: {
          color: 'rgba(230,162,60,0.15)',
        },
        stack: 'confidence-band',
      },
      {
        name: '置信下限',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: [
          ...Array(histDates.length).fill(null),
          ...lowerBounds.map((lb, i) => upperBounds[i] - lb),
        ],
        lineStyle: { opacity: 0 },
        areaStyle: {
          color: 'rgba(230,162,60,0.15)',
        },
        stack: 'confidence-band',
      },
    ],
  }
})

// --- API ---
async function fetchWarehouses() {
  try {
    const res: any = await request.get('/warehouses')
    warehouses.value = res.items ?? res.data ?? res ?? []
  } catch (err) {
    console.error('获取仓库列表失败:', err)
    warehouses.value = []
  }
}

async function searchProducts(query: string) {
  if (!query) {
    productOptions.value = []
    return
  }
  productSearchLoading.value = true
  try {
    const res = await getProducts({ search: query, page_size: 20 })
    productOptions.value = res.items || []
  } catch (err) {
    console.error('搜索产品失败:', err)
  } finally {
    productSearchLoading.value = false
  }
}

async function handleRunForecast() {
  if (!selectedProduct.value) {
    ElMessage.warning('请先选择产品')
    return
  }

  forecastRunning.value = true
  try {
    const params: any = {
      product_id: selectedProduct.value,
      days: forecastDays.value,
      model: selectedModel.value,
    }
    if (selectedWarehouse.value) {
      params.warehouse_id = selectedWarehouse.value
    }

    const res = await runForecast(params)
    forecastResult.value = res

    // Fetch forecast results
    await fetchForecastResults()

    // Fetch historical demand for chart
    await fetchHistoricalDemand()

    ElMessage.success('预测完成')
  } catch (err: any) {
    console.error('运行预测失败:', err)
    ElMessage.error(err?.response?.data?.message || '运行预测失败')
  } finally {
    forecastRunning.value = false
  }
}

async function fetchForecastResults() {
  if (!selectedProduct.value) return
  try {
    const res = await getForecasts({
      product_id: selectedProduct.value,
      page_size: forecastDays.value,
    })
    forecastItems.value = res.items || []
  } catch (err) {
    console.error('获取预测结果失败:', err)
  }
}

async function fetchHistoricalDemand() {
  if (!selectedProduct.value) return
  try {
    const res: any = await request.get('/forecasts/historical', {
      params: {
        product_id: selectedProduct.value,
        days: 30,
      },
    })
    historicalData.value = res.items ?? res.data ?? res ?? []
  } catch (err) {
    console.error('获取历史需求数据失败:', err)
    historicalData.value = []
  }
}

// --- Helpers ---
function formatDateTime(dt: string): string {
  if (!dt) return '-'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// --- Lifecycle ---
onMounted(() => {
  fetchWarehouses()
})
</script>

<style scoped lang="scss">
.forecasts-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .control-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .forecast-chart {
    height: 400px;
    width: 100%;
  }

  .chart-placeholder {
    height: 400px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #c0c4cc;

    p {
      margin-top: 12px;
      font-size: 14px;
    }
  }

  .metric-card {
    text-align: center;

    .metric-label {
      font-size: 14px;
      color: #909399;
      margin-bottom: 8px;
    }

    .metric-value {
      font-size: 32px;
      font-weight: 700;
      line-height: 1.2;
    }

    .metric-desc {
      font-size: 12px;
      color: #c0c4cc;
      margin-top: 8px;
    }

    .text-primary {
      color: #409eff;
    }

    .text-warning {
      color: #e6a23c;
    }

    .text-success {
      color: #67c23a;
    }
  }
}
</style>
