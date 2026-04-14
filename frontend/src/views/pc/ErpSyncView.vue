<template>
  <div class="erp-sync-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>ERP同步管理</h2>
      <div class="header-actions">
        <el-select v-model="syncType" size="default" style="width: 120px; margin-right: 12px">
          <el-option label="全量同步" value="full" />
          <el-option label="增量同步" value="incremental" />
        </el-select>
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="syncing"
          @click="handleSync"
        >
          立即同步
        </el-button>
      </div>
    </div>

    <!-- 状态卡片 -->
    <el-row :gutter="20" class="status-cards">
      <el-col :span="8">
        <el-card shadow="never" class="status-card">
          <div class="card-icon-wrapper icon-connect">
            <el-icon :size="28"><Connection /></el-icon>
          </div>
          <div class="card-content">
            <div class="card-label">ERP连接状态</div>
            <div class="card-value">
              <el-tag :type="erpStatus.connected ? 'success' : 'danger'" effect="dark" size="small">
                {{ erpStatus.connected ? '已连接' : '未连接' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="status-card">
          <div class="card-icon-wrapper icon-time">
            <el-icon :size="28"><Clock /></el-icon>
          </div>
          <div class="card-content">
            <div class="card-label">最后同步时间</div>
            <div class="card-value">{{ erpStatus.lastSyncTime || '--' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="status-card">
          <div class="card-icon-wrapper icon-freq">
            <el-icon :size="28"><Timer /></el-icon>
          </div>
          <div class="card-content">
            <div class="card-label">同步频率</div>
            <div class="card-value">{{ erpConfig.syncInterval ? `每 ${erpConfig.syncInterval} 分钟` : '未配置' }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ERP配置 -->
    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <span>ERP配置</span>
        </div>
      </template>
      <el-form
        ref="configFormRef"
        :model="erpConfig"
        :rules="configRules"
        label-width="120px"
        class="config-form"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="API地址" prop="apiUrl">
              <el-input
                v-model="erpConfig.apiUrl"
                placeholder="请输入ERP API地址"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="API密钥" prop="apiKey">
              <el-input
                v-model="erpConfig.apiKey"
                placeholder="请输入API密钥"
                clearable
                show-password
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="同步间隔(分钟)" prop="syncInterval">
              <el-input-number
                v-model="erpConfig.syncInterval"
                :min="1"
                :max="1440"
                :step="5"
                placeholder="同步间隔"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="操作">
              <el-button type="primary" :loading="savingConfig" @click="handleSaveConfig">
                保存配置
              </el-button>
              <el-button
                type="success"
                plain
                :loading="testingConnection"
                @click="handleTestConnection"
              >
                测试连接
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 同步日志 -->
    <el-card shadow="never" class="log-card">
      <template #header>
        <div class="card-header">
          <span>同步日志</span>
          <el-button type="primary" link size="small" @click="fetchSyncLogs">
            刷新
          </el-button>
        </div>
      </template>
      <el-table
        :data="syncLogs"
        style="width: 100%"
        v-loading="loadingLogs"
        empty-text="暂无同步记录"
        stripe
        :default-sort="{ prop: 'created_at', order: 'descending' }"
      >
        <el-table-column prop="created_at" label="时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 'full' ? 'warning' : 'primary'" size="small">
              {{ row.type === 'full' ? '全量' : '增量' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="direction" label="方向" width="100">
          <template #default="{ row }">
            <span>{{ row.direction === 'pull' ? '拉取' : row.direction === 'push' ? '推送' : '双向' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="getStatusType(row.status)"
              size="small"
              effect="dark"
            >
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="processed_count" label="处理记录数" width="120" align="center" />
        <el-table-column prop="failed_count" label="失败数" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.failed_count > 0 }">
              {{ row.failed_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="100" align="center">
          <template #default="{ row }">
            {{ row.duration ? `${row.duration}s` : '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="message" label="备注" min-width="200" show-overflow-tooltip />
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper" v-if="logTotal > pageSize">
        <el-pagination
          v-model:current-page="logPage"
          :page-size="pageSize"
          :total="logTotal"
          layout="total, prev, pager, next"
          @current-change="fetchSyncLogs"
          small
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Connection, Clock, Timer } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import request from '@/api/request'

// 同步类型
const syncType = ref<'full' | 'incremental'>('incremental')
const syncing = ref(false)

// ERP状态
const erpStatus = reactive({
  connected: false,
  lastSyncTime: '',
})

// ERP配置
const erpConfig = reactive({
  apiUrl: '',
  apiKey: '',
  syncInterval: 30,
})

const configFormRef = ref<FormInstance | null>(null)
const savingConfig = ref(false)
const testingConnection = ref(false)

const configRules: FormRules = {
  apiUrl: [
    { required: true, message: '请输入API地址', trigger: 'blur' },
    { type: 'url', message: '请输入有效的URL', trigger: 'blur' },
  ],
  apiKey: [
    { required: true, message: '请输入API密钥', trigger: 'blur' },
  ],
  syncInterval: [
    { required: true, message: '请输入同步间隔', trigger: 'blur' },
  ],
}

// 同步日志
const syncLogs = ref<any[]>([])
const loadingLogs = ref(false)
const logPage = ref(1)
const logTotal = ref(0)
const pageSize = 20

interface SyncLogItem {
  id: number
  type: 'full' | 'incremental'
  direction: 'pull' | 'push' | 'bidirectional'
  status: 'success' | 'failed' | 'running' | 'partial'
  processed_count: number
  failed_count: number
  duration: number
  message: string
  created_at: string
}

function getStatusType(status: string): 'success' | 'danger' | 'warning' | 'info' {
  switch (status) {
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'running':
      return 'warning'
    case 'partial':
      return 'warning'
    default:
      return 'info'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'success':
      return '成功'
    case 'failed':
      return '失败'
    case 'running':
      return '进行中'
    case 'partial':
      return '部分成功'
    default:
      return '未知'
  }
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

async function handleSync() {
  syncing.value = true
  try {
    await request.post('/erp/sync', {
      type: syncType.value,
    })
    ElMessage.success(`${syncType.value === 'full' ? '全量' : '增量'}同步已启动`)
    // 延迟刷新日志
    setTimeout(() => {
      fetchSyncLogs()
      fetchErpStatus()
    }, 2000)
  } catch {
    // 错误已在拦截器中处理
  } finally {
    syncing.value = false
  }
}

async function handleSaveConfig() {
  if (!configFormRef.value) return
  try {
    await configFormRef.value.validate()
  } catch {
    return
  }

  savingConfig.value = true
  try {
    await request.put('/erp/config', {
      api_url: erpConfig.apiUrl,
      api_key: erpConfig.apiKey,
      sync_interval: erpConfig.syncInterval,
    })
    ElMessage.success('配置保存成功')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    savingConfig.value = false
  }
}

async function handleTestConnection() {
  testingConnection.value = true
  try {
    const result = await request.post<any, { success: boolean; message: string }>('/erp/test-connection', {
      api_url: erpConfig.apiUrl,
      api_key: erpConfig.apiKey,
    })
    if (result.success) {
      ElMessage.success('连接测试成功')
      erpStatus.connected = true
    } else {
      ElMessage.error(`连接测试失败: ${result.message}`)
      erpStatus.connected = false
    }
  } catch {
    erpStatus.connected = false
  } finally {
    testingConnection.value = false
  }
}

async function fetchErpStatus() {
  try {
    const data = await request.get<any, {
      connected: boolean
      last_sync_time: string
    }>('/erp/status')
    erpStatus.connected = data.connected || false
    erpStatus.lastSyncTime = data.last_sync_time
      ? dayjs(data.last_sync_time).format('YYYY-MM-DD HH:mm:ss')
      : ''
  } catch {
    // 静默处理
  }
}

async function fetchErpConfig() {
  try {
    const data = await request.get<any, {
      api_url: string
      api_key: string
      sync_interval: number
    }>('/erp/config')
    erpConfig.apiUrl = data.api_url || ''
    erpConfig.apiKey = data.api_key || ''
    erpConfig.syncInterval = data.sync_interval || 30
  } catch {
    // 静默处理
  }
}

async function fetchSyncLogs() {
  loadingLogs.value = true
  try {
    const data = await request.get<any, {
      items: SyncLogItem[]
      total: number
    }>('/erp/sync-logs', {
      params: {
        page: logPage.value,
        page_size: pageSize,
      },
    })
    syncLogs.value = data.items || []
    logTotal.value = data.total || 0
  } catch {
    // 静默处理
  } finally {
    loadingLogs.value = false
  }
}

onMounted(() => {
  fetchErpStatus()
  fetchErpConfig()
  fetchSyncLogs()
})
</script>

<style scoped lang="scss">
.erp-sync-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    h2 {
      margin: 0;
      font-size: 20px;
      color: #303133;
    }

    .header-actions {
      display: flex;
      align-items: center;
    }
  }

  .status-cards {
    margin-bottom: 20px;

    .status-card {
      :deep(.el-card__body) {
        display: flex;
        align-items: center;
        padding: 20px;
      }

      .card-icon-wrapper {
        width: 56px;
        height: 56px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 16px;
        flex-shrink: 0;

        &.icon-connect {
          background: rgba(103, 194, 58, 0.1);
          color: #67c23a;
        }

        &.icon-time {
          background: rgba(64, 158, 255, 0.1);
          color: #409eff;
        }

        &.icon-freq {
          background: rgba(230, 162, 60, 0.1);
          color: #e6a23c;
        }
      }

      .card-content {
        .card-label {
          font-size: 14px;
          color: #909399;
          margin-bottom: 4px;
        }

        .card-value {
          font-size: 16px;
          font-weight: 600;
          color: #303133;
        }
      }
    }
  }

  .config-card {
    margin-bottom: 20px;
  }

  .log-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .text-danger {
      color: #f56c6c;
      font-weight: 600;
    }

    .pagination-wrapper {
      display: flex;
      justify-content: flex-end;
      margin-top: 16px;
    }
  }
}
</style>
