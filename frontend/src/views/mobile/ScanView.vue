<template>
  <div class="scan-view">
    <van-nav-bar title="扫码查询" />

    <!-- 摄像头扫码区域 -->
    <div class="scan-area">
      <video ref="videoRef" class="scan-video" autoplay playsinline muted></video>
      <div class="scan-overlay">
        <div class="scan-frame">
          <div class="scan-line"></div>
        </div>
        <p class="scan-hint">将条形码/二维码放入框内</p>
      </div>

      <!-- 手电筒切换按钮 -->
      <div v-if="isScanning" class="torch-btn" @click="handleToggleTorch">
        <van-icon
          :name="torchEnabled ? 'bulb' : 'bulb-o'"
          :color="torchEnabled ? '#ff976a' : '#fff'"
          size="24"
        />
      </div>
    </div>

    <!-- 扫码控制按钮 -->
    <div class="scan-actions">
      <van-button
        v-if="!isScanning"
        type="primary"
        block
        round
        size="large"
        icon="scan"
        @click="handleStartScan"
      >
        开始扫码
      </van-button>
      <van-button
        v-else
        type="danger"
        block
        round
        size="large"
        @click="handleStopScan"
      >
        停止扫码
      </van-button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="scan-error">
      <van-notice-bar color="#ee0a24" background="#ffeef0" :text="error" left-icon="warning-o" />
    </div>

    <!-- 手动输入区域 -->
    <div class="manual-input-section">
      <div class="section-title">
        <van-divider :style="{ color: '#969799', borderColor: '#ebedf0', margin: '0' }">
          或手动输入SKU
        </van-divider>
      </div>
      <div class="manual-input-row">
        <van-field
          v-model="manualSku"
          placeholder="请输入SKU编码"
          clearable
          size="large"
          @keyup.enter="handleManualSearch"
        />
        <van-button
          type="primary"
          size="small"
          round
          icon="search"
          :disabled="!manualSku.trim()"
          :loading="isLoadingProduct"
          @click="handleManualSearch"
        >
          查询
        </van-button>
      </div>
    </div>

    <!-- 扫码结果 - 产品信息卡片 -->
    <div v-if="result && !isScanning" class="scan-result">
      <div class="result-header">
        <van-icon name="checked" color="#07c160" size="20" />
        <span class="result-title">扫码结果</span>
        <van-tag type="primary" plain size="medium">{{ result.format }}</van-tag>
      </div>
      <van-cell-group inset class="result-cells">
        <van-cell title="编码" :value="result.text" />
      </van-cell-group>
    </div>

    <!-- 产品信息加载中 -->
    <div v-if="isLoadingProduct" class="product-loading">
      <van-loading size="24px" vertical>查询产品信息中...</van-loading>
    </div>

    <!-- 产品信息卡片 -->
    <div v-if="productInfo" class="product-card">
      <div class="product-header">
        <van-icon name="goods-collect" color="#409eff" size="22" />
        <span class="product-name">{{ productInfo.name }}</span>
      </div>
      <van-cell-group inset>
        <van-cell title="SKU" :value="productInfo.sku" />
        <van-cell title="仓库" :value="productInfo.warehouse_name || '--'" />
        <van-cell title="当前库存">
          <template #value>
            <span class="stock-value" :class="`stock-${productInfo.status}`">
              {{ productInfo.quantity }}
            </span>
          </template>
        </van-cell>
        <van-cell title="库存状态">
          <template #value>
            <van-tag
              :type="getStockTagType(productInfo.status)"
              size="medium"
              round
            >
              {{ getStockStatusLabel(productInfo.status) }}
            </van-tag>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- 快捷操作 -->
      <div class="product-actions">
        <van-button
          type="success"
          size="small"
          round
          icon="plus"
          @click="handleStockIn"
        >
          入库
        </van-button>
        <van-button
          type="warning"
          size="small"
          round
          icon="minus"
          @click="handleStockOut"
        >
          出库
        </van-button>
        <van-button
          type="primary"
          size="small"
          round
          icon="description"
          @click="handleViewDetail"
        >
          查看详情
        </van-button>
      </div>
    </div>

    <!-- 未找到产品 -->
    <div v-if="result && !isLoadingProduct && !productInfo && !isScanning" class="no-product">
      <van-empty description="未找到对应产品信息" image="search">
        <van-button type="primary" size="small" round @click="resetAll">
          重新扫码
        </van-button>
      </van-empty>
    </div>

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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import { useBarcodeScanner } from '@/composables/useBarcodeScanner'
import { createTransaction } from '@/api/inventory'

const router = useRouter()
const videoRef = ref<HTMLVideoElement | null>(null)
const manualSku = ref('')

