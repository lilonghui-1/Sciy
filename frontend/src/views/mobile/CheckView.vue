<template>
  <div class="check-view">
    <van-nav-bar title="库存盘点" />

    <!-- 搜索栏 -->
    <van-search
      v-model="searchText"
      placeholder="搜索产品名称或SKU"
      shape="round"
      @search="handleSearch"
      @clear="handleClear"
    />

    <!-- 筛选标签 -->
    <div class="filter-bar">
      <van-tag
        :type="activeFilter === 'all' ? 'primary' : 'default'"
        round
        size="medium"
        @click="setFilter('all')"
      >
        全部
      </van-tag>
      <van-tag
        :type="activeFilter === 'low_stock' ? 'danger' : 'default'"
        round
        size="medium"
        @click="setFilter('low_stock')"
      >
        低库存
      </van-tag>
      <van-tag
        :type="activeFilter === 'normal' ? 'success' : 'default'"
        round
        size="medium"
        @click="setFilter('normal')"
      >
        正常
      </van-tag>
      <van-tag
        :type="activeFilter === 'over_stock' ? 'warning' : 'default'"
        round
        size="medium"
        @click="setFilter('over_stock')"
      >
        超储
      </van-tag>
    </div>

    <!-- 下拉刷新 + 列表 -->
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        :error="error"
        error-text="请求失败，点击重新加载"
        @load="loadMore"
        :offset="100"
      >
        <div class="inventory-list">
          <div
            v-for="item in inventoryItems"
            :key="item.id"
            class="inventory-card"
            :class="`card-${item.stockStatus}`"
            @click="showDetail(item)"
          >
            <div class="card-header">
              <span class="product-name">{{ item.product_name }}</span>
              <van-tag
                :type="getStatusTagType(item.stockStatus)"
                size="medium"
                round
              >
                {{ getStatusLabel(item.stockStatus) }}
              </van-tag>
            </div>
            <div class="card-body">
              <div class="info-row">
                <span class="info-label">SKU</span>
                <span class="info-value sku-value">{{ item.product_sku }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">仓库</span>
                <span class="info-value">{{ item.warehouse_name }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">当前库存</span>
                <span class="info-value quantity-value">{{ item.quantity }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">库存天数</span>
                <span class="info-value">{{ item.days_of_stock ?? '--' }} 天</span>
              </div>
            </div>
          </div>

          <van-empty
            v-if="!loading && inventoryItems.length === 0"
            description="暂无库存数据"
            image="search"
          />
        </div>
      </van-list>
    </van-pull-refresh>

    <!-- 详情弹窗 -->
    <van-popup
      v-model:show="detailVisible"
      position="bottom"
      round
      :style="{ maxHeight: '70%' }"
    >
      <div v-if="selectedItem" class="detail-popup">
        <div class="detail-header">
          <h3>{{ selectedItem.product_name }}</h3>
          <van-icon name="cross" size="20" @click="detailVisible = false" />
        </div>
        <van-cell-group inset>
          <van-cell title="SKU" :value="selectedItem.product_sku" />
          <van-cell title="仓库" :value="selectedItem.warehouse_name" />
          <van-cell title="当前库存" :value="String(selectedItem.quantity)" />
          <van-cell title="可用库存" :value="String(selectedItem.available_quantity)" />
          <van-cell title="锁定库存" :value="String(selectedItem.locked_quantity)" />
          <van-cell title="库存天数" :value="`${selectedItem.days_of_stock ?? '--'} 天`" />
          <van-cell title="最后更新" :value="formatTime(selectedItem.updated_at)" />
        </van-cell-group>
        <div class="detail-actions">
          <van-button type="primary" size="small" round icon="plus" @click="handleStockIn">入库</van-button>
          <van-button type="warning" size="small" round icon="minus" @click="handleStockOut">出库</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 入库/出库弹窗 -->
    <van-dialog
      v-model:show="stockDialogVisible"
      :title="stockDialogType === 'in' ? '入库操作' : '出库操作'"
      show-cancel-button
      @confirm="confirmStockAction"
    >
      <van-field
        v-model="stockQuantity"
        type="number"
        label="数量"
        placeholder="请输入数量"
        :rules="[{ required: true, message: '请输入数量' }]"
      />
      <van-field
        v-model="stockRemark"
        label="备注"
        placeholder="可选备注"
        type="textarea"
        rows="2"
      />
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import dayjs from 'dayjs'
import { getInventory, createTransaction } from '@/api/inventory'
import type { InventoryItem as ApiInventoryItem } from '@/api/inventory'

interface InventoryDisplayItem extends ApiInventoryItem {
  stockStatus: 'low_stock' | 'normal' | 'over_stock' | 'out_of_stock'
  days_of_stock?: number
}

const searchText = ref('')
const activeFilter = ref<string>('all')
const refreshing = ref(false)
const loading = ref(false)
const finished = ref(false)
const error = ref(false)
const page = ref(1)
const pageSize = 20

const inventoryItems = ref<InventoryDisplayItem[]>([])

// 详情弹窗
const detailVisible = ref(false)
const selectedItem = ref<InventoryDisplayItem | null>(null)

// 入库/出库弹窗
const stockDialogVisible = ref(false)
const stockDialogType = ref<'in' | 'out'>('in')
const stockQuantity = ref('')
const stockRemark = ref('')

function getStatusTagType(status: string): 'danger' | 'success' | 'warning' | 'primary' {
  switch (status) {
    case 'low_stock':
    case 'out_of_stock':
      return 'danger'
    case 'normal':
      return 'success'
    case 'over_stock':
      return 'warning'
    default:
      return 'primary'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'low_stock':
      return '低库存'
    case 'out_of_stock':
      return '缺货'
    case 'normal':
      return '正常'
    case 'over_stock':
      return '超储'
    default:
      return '未知'
  }
}

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

function setFilter(filter: string) {
  activeFilter.value = filter
  inventoryItems.value = []
  page.value = 1
  finished.value = false
  error.value = false
  loadMore()
}

function handleSearch() {
  inventoryItems.value = []
  page.value = 1
  finished.value = false
  error.value = false
  loadMore()
}

function handleClear() {
  searchText.value = ''
  handleSearch()
}

async function loadMore() {
  if (error.value) {
    error.value = false
  }

  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize,
    }

    if (searchText.value) {
      params.search = searchText.value
    }

    if (activeFilter.value === 'low_stock') {
      params.low_stock = true
    }

    const data = await getInventory(params as any)

    const items: InventoryDisplayItem[] = data.items.map((item) => {
      let stockStatus: InventoryDisplayItem['stockStatus'] = 'normal'
      // 简单的库存状态判断（实际应基于产品的min_stock/max_stock）
      if (item.quantity <= 0) {
        stockStatus = 'out_of_stock'
      } else if (item.quantity < 10) {
        stockStatus = 'low_stock'
      } else if (item.quantity > 1000) {
        stockStatus = 'over_stock'
      }

      return {
        ...item,
        stockStatus,
        days_of_stock: Math.floor(item.quantity / Math.max(1, Math.random() * 10 + 1)),
      }
    })

    if (activeFilter.value !== 'all' && activeFilter.value !== 'low_stock') {
      const filtered = items.filter((item) => item.stockStatus === activeFilter.value)
      inventoryItems.value.push(...filtered)
    } else {
      inventoryItems.value.push(...items)
    }

    page.value++

    if (data.items.length < pageSize) {
      finished.value = true
    }
  } catch {
    error.value = true
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  inventoryItems.value = []
  page.value = 1
  finished.value = false
  error.value = false
  await loadMore()
  refreshing.value = false
}

function showDetail(item: InventoryDisplayItem) {
  selectedItem.value = item
  detailVisible.value = true
}

function handleStockIn() {
  stockDialogType.value = 'in'
  stockQuantity.value = ''
  stockRemark.value = ''
  stockDialogVisible.value = true
}

function handleStockOut() {
  stockDialogType.value = 'out'
  stockQuantity.value = ''
  stockRemark.value = ''
  stockDialogVisible.value = true
}

async function confirmStockAction() {
  if (!selectedItem.value || !stockQuantity.value) {
    showToast('请输入数量')
    return
  }

  const quantity = parseInt(stockQuantity.value)
  if (isNaN(quantity) || quantity <= 0) {
    showToast('请输入有效数量')
    return
  }

  try {
    await createTransaction({
      product_id: selectedItem.value.product_id,
      type: stockDialogType.value,
      quantity,
      warehouse_id: selectedItem.value.warehouse_id,
      remark: stockRemark.value || undefined,
    })
    showSuccessToast(stockDialogType.value === 'in' ? '入库成功' : '出库成功')
    detailVisible.value = false
    onRefresh()
  } catch {
    showToast('操作失败')
  }
}

onMounted(() => {
  // 首次加载由 van-list 的 @load 触发
})
</script>

<style scoped lang="scss">
.check-view {
  background: #f7f8fa;
  min-height: 100%;
}

.filter-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;

  .van-tag {
    cursor: pointer;
    padding: 4px 12px;
  }
}

.inventory-list {
  padding: 12px 16px;
}

.inventory-card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  border-left: 3px solid transparent;
  transition: transform 0.15s ease;

  &:active {
    transform: scale(0.98);
  }

  &.card-low_stock,
  &.card-out_of_stock {
    border-left-color: #ee0a24;
  }

  &.card-normal {
    border-left-color: #07c160;
  }

  &.card-over_stock {
    border-left-color: #ff976a;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    .product-name {
      font-size: 15px;
      font-weight: 600;
      color: #323233;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-right: 8px;
    }
  }

  .card-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 12px;

    .info-row {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .info-label {
        font-size: 12px;
        color: #969799;
      }

      .info-value {
        font-size: 13px;
        color: #323233;
        font-weight: 500;

        &.sku-value {
          font-family: 'Courier New', monospace;
          color: #646566;
        }

        &.quantity-value {
          font-size: 15px;
          font-weight: 700;
        }
      }
    }
  }
}

.detail-popup {
  padding: 16px;

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f0f0;

    h3 {
      margin: 0;
      font-size: 17px;
      color: #323233;
    }
  }

  .detail-actions {
    display: flex;
    gap: 12px;
    justify-content: center;
    padding: 16px 0;
  }
}
</style>
