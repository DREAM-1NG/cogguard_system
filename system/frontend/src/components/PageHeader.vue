<!--
  页面标题组件：标题文字 + 右侧悬浮说明图标
-->
<template>
  <div class="page-header">
    <h2 class="page-title">{{ title }}</h2>
    <a-popover
      v-if="description || slots.description"
      placement="bottomLeft"
      :trigger="['hover', 'focus', 'click']"
    >
      <template #content>
        <div style="max-width: 360px; line-height: 1.8">
          <slot name="description">{{ description }}</slot>
        </div>
      </template>
      <button type="button" class="page-help-button" aria-label="查看页面说明">
        <QuestionCircleOutlined aria-hidden="true" />
      </button>
    </a-popover>
  </div>
</template>

<script setup lang="ts">
import { useSlots } from 'vue'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'

const slots = useSlots()

defineProps<{
  title: string
  description?: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.page-help-button {
  align-items: center;
  appearance: none;
  background: transparent;
  border: 0;
  border-radius: 4px;
  font-size: 16px;
  color: #999;
  cursor: help;
  display: inline-flex;
  height: 28px;
  justify-content: center;
  padding: 0;
  transition: color 0.2s;
  width: 28px;
}
.page-help-button:hover,
.page-help-button:focus-visible {
  color: #1890ff;
}
.page-help-button:focus-visible {
  outline: 2px solid #1677ff;
  outline-offset: 2px;
}
</style>