const {
  isScanning,
  result,
  error,
  torchEnabled,
  productInfo,
  isLoadingProduct,
  startScan,
  stopScan,
  resetResult,
  toggleTorch,
  manualLookup,
} = useBarcodeScanner()

// 入库/出库弹窗
const stockDialogVisible = ref(false)
const stockDialogType = ref<'in' | 'out'>('in')
const stockQuantity = ref('')
const stockRemark = ref('')

function handleStartScan() {
  resetAll()
  if (videoRef.value) {
    startScan(videoRef.value)
  } else {
    startScan()
  }
}

function handleStopScan() {
  stopScan()
}

async function handleToggleTorch() {
  await toggleTorch()
}

function handleManualSearch() {
  if (!manualSku.value.trim()) return
  resetResult()
  manualLookup(manualSku.value.trim())
}

function resetAll() {
  resetResult()
  manualSku.value = ''
}

function getStockTagType(status: string): 'success' | 'danger' | 'warning' | 'primary' {
  switch (status) {
    case 'normal':
      return 'success'
    case 'low_stock':
    case 'out_of_stock':
      return 'danger'
    case 'over_stock':
      return 'warning'
    default:
      return 'primary'
  }
}

function getStockStatusLabel(status: string): string {
  switch (status) {
    case 'normal':
      return '正常'
    case 'low_stock':
      return '低库存'
    case 'out_of_stock':
      return '缺货'
    case 'over_stock':
      return '超储'
    default:
      return '未知'
  }
}

function handleStockIn() {
  if (!productInfo.value) return
  stockDialogType.value = 'in'
  stockQuantity.value = ''
  stockRemark.value = ''
  stockDialogVisible.value = true
}

function handleStockOut() {
  if (!productInfo.value) return
  stockDialogType.value = 'out'
  stockQuantity.value = ''
  stockRemark.value = ''
  stockDialogVisible.value = true
}

function handleViewDetail() {
  if (productInfo.value) {
    router.push(`/inventory?product_id=${productInfo.value.id}`)
  }
}

async function confirmStockAction() {
  if (!productInfo.value || !stockQuantity.value) {
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
      product_id: productInfo.value.id,
      type: stockDialogType.value,
      quantity,
      remark: stockRemark.value || undefined,
    })
    showSuccessToast(stockDialogType.value === 'in' ? '入库成功' : '出库成功')
    // 重新查询产品信息以更新库存
    if (result.value) {
      manualLookup(result.value.text)
    }
  } catch {
    showToast('操作失败')
  }
}
</script>

<style scoped lang="scss">
.scan-view {
  background: #f7f8fa;
  min-height: 100%;
}

.scan-area {
  position: relative;
  width: 100%;
  height: 280px;
  background: #000;
  overflow: hidden;
}

.scan-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.scan-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  .scan-frame {
    width: 200px;
    height: 200px;
    border: 2px solid rgba(64, 158, 255, 0.8);
    border-radius: 8px;
    box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.4);
    position: relative;
    overflow: hidden;

    .scan-line {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, #409eff, transparent);
      animation: scanLine 2s ease-in-out infinite;
    }
  }

  .scan-hint {
    color: #fff;
    font-size: 14px;
    margin-top: 16px;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  }
}

@keyframes scanLine {
  0% {
    top: 0;
  }
  50% {
    top: 100%;
  }
  100% {
    top: 0;
  }
}

.torch-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
}

.scan-actions {
  padding: 16px;
}

.scan-error {
  margin: 0 16px;
}

.manual-input-section {
  padding: 0 16px;

  .manual-input-row {
    display: flex;
    gap: 8px;
    align-items: center;

    .van-field {
      flex: 1;
      border-radius: 20px;
      background: #fff;
    }
  }
}

.scan-result {
  margin: 12px 16px 0;

  .result-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    padding: 0 4px;

    .result-title {
      font-size: 14px;
      font-weight: 600;
      color: #323233;
      flex: 1;
    }
  }
}

.product-loading {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.product-card {
  margin: 12px 16px;

  .product-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding: 0 4px;

    .product-name {
      font-size: 16px;
      font-weight: 600;
      color: #323233;
    }
  }

  .stock-value {
    font-weight: 700;
    font-size: 16px;

    &.stock-normal {
      color: #07c160;
    }

    &.stock-low_stock,
    &.stock-out_of_stock {
      color: #ee0a24;
    }

    &.stock-over_stock {
      color: #ff976a;
    }
  }

  .product-actions {
    display: flex;
    gap: 10px;
    justify-content: center;
    padding: 16px 0;
  }
}

.no-product {
  padding: 20px 0;
}
</style>
