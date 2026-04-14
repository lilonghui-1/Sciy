import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getUserInfo as getUserInfoApi } from '@/api/auth'
import type { LoginParams, UserInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => user.value?.username || '')

  async function login(params: LoginParams) {
    const result = await loginApi(params)
    token.value = result.token
    user.value = result.user
    localStorage.setItem('token', result.token)
    localStorage.setItem('username', result.user.username)
    return result
  }

  async function fetchUserInfo() {
    const userInfo = await getUserInfoApi()
    user.value = userInfo
    return userInfo
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('username')
  }

  return {
    token,
    user,
    isLoggedIn,
    username,
    login,
    fetchUserInfo,
    logout,
  }
})
