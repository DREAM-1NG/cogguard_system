<script setup lang="ts">
import { ConfigProvider, theme } from 'ant-design-vue';
</script>

<template>
  <ConfigProvider
    :theme="{
      algorithm: theme.darkAlgorithm,
      token: {
        colorPrimary: '#FAFAFA',       // White text/buttons for dark theme
        colorInfo: '#3B82F6',          // Bright Slate Blue
        colorSuccess: '#10B981',       // Emerald
        colorWarning: '#F59E0B',       // Amber
        colorError: '#EF4444',         // Crimson
        colorBgBase: '#000000',        // Pure black canvas
        colorBgContainer: '#09090B',   // Vercel dark container
        colorBgElevated: '#18181B',    // Popovers/modals
        colorBgLayout: '#000000',      // Layout background
        colorBorder: '#27272A',        // Subtle zinc border
        colorBorderSecondary: '#18181B',
        colorText: '#FAFAFA',          // Light text
        colorTextBase: '#FAFAFA',
        colorTextHeading: '#FFFFFF',
        colorTextSecondary: '#A1A1AA', // Muted Grey text
        borderRadius: 6,               // Swiss Spa 6px radius
        wireframe: false
      },
      components: {
        Alert: {
          colorWarningBg: '#451A03',
          colorWarningBorder: '#B45309',
          colorErrorBg: '#450A0A',
          colorErrorBorder: '#B91C1C',
          colorInfoBg: '#1E3A8A',
          colorInfoBorder: '#1D4ED8'
        },
        Card: {
          colorBgContainer: '#09090B',
          colorBorderSecondary: '#27272A'
        },
        Layout: {
          colorBgBody: '#000000',
          colorBgHeader: '#09090B',
          colorBgTrigger: '#09090B'
        },
        Table: {
          colorBgContainer: '#09090B',
          colorFillAlter: '#000000'
        }
      }
    }"
  >
    <router-view />
  </ConfigProvider>
</template>

<style lang="less">
/* 全局 Swiss Spa Dark 重置 */
body {
  margin: 0;
  padding: 0;
  background-color: #000000 !important;
  background-image: none !important;
  color: #FAFAFA;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* 极致极简：卡片、模态框等容器 */
.ant-card, .ant-modal-content, .ant-dropdown-menu, .ant-select-selector {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.ant-card {
  border: 1px solid #27272A !important;
  border-radius: 8px !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.4) !important;
  background-color: #09090B !important;
}

.ant-card-head {
  border-bottom: 1px solid #27272A !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  color: #FAFAFA !important;
  min-height: 44px !important;
}

.ant-card-head-title {
  padding: 12px 0 !important;
}

/* 表格净化：去线、留白、通透 */
.ant-table-wrapper {
  background: transparent !important;
}
.ant-table {
  background: transparent !important;
}
.ant-table-thead > tr > th {
  background: #000000 !important;
  border-bottom: 1px solid #27272A !important;
  font-weight: 600 !important;
  color: #A1A1AA !important;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.5px;
}
.ant-table-tbody > tr > td {
  border-bottom: 1px solid #18181B !important;
  color: #FAFAFA !important;
}
.ant-table-tbody > tr:hover > td {
  background: #18181B !important;
}

/* 标签高级化：深色发光质感 */
.ant-tag {
  border: 1px solid #27272A !important;
  background: #09090B !important;
  color: #FAFAFA !important;
  border-radius: 4px !important;
  font-weight: 500;
  padding: 0 6px !important;
}
.ant-tag-success {
  background: rgba(16, 185, 129, 0.1) !important;
  border-color: rgba(16, 185, 129, 0.2) !important;
  color: #34D399 !important;
}
.ant-tag-processing, .ant-tag-blue {
  background: rgba(59, 130, 246, 0.1) !important;
  border-color: rgba(59, 130, 246, 0.2) !important;
  color: #60A5FA !important;
}
.ant-tag-error {
  background: rgba(239, 68, 68, 0.1) !important;
  border-color: rgba(239, 68, 68, 0.2) !important;
  color: #F87171 !important;
}
.ant-tag-warning, .ant-tag-orange {
  background: rgba(245, 158, 11, 0.1) !important;
  border-color: rgba(245, 158, 11, 0.2) !important;
  color: #FBBF24 !important;
}

/* 按钮高级化 */
.ant-btn {
  border-radius: 6px !important;
  box-shadow: 0 1px 2px 0 rgba(0,0,0,0.2) !important;
}

/* 表单与输入框 */
.ant-input, .ant-input-number, .ant-select-selector {
  border-radius: 6px !important;
  border-color: #27272A !important;
  background-color: #000000 !important;
  color: #FAFAFA !important;
}
.ant-input:focus, .ant-input-focused, .ant-input-number:focus, .ant-select-focused .ant-select-selector {
  border-color: #FAFAFA !important;
  box-shadow: 0 0 0 2px rgba(255,255,255,0.1) !important;
}

/* 现代极简滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #3F3F46;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #71717A;
}

/* 极简焦点轮廓 */
*:focus-visible {
  outline: 2px solid #FAFAFA !important;
  outline-offset: 2px;
}
</style>

