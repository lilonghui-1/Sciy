<template>
  <div class="inventory-view">
    <div class="page-header">
      <h2>库存管理</h2>
      <el-button type="primary" :icon="Plus" @click="openTransactionDialog">
        新增事务
      </el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- 库存概览 Tab -->
      <el-tab-pane label="库存概览" name="overview">
        <!-- Filters -->
        <el-card shadow="never" class="filter-card">
          <el-row :gutter="16" align="middle">
            <el-col :span="8">
              <el-input
                v-model="snapshotSearch"
                placeholder="搜索产品名称或SKU..."
                clearable
                :prefix-icon="Search"
                @clear="fetchSnapshots"
                @keyup.enter="fetchSnapshots"
              />
            </el-col>
            <el-col :span="6">
              <el-select
                v-model="snapshotWarehouse"
                placeholder="选择仓库"
                clearable
                @change="fetchSnapshots"
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
              <el-button type="primary" :icon="Search" @click="fetchSnapshots">搜索</el-button>
              <el-button @click="resetSnapshotFilters">重置</el-button>
            </el-col>
          </el-row>
        </el-card>

        <el-card shadow="never" style="margin-top: 16px">
          <el-table
            :data="snapshots"
            v-loading="snapshotLoading"
            stripe
            style="width: 100%"
          >
            <el-table-column prop="product_sku" label="产品SKU" width="130" />
            <el-table-column prop="product_name" label="产品名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="warehouse_name" label="仓库" width="120" />
            <el-table-column prop="quantity" label="在库数量" width="100" align="right">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.quantity <= row.min_stock }">
                  {{ row.quantity }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="locked_quantity" label="预留数量" width="100" align="right">
              <template #default="{ row }">
                {{ row.locked_quantity ?? row.reserved_quantity ?? 0 }}
              </template>
            </el-table-column>
            <el-table-column prop="available_quantity" label="可用数量" width="100" align="right">
              <template #default="{ row }">
                <span class="text-success">{{ row.available_quantity }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="inventory_value" label="库存价值" width="120" align="right">
              <template #default="{ row }">
                ¥{{ row.inventory_value?.toFixed(2) || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.updated_at) }}
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="snapshotPage"
              v-model:page-size="snapshotPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="snapshotTotal"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="fetchSnapshots"
              @current-change="fetchSnapshots"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 出入库记录 Tab -->
      <el-tab-pane label="出入库记录" name="transactions">
        <!-- Filters -->
        <el-card shadow="never" class="filter-card">
          <el-row :gutter="16" align="middle">
            <el-col :span="6">
              <el-input
                v-model="txProductSearch"
                placeholder="搜索产品..."
                clearable
                :prefix-icon="Search"
                @clear="fetchTransactions"
                @keyup.enter="fetchTransactions"
              />
            </el-col>
            <el-col :span="5">
              <el-select
                v-model="txWarehouse"
                placeholder="仓库"
                clearable
                @change="fetchTransactions"
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
              <el-select
                v-model="txType"
                placeholder="事务类型"
                clearable
                @change="fetchTransactions"
              >
                <el-option label="入库" value="in" />
                <el-option label="出库" value="out" />
                <el-option label="调整" value="adjustment" />
                <el-option label="调拨" value="transfer" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-date-picker
                v-model="txDateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                @change="fetchTransactions"
              />
            </el-col>
            <el-col :span="3">
              <el-button type="primary" :icon="Search" @click="fetchTransactions">搜索</el-button>
            </el-col>
          </el-row>
        </el-card>

        <el-card shadow="never" style="margin-top: 16px">
          <el-table
            :data="transactions"
            v-loading="txLoading"
            stripe
            style="width: 100%"
          >
            <el-table-column prop="created_at" label="时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="product_name" label="产品" min-width="140" show-overflow-tooltip />
            <el-table-column prop="warehouse_name" label="仓库" width="120">
              <template #default="{ row }">
                {{ row.warehouse_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="getTxTypeTag(row.type)" size="small">
                  {{ getTxTypeLabel(row.type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量变化" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.type === 'in' ? 'text-success' : 'text-danger'">
                  {{ row.type === 'in' ? '+' : '-' }}{{ Math.abs(row.quantity) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="previous_quantity" label="变化前" width="90" align="right">
              <template #default="{ row }">
                {{ row.previous_quantity ?? '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="new_quantity" label="变化后" width="90" align="right">
              <template #default="{ row }">
                {{ row.new_quantity ?? '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="reference_no" label="参考号" width="140" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.reference_no || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="operator" label="操作人" width="100" />
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="txPage"
              v-model:page-size="txPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="txTotal"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="fetchTransactions"
              @current-change="fetchTransactions"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- New Transaction Dialog -->
    <el-dialog
      v-model="txDialogVisible"
      title="新增事务"
      width="560px"
      destroy-on-close
      @close="resetTxForm"
    >
      <el-form
        ref="txFormRef"
        :model="txFormData"
        :rules="txFormRules"
        label-width="100px"
      >
        <el-form-item label="产品" prop="product_id">
          <el-select
            v-model="txFormData.product_id"
            placeholder="请选择产品"
            filterable
            remote
            :remote-method="searchProducts"
            :loading="productSearchLoading"
            style="width: 100%"
          >
            <el-option
              v-for="p in productOptions"
              :key="p.id"
              :label="`${p.sku} - ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库" prop="warehouse_id">
          <el-select
            v-model="txFormData.warehouse_id"
            placeholder="请选择仓库"
            style="width: 100%"
          >
            <el-option
              v-for="wh in warehouses"
              :key="wh.id"
              :label="wh.name"
              :value="wh.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="txFormData.type" placeholder="请选择类型" style="width: 100%">
            <el-option label="入库" value="in" />
            <el-option label="出库" value="out" />
            <el-option label="调整" value="adjustment" />
            <el-option label="调拨" value="transfer" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number
            v-model="txFormData.quantity"
            :min="1"
            :step="1"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="参考号" prop="reference_no">
          <el-input v-model="txFormData.reference_no" placeholder="请输入参考号（可选）" />
        </el-form-item>
        <el-form-item label="原因" prop="remark">
          <el-input
            v-model="txFormData.remark"
            type="textarea"
            :rows="3"
            placeholder="请输入原因说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="txDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="txSubmitLoading" @click="handleCreateTransaction">
          确认提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  getInventory,
  getTransactions,
  createTransaction,
  type InventoryItem,
  type Transaction,
  type CreateTransactionParams,
} from '@/api/inventory'
import { getProducts, type Product } from '@/api/products'
import request from '@/api/request'

// --- Types ---
interface Warehouse {
  id: number
  name: string
}

// --- State ---
const activeTab = ref('overview')

// Snapshots
const snapshots = ref<any[]>([])
const snapshotLoading = ref(false)
const snapshotSearch = ref('')
const snapshotWarehouse = ref<number | undefined>()
const snapshotPage = ref(1)
const snapshotPageSize = ref(20)
const snapshotTotal = ref(0)

// Transactions
const transactions = ref<Transaction[]>([])
const txLoading = ref(false)
const txProductSearch = ref('')
const txWarehouse = ref<number | undefined>()
const txType = ref('')
const txDateRange = ref<string[]>([])
const txPage = ref(1)
const txPageSize = ref(20)
const txTotal = ref(0)

// Warehouses
const warehouses = ref<Warehouse[]>([])

// Transaction Dialog
const txDialogVisible = ref(false)
const txSubmitLoading = ref(false)
const txFormRef = ref<FormInstance | null>(null)
const productOptions = ref<Product[]>([])
const productSearchLoading = ref(false)

const txFormData = reactive<CreateTransactionParams>({
  product_id: 0,
  type: 'in',
  quantity: 1,
  warehouse_id: undefined,
  reference_no: '',
  remark: '',
})

const txFormRules: FormRules = {
  product_id: [{ required: true, message: '请选择产品', trigger: 'change' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

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

async function fetchSnapshots() {
  snapshotLoading.value = true
  try {
    const params: any = {
      page: snapshotPage.value,
      page_size: snapshotPageSize.value,
      search: snapshotSearch.value || undefined,
      warehouse_id: snapshotWarehouse.value || undefined,
    }
    const res = await getInventory(params)
    snapshots.value = (res as any).items || []
    snapshotTotal.value = (res as any).total || 0
  } catch (err) {
    console.error('获取库存概览失败:', err)
    ElMessage.error('获取库存概览失败')
  } finally {
    snapshotLoading.value = false
  }
}

async function fetchTransactions() {
  txLoading.value = true
  try {
    const params: any = {
      page: txPage.value,
      page_size: txPageSize.value,
      product_id: undefined,
      type: txType.value || undefined,
      start_date: txDateRange.value?.[0] || undefined,
      end_date: txDateRange.value?.[1] || undefined,
    }
    const res = await getTransactions(params)
    transactions.value = res.items || []
    txTotal.value = res.total || 0
  } catch (err) {
    console.error('获取事务记录失败:', err)
    ElMessage.error('获取事务记录失败')
  } finally {
    txLoading.value = false
  }
}

function resetSnapshotFilters() {
  snapshotSearch.value = ''
  snapshotWarehouse.value = undefined
  snapshotPage.value = 1
  fetchSnapshots()
}

function handleTabChange() {
  if (activeTab.value === 'overview') {
    fetchSnapshots()
  } else {
    fetchTransactions()
  }
}

// Transaction Dialog
function openTransactionDialog() {
  txDialogVisible.value = true
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

async function handleCreateTransaction() {
  if (!txFormRef.value) return
  await txFormRef.value.validate(async (valid) => {
    if (!valid) return
    txSubmitLoading.value = true
    try {
      await createTransaction({
        product_id: txFormData.product_id,
        type: txFormData.type,
        quantity: txFormData.quantity,
        warehouse_id: txFormData.warehouse_id,
        reference_no: txFormData.reference_no || undefined,
        remark: txFormData.remark || undefined,
      })
      ElMessage.success('事务创建成功')
      txDialogVisible.value = false
      fetchSnapshots()
      fetchTransactions()
    } catch (err: any) {
      console.error('创建事务失败:', err)
      ElMessage.error(err?.response?.data?.message || '创建事务失败')
    } finally {
      txSubmitLoading.value = false
    }
  })
}

function resetTxForm() {
  Object.assign(txFormData, {
    product_id: 0,
    type: 'in',
    quantity: 1,
    warehouse_id: undefined,
    reference_no: '',
    remark: '',
  })
  productOptions.value = []
  txFormRef.value?.resetFields()
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

function getTxTypeTag(type: string): 'success' | 'danger' | 'warning' | 'info' {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    in: 'success',
    out: 'danger',
    adjustment: 'warning',
    transfer: 'info',
  }
  return map[type] || 'info'
}

function getTxTypeLabel(type: string): string {
  const map: Record<string, string> = {
    in: '入库',
    out: '出库',
    adjustment: '调整',
    transfer: '调拨',
  }
  return map[type] || type
}

// --- Lifecycle ---
onMounted(() => {
  fetchWarehouses()
  fetchSnapshots()
})
</script>

<style scoped lang="scss">
.inventory-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
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

  .text-success {
    color: #67c23a;
    font-weight: 600;
  }

  .text-danger {
    color: #f56c6c;
    font-weight: 600;
  }
}
</style>
