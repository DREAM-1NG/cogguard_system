<!--
  全局布局组件

  左侧可折叠侧边栏导航 + 顶部栏（用户信息、登出）+ 主内容区。
  子路由页面通过 <router-view /> 渲染在主内容区中。
-->
<template>
  <a-layout class="app-layout">
    <!-- 侧边栏 -->
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark">
      <div class="logo">
        <span v-if="!collapsed">CogGuard</span>
        <span v-else>CG</span>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selectedKeys="selectedKeys"
        @click="handleMenuClick"
      >
        <a-menu-item key="/">
          <DashboardOutlined />
          <span>监测看板</span>
        </a-menu-item>
        <a-menu-item key="/crawl">
          <CloudDownloadOutlined />
          <span>数据采集</span>
        </a-menu-item>
        <!-- 后续模块菜单项预留 -->
        <a-menu-item key="/coordination" disabled>
          <ApartmentOutlined />
          <span>协同检测</span>
        </a-menu-item>
        <a-menu-item key="/propagation" disabled>
          <ShareAltOutlined />
          <span>传播归因</span>
        </a-menu-item>
        <a-menu-item key="/accounts" disabled>
          <UserOutlined />
          <span>账户监测</span>
        </a-menu-item>
        <a-menu-item key="/risk" disabled>
          <AlertOutlined />
          <span>风险研判</span>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <!-- 顶部栏 -->
      <a-layout-header class="app-header">
        <div class="header-right">
          <span class="username">{{ authStore.userInfo?.username || '用户' }}</span>
          <a-button type="link" @click="handleLogout">退出登录</a-button>
        </div>
      </a-layout-header>

      <!-- 主内容区 -->
      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  DashboardOutlined,
  CloudDownloadOutlined,
  ApartmentOutlined,
  ShareAltOutlined,
  UserOutlined,
  AlertOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const collapsed = ref(false)

/** 当前选中的菜单项，与路由路径同步 */
const selectedKeys = computed(() => [route.path])

/** 菜单点击跳转路由 */
function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}

/** 退出登录 */
function handleLogout() {
  authStore.logout()
}

/** 页面加载时获取用户信息 */
onMounted(async () => {
  if (authStore.isLoggedIn && !authStore.userInfo) {
    try {
      await authStore.fetchProfile()
    } catch {
      // Token 失效时 request 拦截器会自动跳转登录
    }
  }
})
</script>

<style scoped lang="less">
.app-layout {
  min-height: 100vh;
}

.logo {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.app-header {
  background: #fff;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  color: #333;
  font-weight: 500;
}

.app-content {
  margin: 16px;
  padding: 24px;
  background: #fff;
  border-radius: 6px;
  min-height: 360px;
}
</style>
