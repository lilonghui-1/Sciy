import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { showToast } from 'vant'

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 添加JWT Token
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理401等错误
request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error: AxiosError<{ message?: string }>) => {
    if (error.response) {
      const status = error.response.status
      const serverMessage = error.response.data?.message

      switch (status) {
        case 401:
          showToast('登录已过期，请重新登录')
          ElMessage.error('登录已过期，请重新登录')
          localStorage.removeItem('token')
          localStorage.removeItem('username')
          window.location.href = '/login'
          break
        case 403:
          showToast('没有权限访问该资源')
          ElMessage.error('没有权限访问该资源')
          break
        case 404:
          showToast('请求的资源不存在')
          ElMessage.error('请求的资源不存在')
          break
        case 422:
          showToast(serverMessage || '请求参数错误')
          ElMessage.error(serverMessage || '请求参数错误')
          break
        case 429:
          showToast('请求过于频繁，请稍后再试')
          ElMessage.error('请求过于频繁，请稍后再试')
          break
        case 500:
          showToast('服务器内部错误')
          ElMessage.error('服务器内部错误')
          break
        default:
          showToast(serverMessage || '请求失败')
          ElMessage.error(serverMessage || '请求失败')
      }
    } else if (error.code === 'ECONNABORTED') {
      showToast('请求超时，请稍后重试')
      ElMessage.error('请求超时，请稍后重试')
    } else {
      showToast('网络连接失败，请检查网络设置')
      ElMessage.error('网络连接失败，请检查网络设置')
    }
    return Promise.reject(error)
  }
)

export default request
