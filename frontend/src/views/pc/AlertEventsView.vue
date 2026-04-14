<template>
  <div class="alert-events-view">
    <div class="page-header">
      <h2>告警事件</h2>
      <div class="header-actions">
        <el-button
          type="warning"
          :icon="Check"
          :disabled="selectedEvents.length === 0"
          @click="handleBatchAcknowledge"
        >
          批量确认 ({{ selectedEvents.length }})
        </el-button>
        <el-button :icon="Refresh" @click="fetchEvents">刷新</el-button>
      </div>
    </div>

    <!-- Filters -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="5">
          <el-select
            v-model="filterSeverity"
            placeholder="严重程度"
            clearable
            @change="fetchEvents"
          >
            <el-option label="严重" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select
            v-model="filterStatus"
            placeholder="状态"
            clearable
            @change="fetchEvents"
          >
            <el-option label="新告警" value="new" />
            <el-option label="已确认" value="acknowledged" />
            <el-option label="已解决" value="resolved" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-date-picker
            v-model="filterDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            @change="fetchEvents"
          />
        </el-col>
        <el-col :span="6">
          <el-button type="primary" :icon="Search" @click="fetchEvents">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Events Table -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-table
        ref="tableRef"
        :data="events"
        v-loading="loading"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="rule_name" label="规则名称" width="150" show-overflow-tooltip />
        <el-table-column prop="product_name" label="产品" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.product_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度" width="100" align="center">
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
        <el-table-column prop="message" label="告警消息" min-width="250" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              :type="getStatusTagType(row.status || (row.acknowledged ? 'acknowledged' : 'new'))"
              size="small"
            >
              {{ getStatusLabel(row.status || (row.acknowledged ? 'acknowledged' : 'new')) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="getEventStatus(row) === 'new'"
              size="small"
              type="primary"
              link
              @click="handleAcknowledge(row.id)"
            >
              确认
            </el-button>
            <el-button
              v-if="getEventStatus(row) !== 'resolved'"
              size="small"
              type="success"
              link
              @click="handleResolve(row.id)"
            >
              解决
            </el-button>
            <span v-if="getEventStatus(row) === 'resolved'" style="color: #909399; font-size: 13px">
              已处理
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="fetchEvents"
          @current-change="fetchEvents"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Check, Search } from '@element-plus/icons-vue'
import type { ElTable } from 'element-plus'
import {
  getAlertEvents,
  acknowledgeAlert,
  type AlertEvent,
} from '@/api/alerts'
import request from '@/api/request'

// --- State ---
const events = ref<AlertEvent[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const filterSeverity = ref('')
const filterStatus = ref('')
const filterDateRange = ref<string[]>([])

const selectedEvents = ref<AlertEvent[]>([])
const tableRef = ref<InstanceType<typeof ElTable> | null>(null)

// --- API ---
async function fetchEvents() {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      severity: filterSeverity.value || undefined,
      status: filterStatus.value || undefined,
      start_date: filterDateRange.value?.[0] || undefined,
      end_date: filterDateRange.value?.[1] || undefined,
    }
    const res = await getAlertEvents(params)
    events.value = res.items || []
    total.value = res.total || 0
  } catch (err) {
    console.error('获取告警事件失败:', err)
    ElMessage.error('获取告警事件失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filterSeverity.value = ''
  filterStatus.value = ''
  filterDateRange.value = []
  currentPage.value = 1
  fetchEvents()
}

function handleSelectionChange(selection: AlertEvent[]) {
  selectedEvents.value = selection
}

function getEventStatus(row: AlertEvent): string {
  return (row as any).status || (row.acknowledged ? 'acknowledged' : 'new')
}

async function handleAcknowledge(id: number) {
  try {
    await acknowledgeAlert(id)
    ElMessage.success('告警已确认')
    fetchEvents()
  } catch (err: any) {
    console.error('确认告警失败:', err)
    ElMessage.error(err?.response?.data?.message || '确认告警失败')
  }
}

async function handleResolve(id: number) {
  try {
    await request.post(`/alerts/events/${id}/resolve`)
    ElMessage.success('告警已解决')
    fetchEvents()
  } catch (err: any) {
    console.error('解决告警失败:', err)
    ElMessage.error(err?.response?.data?.message || '解决告警失败')
  }
}

async function handleBatchAcknowledge() {
  const newEvents = selectedEvents.value.filter(
    (e) => getEventStatus(e) === 'new'
  )
  if (newEvents.length === 0) {
    ElMessage.warning('所选事件中没有新告警')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要批量确认 ${newEvents.length} 条新告警吗？`,
      '批量确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )

    const ids = newEvents.map((e) => e.id)
    await request.post('/alerts/events/batch-acknowledge', { event_ids: ids })
    ElMessage.success(`已确认 ${ids.length} 条告警`)
    fetchEvents()
  } catch (err: any) {
    if (err !== 'cancel') {
      console.error('批量确认失败:', err)
      ElMessage.error('批量确认失败')
    }
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
  fetchEvents()
})
</script>

<style scoped lang="scss">
.alert-events-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  .filter-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #ebeef5;
  }
}
</style>
