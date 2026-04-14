<template>
  <div class="alerts-view">
    <van-nav-bar title="告警中心" />

    <!-- 标签页: 待处理 | 已处理 -->
    <van-tabs v-model:active="activeTab" sticky @change="handleTabChange">
      <van-tab :title="`待处理`" :badge="pendingCount || ''">
        <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
          <van-list
            v-model:loading="loading"
            :finished="finished"
            finished-text="没有更多了"
            :error="listError"
            error-text="请求失败，点击重新加载"
            @load="loadMore"
          >
            <div class="alert-list">
              <div
                v-for="alert in alertList"
                :key="alert.id"
                class="alert-card"
                :class="`severity-${alert.severity}`"
              >
                <!-- 告警头部 -->
                <div class="alert-header" @click="toggleExpand(alert.id)">
                  <div class="alert-header-left">
                    <van-icon
                      :name="getSeverityIcon(alert.severity)"
                      :color="getSeverityColor(alert.severity)"
                      size="22"
                      class="severity-icon"
                    />
                    <div class="alert-title-area">
                      <div class="alert-title">{{ alert.rule_name || '库存告警' }}</div>
                      <div class="alert-time">{{ formatTime(alert.created_at) }}</div>
                    </div>
                  </div>
                  <van-icon
                    :name="expandedId === alert.id ? 'arrow-up' : 'arrow-down'"
                    size="14"
                    color="#969799"
                  />
                </div>

                <!-- 告警摘要 -->
                <div class="alert-summary">
                  <span class="product-name">{{ alert.product_name }}</span>
                  <van-tag
                    :type="alert.severity === 'critical' ? 'danger' : alert.severity === 'warning' ? 'warning' : 'primary'"
                    size="small"
                    round
                  >
                    {{ getSeverityLabel(alert.severity) }}
                  </van-tag>
                </div>

                <!-- 展开详情 -->
                <div v-if="expandedId === alert.id" class="alert-detail">
                  <div class="detail-row">
                    <span class="detail-label">告警消息</span>
                    <span class="detail-value">{{ alert.message }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">产品名称</span>
                    <span class="detail-value">{{ alert.product_name }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">告警时间</span>
                    <span class="detail-value">{{ formatFullTime(alert.created_at) }}</span>
                  </div>
                </div>

                <!-- 操作按钮 -->
                <div class="alert-actions">
                  <van-button
                    size="small"
                    round
                    plain
                    type="primary"
                    icon="todo-list-o"
                    :loading="ackLoadingMap[alert.id]"
                    @click.stop="handleAcknowledge(alert)"
                  >
                    确认
                  </van-button>
                  <van-button
                    size="small"
                    round
                    plain
                    type="success"
                    icon="success"
                    :loading="resolveLoadingMap[alert.id]"
                    @click.stop="handleResolve(alert)"
                  >
                    解决
                  </van-button>
                </div>
              </div>

              <van-empty
                v-if="!loading && alertList.length === 0"
                description="暂无待处理告警"
                image="search"
              />
            </div>
          </van-list>
        </van-pull-refresh>
      </van-tab>

      <van-tab title="已处理">
        <van-list
          v-model:loading="loadingDone"
          :finished="finishedDone"
          finished-text="没有更多了"
          :error="listErrorDone"
          error-text="请求失败，点击重新加载"
          @load="loadMoreDone"
        >
          <div class="alert-list">
            <div
              v-for="alert in doneList"
              :key="alert.id"
              class="alert-card resolved"
            >
              <div class="alert-header" @click="toggleExpandDone(alert.id)">
                <div class="alert-header-left">
                  <van-icon name="passed" color="#07c160" size="22" class="severity-icon" />
                  <div class="alert-title-area">
                    <div class="alert-title">{{ alert.rule_name || '库存告警' }}</div>
                    <div class="alert-time">{{ formatTime(alert.created_at) }}</div>
                  </div>
                </div>
                <van-icon
                  :name="expandedDoneId === alert.id ? 'arrow-up' : 'arrow-down'"
                  size="14"
                  color="#969799"
                />
              </div>

              <div class="alert-summary">
                <span class="product-name">{{ alert.product_name }}</span>
                <van-tag type="success" size="small" round>已处理</van-tag>
              </div>

              <div v-if="expandedDoneId === alert.id" class="alert-detail">
                <div class="detail-row">
                  <span class="detail-label">告警消息</span>
                  <span class="detail-value">{{ alert.message }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">确认人</span>
                  <span class="detail-value">{{ alert.acknowledged_by || '--' }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">确认时间</span>
                  <span class="detail-value">{{ alert.acknowledged_at ? formatFullTime(alert.acknowledged_at) : '--' }}</span>
                </div>
              </div>
            </div>

            <van-empty
              v-if="!loadingDone && doneList.length === 0"
              description="暂无已处理告警"
              image="search"
            />
          </div>
        </van-list>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { showToast, showSuccessToast, showDialog } from 'vant'
import dayjs from 'dayjs'
import { getAlertEvents, acknowledgeAlert } from '@/api/alerts'
import type { AlertEvent } from '@/api/alerts'

const activeTab = ref(0)
const refreshing = ref(false)
const loading = ref(false)
const finished = ref(false)
const listError = ref(false)
const page = ref(1)
const pageSize = 20
const pendingCount = ref(0)

const loadingDone = ref(false)
const finishedDone = ref(false)
const listErrorDone = ref(false)
const donePage = ref(1)

const alertList = ref<AlertEvent[]>([])
const doneList = ref<AlertEvent[]>([])

const expandedId = ref<number | null>(null)
const expandedDoneId = ref<number | null>(null)

const ackLoadingMap = reactive<Record<number, boolean>>({})
const resolveLoadingMap = reactive<Record<number, boolean>>({})

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

function formatFullTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

function toggleExpandDone(id: number) {
  expandedDoneId.value = expandedDoneId.value === id ? null : id
}

async function loadMore() {
  if (listError.value) {
    listError.value = false
  }

  try {
    const data = await getAlertEvents({
      page: page.value,
      page_size: pageSize,
      acknowledged: false,
    })

    alertList.value.push(...data.items)
    pendingCount.value = data.total
    page.value++

    if (data.items.length < pageSize) {
      finished.value = true
    }
  } catch {
    listError.value = true
  } finally {
    loading.value = false
  }
}

async function loadMoreDone() {
  if (listErrorDone.value) {
    listErrorDone.value = false
  }

  try {
    const data = await getAlertEvents({
      page: donePage.value,
      page_size: pageSize,
      acknowledged: true,
    })

    doneList.value.push(...data.items)
    donePage.value++

    if (data.items.length < pageSize) {
      finishedDone.value = true
    }
  } catch {
    listErrorDone.value = true
  } finally {
    loadingDone.value = false
  }
}

function handleTabChange() {
  // 切换标签时不需要额外操作，van-list 会自动加载
}

async function onRefresh() {
  alertList.value = []
  page.value = 1
  finished.value = false
  listError.value = false
  await loadMore()
  refreshing.value = false
}

async function handleAcknowledge(alert: AlertEvent) {
  ackLoadingMap[alert.id] = true
  try {
    await acknowledgeAlert(alert.id)
    showSuccessToast('已确认')
    // 从列表中移除
    const index = alertList.value.findIndex((a) => a.id === alert.id)
    if (index !== -1) {
      alertList.value.splice(index, 1)
      pendingCount.value = Math.max(0, pendingCount.value - 1)
    }
  } catch {
    showToast('确认失败')
  } finally {
    ackLoadingMap[alert.id] = false
  }
}

async function handleResolve(alert: AlertEvent) {
  try {
    await showDialog({
      title: '确认解决',
      message: `确认将告警"${alert.rule_name}"标记为已解决？`,
      showCancelButton: true,
      confirmButtonText: '确认解决',
      cancelButtonText: '取消',
    })

    resolveLoadingMap[alert.id] = true
    try {
      await acknowledgeAlert(alert.id)
      showSuccessToast('已解决')
      const index = alertList.value.findIndex((a) => a.id === alert.id)
      if (index !== -1) {
        alertList.value.splice(index, 1)
        pendingCount.value = Math.max(0, pendingCount.value - 1)
      }
    } catch {
      showToast('操作失败')
    } finally {
      resolveLoadingMap[alert.id] = false
    }
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  // van-list 会自动触发加载
})
</script>

<style scoped lang="scss">
.alerts-view {
  background: #f7f8fa;
  min-height: 100%;
}

.alert-list {
  padding: 12px 16px;
}

.alert-card {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  border-left: 3px solid #1989fa;

  &.severity-critical {
    border-left-color: #ee0a24;
  }

  &.severity-warning {
    border-left-color: #ff976a;
  }

  &.severity-info {
    border-left-color: #1989fa;
  }

  &.resolved {
    border-left-color: #07c160;
    opacity: 0.85;
  }

  .alert-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;

    .alert-header-left {
      display: flex;
      align-items: center;
      flex: 1;
      min-width: 0;

      .severity-icon {
        margin-right: 10px;
        flex-shrink: 0;
      }

      .alert-title-area {
        flex: 1;
        min-width: 0;

        .alert-title {
          font-size: 15px;
          font-weight: 600;
          color: #323233;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .alert-time {
          font-size: 12px;
          color: #969799;
          margin-top: 2px;
        }
      }
    }
  }

  .alert-summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #f5f5f5;

    .product-name {
      font-size: 13px;
      color: #646566;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-right: 8px;
    }
  }

  .alert-detail {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #f5f5f5;
    background: #fafafa;
    border-radius: 8px;
    padding: 10px;

    .detail-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 6px;

      &:last-child {
        margin-bottom: 0;
      }

      .detail-label {
        font-size: 12px;
        color: #969799;
        flex-shrink: 0;
        margin-right: 12px;
      }

      .detail-value {
        font-size: 13px;
        color: #323233;
        text-align: right;
        word-break: break-all;
      }
    }
  }

  .alert-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid #f5f5f5;
  }
}
</style>
