<!--
  全局布局：侧边栏 + 顶部用户栏 + 标签页导航 + 主内容区
-->
<template>
  <a-layout class="app-layout">
    <!-- 侧边栏 -->
    <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark">
      <div class="logo">
        <span v-if="!collapsed">CogGuard</span>
        <span v-else>CG</span>
      </div>
      <a-menu theme="dark" mode="inline" :selectedKeys="selectedKeys" @click="handleMenuClick">
        <a-menu-item v-for="item in menuItems" :key="item.path" :disabled="item.disabled">
          <a-tooltip :title="item.desc" placement="right" :mouseEnterDelay="0.4">
            <component :is="item.icon" />
            <span>{{ item.label }}</span>
          </a-tooltip>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <!-- 顶部栏 -->
      <a-layout-header class="app-header">
        <div class="header-left">
          <span class="header-module">{{ (currentMenu as any)?.label || 'CogGuard' }}</span>
        </div>
        <div class="header-right">
          <a-dropdown>
            <div class="user-badge">
              <a-avatar size="small" style="background-color: #001529; font-size: 12px">
                {{ ((authStore.userInfo as any)?.username || 'U').charAt(0).toUpperCase() }}
              </a-avatar>
              <span class="user-name">{{ (authStore.userInfo as any)?.username || '用户' }}</span>
            </div>
            <template #overlay>
              <a-menu>
                <a-menu-item disabled>
                  <UserOutlined /> 角色：{{ (authStore.userInfo as any)?.role || '-' }}
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

      <!-- 标签页导航 -->
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

      <!-- 主内容区 -->
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
  LogoutOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const collapsed = ref(false)

const menuItems = [
  { path: '/', label: '监测看板', icon: DashboardOutlined, desc: '系统概览：任务统计、风险趋势、数据总量', disabled: false },
  { path: '/crawl', label: '数据采集', icon: CloudDownloadOutlined, desc: '创建采集任务，管理多平台数据抓取', disabled: false },
  { path: '/coordination', label: '协同检测', icon: ApartmentOutlined, desc: '检测时间窗口内的协调分享行为，构建协同网络', disabled: false },
  { path: '/propagation', label: '传播归因', icon: ShareAltOutlined, desc: '分析信息传播路径，识别起爆/桥接/扩散关键角色', disabled: false },
  { path: '/accounts', label: '账户监测', icon: UserOutlined, desc: '账户行为画像、作息节律、自动化倾向评估', disabled: false },
  { path: '/risk', label: '风险研判', icon: AlertOutlined, desc: '有害内容、立场、风险阶段、DISARM 与反制建议分析', disabled: false },
]

const currentMenu = computed(() => menuItems.find(m => m.path === route.path))
const selectedKeys = computed(() => [route.path])

// ---- 标签页管理 ----
const openTabs = ref<Array<{ path: string; label: string }>>([])

function findLabel(path: string): string {
  return menuItems.find(m => m.path === path)?.label || '页面'
}

function addTab(path: string) {
  if (!openTabs.value.find(t => t.path === path)) {
    openTabs.value.push({ path, label: findLabel(path) })
  }
}

function closeTab(path: string) {
  const idx = openTabs.value.findIndex(t => t.path === path)
  if (idx === -1) return
  openTabs.value.splice(idx, 1)
  if (path === route.path && openTabs.value.length > 0) {
    const target = openTabs.value[Math.min(idx, openTabs.value.length - 1)]
    router.push(target.path)
  }
}

watch(() => route.path, (p) => addTab(p), { immediate: true })

function handleMenuClick({ key }: { key: string }) {
  router.push(key)
}

function handleLogout() {
  authStore.logout()
}

onMounted(async () => {
  if (authStore.isLoggedIn && !authStore.userInfo) {
    try { await authStore.fetchProfile() } catch { /* handled */ }
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

// ---- 标签页 ----
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
