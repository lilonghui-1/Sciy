<template>
  <div class="import-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>数据导入</h2>
      <el-button type="primary" :icon="Download" @click="handleDownloadTemplate">
        下载导入模板
      </el-button>
    </div>

    <!-- 上传区域 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="never" class="upload-card">
          <template #header>
            <div class="card-header">
              <span>导入产品数据</span>
              <el-tag type="info" size="small">.xlsx / .csv</el-tag>
            </div>
          </template>
          <el-upload
            ref="productUploadRef"
            drag
            :action="uploadAction"
            :headers="uploadHeaders"
            :data="{ type: 'products' }"
            accept=".xlsx,.xls,.csv"
            :show-file-list="true"
            :limit="1"
            :on-success="handleProductSuccess"
            :on-error="handleUploadError"
            :on-exceed="handleExceed"
            :before-upload="beforeUpload"
            :on-progress="handleProgress"
            class="upload-area"
          >
            <div class="upload-content">
              <el-icon :size="48" color="#c0c4cc"><Upload /></el-icon>
              <div class="el-upload__text">
                将文件拖到此处，或<em>点击上传</em>
              </div>
              <div class="el-upload__tip">
                支持 .xlsx、.xls、.csv 格式，单次最大10MB
              </div>
            </div>
          </el-upload>

          <!-- 导入结果 -->
          <div v-if="productImportResult" class="import-result">
            <el-result
              :icon="productImportResult.success ? 'success' : 'error'"
              :title="productImportResult.success ? '导入完成' : '导入失败'"
              :sub-title="`成功: ${productImportResult.successCount} 条，失败: ${productImportResult.failedCount} 条`"
            >
              <template #extra>
                <el-button
                  v-if="productImportResult.errors && productImportResult.errors.length > 0"
                  type="primary"
                  link
                  @click="showProductErrors = !showProductErrors"
                >
                  {{ showProductErrors ? '收起错误详情' : '查看错误详情' }}
                </el-button>
              </template>
            </el-result>
            <div v-if="showProductErrors && productImportResult.errors" class="error-list">
              <el-table
                :data="productImportResult.errors"
                size="small"
                max-height="200"
                stripe
              >
                <el-table-column prop="row" label="行号" width="80" />
                <el-table-column prop="field" label="字段" width="120" />
                <el-table-column prop="message" label="错误信息" min-width="200" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never" class="upload-card">
          <template #header>
            <div class="card-header">
              <span>导入库存数据</span>
              <el-tag type="info" size="small">.xlsx / .csv</el-tag>
            </div>
          </template>
          <el-upload
            ref="inventoryUploadRef"
            drag
            :action="uploadAction"
            :headers="uploadHeaders"
            :data="{ type: 'inventory' }"
            accept=".xlsx,.xls,.csv"
            :show-file-list="true"
            :limit="1"
            :on-success="handleInventorySuccess"
            :on-error="handleUploadError"
            :on-exceed="handleExceed"
            :before-upload="beforeUpload"
            :on-progress="handleProgress"
            class="upload-area"
          >
            <div class="upload-content">
              <el-icon :size="48" color="#c0c4cc"><Upload /></el-icon>
              <div class="el-upload__text">
                将文件拖到此处，或<em>点击上传</em>
              </div>
              <div class="el-upload__tip">
                支持 .xlsx、.xls、.csv 格式，单次最大10MB
              </div>
            </div>
          </el-upload>

          <!-- 导入结果 -->
          <div v-if="inventoryImportResult" class="import-result">
            <el-result
              :icon="inventoryImportResult.success ? 'success' : 'error'"
              :title="inventoryImportResult.success ? '导入完成' : '导入失败'"
              :sub-title="`成功: ${inventoryImportResult.successCount} 条，失败: ${inventoryImportResult.failedCount} 条`"
            >
              <template #extra>
                <el-button
                  v-if="inventoryImportResult.errors && inventoryImportResult.errors.length > 0"
                  type="primary"
                  link
                  @click="showInventoryErrors = !showInventoryErrors"
                >
                  {{ showInventoryErrors ? '收起错误详情' : '查看错误详情' }}
                </el-button>
              </template>
            </el-result>
            <div v-if="showInventoryErrors && inventoryImportResult.errors" class="error-list">
              <el-table
                :data="inventoryImportResult.errors"
                size="small"
                max-height="200"
                stripe
              >
                <el-table-column prop="row" label="行号" width="80" />
                <el-table-column prop="field" label="字段" width="120" />
                <el-table-column prop="message" label="错误信息" min-width="200" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 导入历史 -->
    <el-card shadow="never" class="history-card">
      <template #header>
        <div class="card-header">
          <span>导入历史</span>
          <el-button type="primary" link size="small" @click="fetchImportHistory">
            刷新
          </el-button>
        </div>
      </template>
      <el-table
        :data="importHistory"
        style="width: 100%"
        v-loading="loadingHistory"
        empty-text="暂无导入记录"
        stripe
        :default-sort="{ prop: 'created_at', order: 'descending' }"
      >
        <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 'products' ? 'primary' : 'success'" size="small">
              {{ row.type === 'products' ? '产品' : '库存' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'success' ? 'success' : row.status === 'partial' ? 'warning' : 'danger'"
              size="small"
              effect="dark"
            >
              {{ row.status === 'success' ? '成功' : row.status === 'partial' ? '部分成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_rows" label="总行数" width="80" align="center" />
        <el-table-column prop="success_count" label="成功" width="80" align="center">
          <template #default="{ row }">
            <span class="text-success">{{ row.success_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_count" label="失败" width="80" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.error_count > 0 }">{{ row.error_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="created_at" label="导入时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.error_count > 0"
              type="primary"
              link
              size="small"
              @click="viewHistoryErrors(row)"
            >
              错误详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper" v-if="historyTotal > historyPageSize">
        <el-pagination
          v-model:current-page="historyPage"
          :page-size="historyPageSize"
          :total="historyTotal"
          layout="total, prev, pager, next"
          @current-change="fetchImportHistory"
          small
        />
      </div>
    </el-card>

    <!-- 错误详情弹窗 -->
    <el-dialog
      v-model="errorDialogVisible"
      title="导入错误详情"
      width="600px"
      destroy-on-close
    >
      <el-table
        :data="errorDialogData"
        size="small"
        stripe
        max-height="400"
      >
        <el-table-column prop="row" label="行号" width="80" />
        <el-table-column prop="field" label="字段" width="120" />
        <el-table-column prop="value" label="值" width="150" show-overflow-tooltip />
        <el-table-column prop="message" label="错误信息" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Download } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import request from '@/api/request'

const uploadAction = computed(() => {
  return `${import.meta.env.VITE_API_BASE_URL || '/api'}/import/upload`
})

const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

// 上传引用
const productUploadRef = ref<any>(null)
const inventoryUploadRef = ref<any>(null)

// 导入结果
interface ImportResult {
  success: boolean
  successCount: number
  failedCount: number
  errors: Array<{ row: number; field: string; value?: string; message: string }>
}

const productImportResult = ref<ImportResult | null>(null)
const inventoryImportResult = ref<ImportResult | null>(null)
const showProductErrors = ref(false)
const showInventoryErrors = ref(false)

// 导入历史
const importHistory = ref<any[]>([])
const loadingHistory = ref(false)
const historyPage = ref(1)
const historyTotal = ref(0)
const historyPageSize = 20

// 错误详情弹窗
const errorDialogVisible = ref(false)
const errorDialogData = ref<any[]>([])

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

function beforeUpload(file: File): boolean {
  const allowedTypes = [
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'text/csv',
    'application/csv',
  ]
  const allowedExtensions = ['.xlsx', '.xls', '.csv']
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

  if (!allowedExtensions.includes(ext)) {
    ElMessage.error('仅支持 .xlsx、.xls、.csv 格式文件')
    return false
  }

  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过10MB')
    return false
  }

  return true
}

function handleProgress() {
  // 上传进度处理
}

function handleExceed() {
  ElMessage.warning('只能上传一个文件，请先移除已选文件')
}

function handleProductSuccess(response: any) {
  if (response.success !== undefined) {
    productImportResult.value = {
      success: response.failed_count === 0,
      successCount: response.success_count || 0,
      failedCount: response.failed_count || 0,
      errors: response.errors || [],
    }
    if (response.failed_count === 0) {
      ElMessage.success('产品数据导入成功')
    } else {
      ElMessage.warning(`导入完成，${response.failed_count} 条记录失败`)
    }
    fetchImportHistory()
  } else {
    ElMessage.error('导入响应格式异常')
  }
}

function handleInventorySuccess(response: any) {
  if (response.success !== undefined) {
    inventoryImportResult.value = {
      success: response.failed_count === 0,
      successCount: response.success_count || 0,
      failedCount: response.failed_count || 0,
      errors: response.errors || [],
    }
    if (response.failed_count === 0) {
      ElMessage.success('库存数据导入成功')
    } else {
      ElMessage.warning(`导入完成，${response.failed_count} 条记录失败`)
    }
    fetchImportHistory()
  } else {
    ElMessage.error('导入响应格式异常')
  }
}

function handleUploadError() {
  ElMessage.error('文件上传失败，请检查网络后重试')
}

async function handleDownloadTemplate() {
  try {
    const token = localStorage.getItem('token')
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
    const response = await fetch(`${baseUrl}/import/template`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })

    if (!response.ok) {
      throw new Error('下载失败')
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '库存导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch {
    ElMessage.error('模板下载失败')
  }
}

function viewHistoryErrors(row: any) {
  errorDialogData.value = row.errors || []
  errorDialogVisible.value = true
}

async function fetchImportHistory() {
  loadingHistory.value = true
  try {
    const data = await request.get<any, {
      items: any[]
      total: number
    }>('/import/history', {
      params: {
        page: historyPage.value,
        page_size: historyPageSize,
      },
    })
    importHistory.value = data.items || []
    historyTotal.value = data.total || 0
  } catch {
    // 静默处理
  } finally {
    loadingHistory.value = false
  }
}

onMounted(() => {
  fetchImportHistory()
})
</script>

<style scoped lang="scss">
.import-view {
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
  }

  .upload-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .upload-area {
      :deep(.el-upload-dragger) {
        padding: 30px;
        border-radius: 8px;

        .upload-content {
          display: flex;
          flex-direction: column;
          align-items: center;

          .el-upload__text {
            margin-top: 12px;
            font-size: 14px;
            color: #606266;

            em {
              color: #409eff;
              font-style: normal;
            }
          }

          .el-upload__tip {
            margin-top: 8px;
            font-size: 12px;
            color: #909399;
          }
        }
      }
    }

    .import-result {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #f0f0f0;

      .error-list {
        margin-top: 12px;
      }
    }
  }

  .history-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .text-success {
      color: #67c23a;
      font-weight: 600;
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
