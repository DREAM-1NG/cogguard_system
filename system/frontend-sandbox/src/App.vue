<script setup lang="ts">
import { ConfigProvider, theme } from 'ant-design-vue';
</script>

<template>
  <ConfigProvider
    :theme="{
      algorithm: theme.defaultAlgorithm,
      token: {
        colorPrimary: '#18181B',       // Deep Graphite
        colorInfo: '#2563EB',          // Slate Blue
        colorSuccess: '#059669',       // Emerald
        colorWarning: '#D97706',       // Amber
        colorError: '#DC2626',         // Crimson
        colorBgBase: '#FAF9F6',        // Warm Alabaster canvas
        colorBgContainer: '#FFFFFF',   // Pure White container
        colorBgElevated: '#FFFFFF',    // Pure White popovers/modals
        colorBgLayout: '#FAF9F6',      // Layout background
        colorBorder: '#E4E4E7',        // Subtle Stone border
        colorBorderSecondary: '#F4F4F5',
        colorText: '#18181B',          // Deep Graphite primary text
        colorTextBase: '#18181B',
        colorTextHeading: '#09090B',
        colorTextSecondary: '#71717A', // Muted Grey text
        borderRadius: 6,               // Swiss Spa 6px radius
        wireframe: false
      },
      components: {
        Alert: {
          colorWarningBg: '#FEF3C7',
          colorWarningBorder: '#FDE68A',
          colorErrorBg: '#FEF2F2',
          colorErrorBorder: '#FECACA',
          colorInfoBg: '#EFF6FF',
          colorInfoBorder: '#BFDBFE'
        },
        Card: {
          colorBgContainer: '#FFFFFF',
          colorBorderSecondary: '#F4F4F5'
        },
        Layout: {
          colorBgBody: '#FAF9F6',
          colorBgHeader: '#FFFFFF',
          colorBgTrigger: '#FAF9F6'
        },
        Table: {
          colorBgContainer: '#FFFFFF',
          colorFillAlter: '#FAF9F6'
        }
      }
    }"
  >
    <router-view />
  </ConfigProvider>
</template>

<style lang="less">
/* 全局 Swiss Spa Minimalist 画布重置 */
body {
  margin: 0;
  padding: 0;
  background-color: #FAF9F6 !important;
  background-image: none !important;
  color: #18181B;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* 极致极简：卡片、模态框等容器 */
.ant-card, .ant-modal-content, .ant-dropdown-menu, .ant-select-selector {
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.ant-card {
  border: 1px solid #E4E4E7 !important;
  border-radius: 8px !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02) !important;
}

.ant-card-head {
  border-bottom: 1px solid #F4F4F5 !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  color: #18181B !important;
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
  background: #FAF9F6 !important;
  border-bottom: 1px solid #E4E4E7 !important;
  font-weight: 600 !important;
  color: #71717A !important;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.5px;
}
.ant-table-tbody > tr > td {
  border-bottom: 1px solid #F4F4F5 !important;
  color: #18181B !important;
}
.ant-table-tbody > tr:hover > td {
  background: #F4F4F5 !important;
}

/* 标签高级化：低饱和度、柔和边框 */
.ant-tag {
  border: 1px solid #E4E4E7 !important;
  background: #FFFFFF !important;
  color: #18181B !important;
  border-radius: 4px !important;
  font-weight: 500;
  padding: 0 6px !important;
}
.ant-tag-success {
  background: #ECFDF5 !important;
  border-color: #D1FAE5 !important;
  color: #065F46 !important;
}
.ant-tag-processing, .ant-tag-blue {
  background: #EFF6FF !important;
  border-color: #DBEAFE !important;
  color: #1E40AF !important;
}
.ant-tag-error {
  background: #FEF2F2 !important;
  border-color: #FEE2E2 !important;
  color: #991B1B !important;
}
.ant-tag-warning, .ant-tag-orange {
  background: #FFFBEB !important;
  border-color: #FEF3C7 !important;
  color: #92400E !important;
}

/* 按钮高级化 */
.ant-btn {
  border-radius: 6px !important;
  box-shadow: 0 1px 2px 0 rgba(0,0,0,0.02) !important;
}

/* 表单与输入框 */
.ant-input, .ant-input-number, .ant-select-selector {
  border-radius: 6px !important;
  border-color: #E4E4E7 !important;
}
.ant-input:focus, .ant-input-focused, .ant-input-number:focus, .ant-select-focused .ant-select-selector {
  border-color: #18181B !important;
  box-shadow: 0 0 0 2px rgba(24,24,27,0.1) !important;
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
  background: #D4D4D8;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #A1A1AA;
}

/* 极简焦点轮廓 */
*:focus-visible {
  outline: 2px solid #18181B !important;
  outline-offset: 2px;
}
</style>

