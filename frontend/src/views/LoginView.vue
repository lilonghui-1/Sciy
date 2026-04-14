<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">库存管理系统</h1>
      <p class="login-subtitle">智能库存管理平台</p>

      <van-form @submit="handleLogin" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            :rules="[{ required: true, message: '请输入用户名' }]"
          />
          <van-field
            v-model="form.password"
            type="password"
            name="password"
            label="密码"
            placeholder="请输入密码"
            :rules="[{ required: true, message: '请输入密码' }]"
          />
        </van-cell-group>

        <div class="login-actions">
          <van-button
            round
            block
            type="primary"
            native-type="submit"
            :loading="loading"
            loading-text="登录中..."
          >
            登录
          </van-button>
        </div>
      </van-form>

      <div class="login-footer">
        <span>还没有账号？</span>
        <a href="#" @click.prevent="showRegister = true">立即注册</a>
      </div>
    </div>

    <!-- 注册弹窗 -->
    <van-popup
      v-model:show="showRegister"
      position="bottom"
      round
      :style="{ height: '70%' }"
    >
      <div class="register-panel">
        <h2>用户注册</h2>
        <van-form @submit="handleRegister">
          <van-cell-group inset>
            <van-field
              v-model="registerForm.username"
              label="用户名"
              placeholder="请输入用户名"
              :rules="[{ required: true, message: '请输入用户名' }]"
            />
            <van-field
              v-model="registerForm.email"
              label="邮箱"
              placeholder="请输入邮箱"
              :rules="[
                { required: true, message: '请输入邮箱' },
                { pattern: emailPattern, message: '邮箱格式不正确' },
              ]"
            />
            <van-field
              v-model="registerForm.phone"
              label="手机号"
              placeholder="请输入手机号（选填）"
            />
            <van-field
              v-model="registerForm.password"
              type="password"
              label="密码"
              placeholder="请输入密码"
              :rules="[{ required: true, message: '请输入密码' }]"
            />
          </van-cell-group>
          <div class="register-actions">
            <van-button round block type="primary" native-type="submit" :loading="registerLoading">
              注册
            </van-button>
            <van-button round block plain type="default" @click="showRegister = false">
              取消
            </van-button>
          </div>
        </van-form>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import { register } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const showRegister = ref(false)
const registerLoading = ref(false)
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const form = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  email: '',
  phone: '',
  password: '',
})

async function handleLogin() {
  loading.value = true
  try {
    await authStore.login({
      username: form.username,
      password: form.password,
    })
    showSuccessToast('登录成功')
    router.push('/')
  } catch (err: any) {
    showFailToast(err?.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  registerLoading.value = true
  try {
    await register(registerForm)
    showSuccessToast('注册成功，请登录')
    showRegister.value = false
    form.username = registerForm.username
    form.password = ''
    registerForm.username = ''
    registerForm.email = ''
    registerForm.phone = ''
    registerForm.password = ''
  } catch (err: any) {
    showFailToast(err?.response?.data?.message || '注册失败')
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px 30px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.login-title {
  text-align: center;
  font-size: 28px;
  color: #303133;
  margin: 0 0 8px 0;
}

.login-subtitle {
  text-align: center;
  font-size: 14px;
  color: #909399;
  margin: 0 0 30px 0;
}

.login-form {
  margin-top: 20px;
}

.login-actions {
  margin: 30px 16px 0;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: #909399;

  a {
    color: #409eff;
    text-decoration: none;
  }
}

.register-panel {
  padding: 20px;

  h2 {
    text-align: center;
    margin: 0 0 20px 0;
    font-size: 20px;
    color: #303133;
  }
}

.register-actions {
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
