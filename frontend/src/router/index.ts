import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/PcLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/pc/DashboardView.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'products',
        name: 'Products',
        component: () => import('@/views/pc/ProductsView.vue'),
        meta: { title: '产品管理' },
      },
      {
        path: 'inventory',
        name: 'Inventory',
        component: () => import('@/views/pc/InventoryView.vue'),
        meta: { title: '库存管理' },
      },
      {
        path: 'forecasts',
        name: 'Forecasts',
        component: () => import('@/views/pc/ForecastsView.vue'),
        meta: { title: '预测分析' },
      },
      {
        path: 'alerts/rules',
        name: 'AlertRules',
        component: () => import('@/views/pc/AlertRulesView.vue'),
        meta: { title: '告警规则' },
      },
      {
        path: 'alerts/events',
        name: 'AlertEvents',
        component: () => import('@/views/pc/AlertEventsView.vue'),
        meta: { title: '告警事件' },
      },
      {
        path: 'erp-sync',
        name: 'ErpSync',
        component: () => import('@/views/pc/ErpSyncView.vue'),
        meta: { title: 'ERP同步' },
      },
      {
        path: 'import',
        name: 'Import',
        component: () => import('@/views/pc/ImportView.vue'),
        meta: { title: '数据导入' },
      },
      {
        path: 'ai-chat',
        name: 'AIChat',
        component: () => import('@/views/pc/AIChatView.vue'),
        meta: { title: 'AI助手' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/pc/SettingsView.vue'),
        meta: { title: '系统设置' },
      },
    ],
  },
  {
    path: '/mobile',
    component: () => import('@/layouts/MobileLayout.vue'),
    redirect: '/mobile/home',
    children: [
      {
        path: 'home',
        name: 'MobileHome',
        component: () => import('@/views/mobile/HomeView.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'check',
        name: 'MobileCheck',
        component: () => import('@/views/mobile/CheckView.vue'),
        meta: { title: '库存盘点' },
      },
      {
        path: 'alerts',
        name: 'MobileAlerts',
        component: () => import('@/views/mobile/AlertsView.vue'),
        meta: { title: '告警' },
      },
      {
        path: 'scan',
        name: 'MobileScan',
        component: () => import('@/views/mobile/ScanView.vue'),
        meta: { title: '扫码' },
      },
      {
        path: 'chat',
        name: 'MobileChat',
        component: () => import('@/views/mobile/AIChatMobileView.vue'),
        meta: { title: 'AI' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router
