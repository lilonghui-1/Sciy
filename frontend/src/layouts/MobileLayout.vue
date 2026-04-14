<template>
  <div class="mobile-layout">
    <div class="mobile-content">
      <RouterView />
    </div>
    <van-tabbar v-model="activeTab" route>
      <van-tabbar-item to="/mobile/home" icon="home-o">首页</van-tabbar-item>
      <van-tabbar-item to="/mobile/check" icon="orders-o">库存</van-tabbar-item>
      <van-tabbar-item to="/mobile/alerts" icon="bell" :badge="alertBadge">告警</van-tabbar-item>
      <van-tabbar-item to="/mobile/scan" icon="scan">扫码</van-tabbar-item>
      <van-tabbar-item to="/mobile/chat" icon="chat-o">AI</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activeTab = ref(0)

const alertBadge = computed(() => {
  const count = localStorage.getItem('unreadAlerts')
  return count ? count : ''
})
</script>

<style scoped lang="scss">
.mobile-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  background-color: #f7f8fa;
}
</style>
