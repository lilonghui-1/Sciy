<template>
  <div class="settings-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" type="border-card" class="settings-tabs">

      <!-- 基本设置 -->
      <el-tab-pane label="基本设置" name="basic">
        <el-row :gutter="24">
          <el-col :span="14">
            <el-card shadow="never">
              <template #header>
                <span>用户信息</span>
              </template>
              <el-form
                ref="userFormRef"
                :model="userForm"
                :rules="userRules"
                label-width="100px"
              >
                <el-form-item label="用户名" prop="username">
                  <el-input v-model="userForm.username" disabled />
                </el-form-item>
                <el-form-item label="邮箱" prop="email">
                  <el-input v-model="userForm.email" placeholder="请输入邮箱" clearable />
                </el-form-item>
                <el-form-item label="手机号" prop="phone">
                  <el-input v-model="userForm.phone" placeholder="请输入手机号" clearable />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="savingUser" @click="handleSaveUser">
                    保存修改
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="10">
            <el-card shadow="never">
              <template #header>
                <span>修改密码</span>
              </template>
              <el-form
                ref="passwordFormRef"
                :model="passwordForm"
                :rules="passwordRules"
                label-width="100px"
              >
                <el-form-item label="当前密码" prop="oldPassword">
                  <el-input
                    v-model="passwordForm.oldPassword"
                    type="password"
                    placeholder="请输入当前密码"
                    show-password
                  />
                </el-form-item>
                <el-form-item label="新密码" prop="newPassword">
                  <el-input
                    v-model="passwordForm.newPassword"
                    type="password"
                    placeholder="请输入新密码（至少6位）"
                    show-password
                  />
                </el-form-item>
                <el-form-item label="确认密码" prop="confirmPassword">
                  <el-input
                    v-model="passwordForm.confirmPassword"
                    type="password"
                    placeholder="请再次输入新密码"
                    show-password
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">
                    修改密码
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 通知设置 -->
      <el-tab-pane label="通知设置" name="notification">
        <el-row :gutter="24">
          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <span>通知渠道</span>
              </template>
              <div class="notification-list">
                <div class="notification-item">
                  <div class="notification-info">
                    <div class="notification-name">站内通知</div>
                    <div class="notification-desc">在系统内接收告警和通知消息</div>
                  </div>
                  <el-switch v-model="notificationSettings.inApp" />
                </div>
                <el-divider />
                <div class="notification-item">
                  <div class="notification-info">
                    <div class="notification-name">邮件通知</div>
                    <div class="notification-desc">通过邮件接收重要告警通知</div>
                  </div>
                  <el-switch v-model="notificationSettings.email" />
                </div>
                <el-divider />
                <div class="notification-item">
                  <div class="notification-info">
                    <div class="notification-name">短信通知</div>
                    <div class="notification-desc">通过短信接收紧急告警（仅严重级别）</div>
                  </div>
                  <el-switch v-model="notificationSettings.sms" />
                </div>
                <el-divider />
                <div class="notification-item">
                  <div class="notification-info">
                    <div class="notification-name">Webhook通知</div>
                    <div class="notification-desc">通过自定义Webhook推送通知到第三方系统</div>
                  </div>
                  <el-switch v-model="notificationSettings.webhook" />
                </div>
              </div>
              <div class="notification-actions">
                <el-button type="primary" :loading="savingNotification" @click="handleSaveNotification">
                  保存通知设置
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <span>通知接收配置</span>
              </template>
              <el-form
                ref="notifyConfigFormRef"
                :model="notifyConfig"
                label-width="100px"
              >
                <el-form-item label="通知邮箱">
                  <el-input
                    v-model="notifyConfig.email"
                    placeholder="请输入接收通知的邮箱"
                    clearable
                    :disabled="!notificationSettings.email"
                  />
                </el-form-item>
                <el-form-item label="手机号码">
                  <el-input
                    v-model="notifyConfig.phone"
                    placeholder="请输入接收短信的手机号"
                    clearable
                    :disabled="!notificationSettings.sms"
                  />
                </el-form-item>
                <el-form-item label="Webhook URL">
                  <el-input
                    v-model="notifyConfig.webhookUrl"
                    placeholder="请输入Webhook地址"
                    clearable
                    :disabled="!notificationSettings.webhook"
                  />
                </el-form-item>
                <el-form-item label="Webhook密钥">
                  <el-input
                    v-model="notifyConfig.webhookSecret"
                    placeholder="可选，用于签名验证"
                    clearable
                    show-password
                    :disabled="!notificationSettings.webhook"
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="savingNotifyConfig" @click="handleSaveNotifyConfig">
                    保存配置
                  </el-button>
                  <el-button
                    type="success"
                    plain
                    :loading="testingWebhook"
                    :disabled="!notificationSettings.webhook || !notifyConfig.webhookUrl"
                    @click="handleTestWebhook"
                  >
                    测试Webhook
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ERP配置 -->
      <el-tab-pane label="ERP配置" name="erp">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>ERP系统对接配置</span>
              <el-button
                type="success"
                plain
                size="small"
                :loading="testingErpConnection"
                @click="handleTestErpConnection"
              >
                测试连接
              </el-button>
            </div>
          </template>
          <el-form
            ref="erpFormRef"
            :model="erpForm"
            :rules="erpRules"
            label-width="120px"
            class="erp-form"
          >
            <el-row :gutter="24">
              <el-col :span="12">
                <el-form-item label="ERP API地址" prop="apiUrl">
                  <el-input
                    v-model="erpForm.apiUrl"
                    placeholder="例如: https://erp.example.com/api"
                    clearable
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="API密钥" prop="apiKey">
                  <el-input
                    v-model="erpForm.apiKey"
                    placeholder="请输入API密钥"
                    clearable
                    show-password
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="同步间隔(分钟)" prop="syncInterval">
                  <el-input-number
                    v-model="erpForm.syncInterval"
                    :min="1"
                    :max="1440"
                    :step="5"
                    controls-position="right"
                  />
                  <span class="form-tip">设置自动同步的时间间隔，1-1440分钟</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="同步方向">
                  <el-select v-model="erpForm.direction" style="width: 100%">
                    <el-option label="从ERP拉取" value="pull" />
                    <el-option label="推送到ERP" value="push" />
                    <el-option label="双向同步" value="bidirectional" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="超时时间(秒)">
                  <el-input-number
                    v-model="erpForm.timeout"
                    :min="5"
                    :max="300"
                    :step="5"
                    controls-position="right"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="启用自动同步">
                  <el-switch v-model="erpForm.autoSync" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item>
              <el-button type="primary" :loading="savingErp" @click="handleSaveErp">
                保存ERP配置
              </el-button>
              <el-button @click="handleResetErp">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getUserInfo } from '@/api/auth'
