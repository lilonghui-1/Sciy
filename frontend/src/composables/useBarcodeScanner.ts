import { ref, onUnmounted } from 'vue'
import { BrowserMultiFormatReader, NotFoundException } from '@zxing/browser'

export interface BarcodeResult {
  text: string
  format: string
}

export interface ProductInfo {
  id: number
  name: string
  sku: string
  quantity: number
  warehouse_name: string
  status: 'normal' | 'low_stock' | 'over_stock' | 'out_of_stock'
  cost_price: number
  selling_price: number
}

export function useBarcodeScanner() {
  const isScanning = ref(false)
  const result = ref<BarcodeResult | null>(null)
  const error = ref<string | null>(null)
  const videoElement = ref<HTMLVideoElement | null>(null)
  const torchEnabled = ref(false)
  const productInfo = ref<ProductInfo | null>(null)
  const isLoadingProduct = ref(false)

  let reader: BrowserMultiFormatReader | null = null
  let videoTrack: MediaStreamTrack | null = null

  async function startScan(videoEl?: HTMLVideoElement) {
    if (isScanning.value) return

    const targetVideo = videoEl || videoElement.value
    if (!targetVideo) {
      error.value = '未找到视频元素'
      return
    }

    try {
      isScanning.value = true
      error.value = null
      result.value = null
      productInfo.value = null

      reader = new BrowserMultiFormatReader()

      const videoInputDevices = await reader.listVideoInputDevices()
      if (videoInputDevices.length === 0) {
        throw new Error('未检测到摄像头设备')
      }

      // 优先选择后置摄像头
      const backCamera = videoInputDevices.find(
        (device) =>
          device.label.toLowerCase().includes('back') ||
          device.label.toLowerCase().includes('rear') ||
          device.label.toLowerCase().includes('environment')
      )
      const deviceId = backCamera?.deviceId || undefined

      reader.decodeFromVideoDevice(deviceId, targetVideo, (results, err) => {
        if (results) {
          result.value = {
            text: results.getText(),
            format: results.getBarcodeFormat().toString(),
          }
          stopScan()
          // 自动查询产品信息
          lookupProduct(result.value.text)
        }
        if (err && !(err instanceof NotFoundException)) {
          console.warn('扫码警告:', err)
        }
      })

      // 获取视频轨道以支持手电筒
      const stream = targetVideo.srcObject as MediaStream
      if (stream) {
        videoTrack = stream.getVideoTracks()[0] || null
      }
    } catch (err: any) {
      error.value = err.message || '启动摄像头失败'
      isScanning.value = false
    }
  }

  function stopScan() {
    if (reader) {
      reader.reset()
      reader = null
    }
    videoTrack = null
    torchEnabled.value = false
    isScanning.value = false
  }

  function resetResult() {
    result.value = null
    error.value = null
    productInfo.value = null
  }

  async function toggleTorch(): Promise<boolean> {
    if (!videoTrack) return false

    try {
      const capabilities = videoTrack.getCapabilities() as any
      if (!capabilities.torch) {
        error.value = '当前设备不支持手电筒'
        return false
      }

      torchEnabled.value = !torchEnabled.value
      await videoTrack.applyConstraints({
        advanced: [{ torch: torchEnabled.value }] as any,
      })
      return torchEnabled.value
    } catch (err: any) {
      error.value = err.message || '切换手电筒失败'
      return false
    }
  }

  async function lookupProduct(code: string) {
    isLoadingProduct.value = true
    try {
      const token = localStorage.getItem('token')
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
      const response = await fetch(
        `${baseUrl}/products/lookup?code=${encodeURIComponent(code)}`,
        {
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        }
      )
      if (response.ok) {
        productInfo.value = await response.json()
      } else {
        productInfo.value = null
      }
    } catch {
      productInfo.value = null
    } finally {
      isLoadingProduct.value = false
    }
  }

  async function manualLookup(sku: string) {
    if (!sku.trim()) return
    result.value = { text: sku.trim(), format: '手动输入' }
    await lookupProduct(sku.trim())
  }

  onUnmounted(() => {
    stopScan()
  })

  return {
    isScanning,
    result,
    error,
    videoElement,
    torchEnabled,
    productInfo,
    isLoadingProduct,
    startScan,
    stopScan,
    resetResult,
    toggleTorch,
    lookupProduct,
    manualLookup,
  }
}
