<template>
  <a-layout class="app-layout">
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark">
      <div class="logo">
        <span v-if="!collapsed">CogGuard</span>
        <span v-else>CG</span>
      </div>
      <a-menu theme="dark" mode="inline" :selectedKeys="selectedKeys" @click="handleMenuClick">
        <a-menu-item v-for="item in visibleMenuItems" :key="item.path" :disabled="item.disabled">
          <a-tooltip :title="item.desc" placement="right" :mouseEnterDelay="0.4">
            <component :is="item.icon" />
            <span>{{ item.label }}</span>
          </a-tooltip>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="app-header">
        <div class="header-left">
          <span class="header-module">{{ currentMenu?.label || 'CogGuard' }}</span>
        </div>
        <div class="header-right">
          <a-dropdown>
            <div class="user-badge">
              <a-avatar size="small" style="background-color: #001529; font-size: 12px">
                {{ (authStore.userInfo?.username || 'U').charAt(0).toUpperCase() }}
              </a-avatar>
              <span class="user-name">{{ authStore.userInfo?.username || '用户' }}</span>
            </div>
            <template #overlay>
              <a-menu>
                <a-menu-item disabled>
                  <UserOutlined /> 角色：{{ authStore.userInfo?.role || '-' }}
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item @click="handleLogout" danger>
                  <LogoutOutlined /> 退出登录
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <div class="tab-bar">
        <div
          v-for="tab in openTabs"
          :key="tab.path"
          :class="['tab-item', { active: tab.path === route.path }]"
          @click="router.push(tab.path)"
        >
          <span>{{ tab.label }}</span>
          <CloseOutlined
            v-if="openTabs.length > 1"
            class="tab-close"
            @click.stop="closeTab(tab.path)"
          />
        </div>
      </div>

      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  DashboardOutlined,
  CloudDownloadOutlined,
  ApartmentOutlined,
  ShareAltOutlined,
  UserOutlined,
  AlertOutlined,
  SettingOutlined,
  LogoutOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const collapsed = ref(false)

const menuItems = [
  { path: '/dashboard', label: '数据大屏', icon: DashboardOutlined, desc: '系统首页的大屏总览，保留本地地图资产和平台分布可视化', disabled: false },
  { path: '/crawl', label: '数据采集', icon: CloudDownloadOutlined, desc: '创建采集请求并管理多平台数据获取', disabled: false },
  { path: '/coordination', label: '协同发现', icon: ApartmentOutlined, desc: '发现协同行为并构建协同网络', disabled: false },
  { path: '/propagation', label: '传播分析', icon: ShareAltOutlined, desc: '查看传播预测、证据链和传播角色', disabled: false },
  { path: '/accounts', label: '账号画像', icon: UserOutlined, desc: '账号画像、活跃节律和自动化倾向', disabled: false },
  { path: '/risk', label: '风险研判', icon: AlertOutlined, desc: '风险研判、证据融合和治理分析', disabled: false },
  { path: '/system', label: '系统管理', icon: SettingOutlined, desc: '管理研判服务、评测数据集、策略、任务和回填', disabled: false, roles: ['admin'] },
]

const visibleMenuItems = computed(() => {
  const role = authStore.userInfo?.role
  return menuItems.filter((item) => !item.roles || item.roles.includes(String(role)))
})

const selectedKeys = computed(() => {
  const exact = visibleMenuItems.value.find((item) => item.path === route.path)
  if (exact) return [exact.path]
  const prefix = visibleMenuItems.value.find((item) => item.path !== '/' && route.path.startsWith(item.path))
  return [prefix?.path || route.path]
})
const currentMenu = computed(() => visibleMenuItems.value.find((item) => item.path === selectedKeys.value[0]))

const openTabs = ref<Array<{ path: string; label: string }>>([])

function findLabel(path: string): string {
  return visibleMenuItems.value.find((item) => item.path === path)?.label || '页面'
}

function addTab(path: string) {
  if (!openTabs.value.find((tab) => tab.path === path)) {
    openTabs.value.push({ path, label: findLabel(path) })
  }
}

function closeTab(path: string) {
  const idx = openTabs.value.findIndex((tab) => tab.path === path)
  if (idx === -1) return
  openTabs.value.splice(idx, 1)
  if (path === route.path && openTabs.value.length > 0) {
    const target = openTabs.value[Math.min(idx, openTabs.value.length - 1)]
    router.push(target.path)
  }
}

watch(() => route.path, (path) => addTab(path), { immediate: true })

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}

function handleLogout() {
  authStore.logout()
}

onMounted(async () => {
  if (authStore.isLoggedIn && !authStore.userInfo) {
    try {
      await authStore.fetchProfile()
    } catch {
      // The request interceptor handles auth failures globally.
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
  padding: 0 20px;
  height: 48px;
  line-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
}

.header-module {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a2e;
  letter-spacing: 0.5px;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 14px;
  border-radius: 20px;
  background: #f0f5ff;
  border: 1px solid #d6e4ff;
  transition: all 0.2s;

  &:hover {
    background: #e6f0ff;
    box-shadow: 0 2px 6px rgba(24, 144, 255, 0.15);
  }
}

.user-name {
  color: #1a1a2e;
  font-weight: 600;
  font-size: 13px;
}

.tab-bar {
  display: flex;
  align-items: center;
  background: #fafafa;
  padding: 6px 16px 0;
  border-bottom: 1px solid #f0f0f0;
  gap: 4px;
  overflow-x: auto;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  color: #666;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  position: relative;
  top: 1px;

  &:hover {
    color: #1890ff;
    background: #fff;
  }

  &.active {
    color: #1890ff;
    font-weight: 600;
    background: #fff;
    border-color: #d9d9d9;
    border-bottom: 2px solid #fff;
  }
}

.tab-close {
  font-size: 10px;
  color: #bbb;
  border-radius: 50%;
  padding: 2px;
  transition: all 0.15s;

  &:hover {
    color: #f5222d;
    background: #fff1f0;
  }
}

.app-content {
  margin: 16px;
  padding: 20px 24px;
  background: #fff;
  border-radius: 6px;
  min-height: 360px;
}
</style>