import request from '@/api/request'

const activeTab = ref('basic')

// ===== 基本设置 =====
const userFormRef = ref<FormInstance | null>(null)
const savingUser = ref(false)

const userForm = reactive({
  username: '',
  email: '',
  phone: '',
})

const userRules: FormRules = {
  email: [
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入有效的手机号码', trigger: 'blur' },
  ],
}

const passwordFormRef = ref<FormInstance | null>(null)
const changingPassword = ref(false)

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

// ===== 通知设置 =====
const notificationSettings = reactive({
  inApp: true,
  email: false,
  sms: false,
  webhook: false,
})

const notifyConfig = reactive({
  email: '',
  phone: '',
  webhookUrl: '',
  webhookSecret: '',
})

const savingNotification = ref(false)
const savingNotifyConfig = ref(false)
const testingWebhook = ref(false)

// ===== ERP配置 =====
const erpFormRef = ref<FormInstance | null>(null)
const savingErp = ref(false)
const testingErpConnection = ref(false)

const erpForm = reactive({
  apiUrl: '',
  apiKey: '',
  syncInterval: 30,
  direction: 'pull' as 'pull' | 'push' | 'bidirectional',
  timeout: 30,
  autoSync: false,
})

const erpRules: FormRules = {
  apiUrl: [
    { required: true, message: '请输入ERP API地址', trigger: 'blur' },
    { type: 'url', message: '请输入有效的URL', trigger: 'blur' },
  ],
  apiKey: [
    { required: true, message: '请输入API密钥', trigger: 'blur' },
  ],
  syncInterval: [
    { required: true, message: '请输入同步间隔', trigger: 'blur' },
  ],
}

// ===== 方法 =====

async function fetchUserInfo() {
  try {
    const data = await getUserInfo()
    userForm.username = data.username || ''
    userForm.email = data.email || ''
    userForm.phone = data.phone || ''
  } catch {
    // 静默处理
  }
}

async function handleSaveUser() {
  if (!userFormRef.value) return
  try {
    await userFormRef.value.validate()
  } catch {
    return
  }

  savingUser.value = true
  try {
    await request.put('/auth/profile', {
      email: userForm.email,
      phone: userForm.phone,
    })
    ElMessage.success('用户信息保存成功')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    savingUser.value = false
  }
}

async function handleChangePassword() {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
  } catch {
    return
  }

  changingPassword.value = true
  try {
    await request.put('/auth/password', {
      old_password: passwordForm.oldPassword,
      new_password: passwordForm.newPassword,
    })
    ElMessage.success('密码修改成功')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch {
    // 错误已在拦截器中处理
  } finally {
    changingPassword.value = false
  }
}

async function fetchNotificationSettings() {
  try {
    const data = await request.get<any, {
      in_app: boolean
      email: boolean
      sms: boolean
      webhook: boolean
      notify_email: string
      notify_phone: string
      webhook_url: string
      webhook_secret: string
    }>('/settings/notification')
    notificationSettings.inApp = data.in_app ?? true
    notificationSettings.email = data.email ?? false
    notificationSettings.sms = data.sms ?? false
    notificationSettings.webhook = data.webhook ?? false
    notifyConfig.email = data.notify_email || ''
    notifyConfig.phone = data.notify_phone || ''
    notifyConfig.webhookUrl = data.webhook_url || ''
    notifyConfig.webhookSecret = data.webhook_secret || ''
  } catch {
    // 静默处理
  }
}

async function handleSaveNotification() {
  savingNotification.value = true
  try {
    await request.put('/settings/notification', {
      in_app: notificationSettings.inApp,
      email: notificationSettings.email,
      sms: notificationSettings.sms,
      webhook: notificationSettings.webhook,
    })
    ElMessage.success('通知渠道设置保存成功')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    savingNotification.value = false
  }
}

async function handleSaveNotifyConfig() {
  savingNotifyConfig.value = true
  try {
    await request.put('/settings/notification/config', {
      notify_email: notifyConfig.email,
      notify_phone: notifyConfig.phone,
      webhook_url: notifyConfig.webhookUrl,
      webhook_secret: notifyConfig.webhookSecret,
    })
    ElMessage.success('通知接收配置保存成功')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    savingNotifyConfig.value = false
  }
}

async function handleTestWebhook() {
  if (!notifyConfig.webhookUrl) {
    ElMessage.warning('请先填写Webhook URL')
    return
  }

  testingWebhook.value = true
  try {
    await request.post('/settings/notification/test-webhook', {
      webhook_url: notifyConfig.webhookUrl,
      webhook_secret: notifyConfig.webhookSecret,
    })
    ElMessage.success('Webhook测试消息已发送')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    testingWebhook.value = false
  }
}

async function fetchErpConfig() {
  try {
    const data = await request.get<any, {
      api_url: string
      api_key: string
      sync_interval: number
      direction: string
      timeout: number
      auto_sync: boolean
    }>('/settings/erp')
    erpForm.apiUrl = data.api_url || ''
    erpForm.apiKey = data.api_key || ''
    erpForm.syncInterval = data.sync_interval || 30
    erpForm.direction = (data.direction as any) || 'pull'
    erpForm.timeout = data.timeout || 30
    erpForm.autoSync = data.auto_sync ?? false
  } catch {
    // 静默处理
  }
}

async function handleSaveErp() {
  if (!erpFormRef.value) return
  try {
    await erpFormRef.value.validate()
  } catch {
    return
  }

  savingErp.value = true
  try {
    await request.put('/settings/erp', {
      api_url: erpForm.apiUrl,
      api_key: erpForm.apiKey,
      sync_interval: erpForm.syncInterval,
      direction: erpForm.direction,
      timeout: erpForm.timeout,
      auto_sync: erpForm.autoSync,
    })
    ElMessage.success('ERP配置保存成功')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    savingErp.value = false
  }
}

function handleResetErp() {
  erpForm.apiUrl = ''
  erpForm.apiKey = ''
  erpForm.syncInterval = 30
  erpForm.direction = 'pull'
  erpForm.timeout = 30
  erpForm.autoSync = false
  ElMessage.info('配置已重置')
}

async function handleTestErpConnection() {
  if (!erpForm.apiUrl || !erpForm.apiKey) {
    ElMessage.warning('请先填写API地址和密钥')
    return
  }

  testingErpConnection.value = true
  try {
    const result = await request.post<any, { success: boolean; message: string }>(
      '/settings/erp/test-connection',
      {
        api_url: erpForm.apiUrl,
        api_key: erpForm.apiKey,
        timeout: erpForm.timeout,
      }
    )
    if (result.success) {
      ElMessage.success('ERP连接测试成功')
    } else {
      ElMessage.error(`连接测试失败: ${result.message}`)
    }
  } catch {
    // 错误已在拦截器中处理
  } finally {
    testingErpConnection.value = false
  }
}

onMounted(() => {
  fetchUserInfo()
  fetchNotificationSettings()
  fetchErpConfig()
})
</script>

<style scoped lang="scss">
.settings-view {
  .page-header {
    margin-bottom: 20px;

    h2 {
      margin: 0;
      font-size: 20px;
      color: #303133;
    }
  }

  .settings-tabs {
    :deep(.el-tabs__content) {
      padding: 20px;
    }
  }

  .notification-list {
    .notification-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;

      .notification-info {
        .notification-name {
          font-size: 14px;
          font-weight: 500;
          color: #303133;
          margin-bottom: 4px;
        }

        .notification-desc {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }

  .notification-actions {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;
  }

  .erp-form {
    .form-tip {
      display: block;
      font-size: 12px;
      color: #909399;
      margin-top: 4px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
