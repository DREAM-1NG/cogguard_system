<!--
  页面标题组件：标题文字 + 右侧悬浮说明图标
-->
<template>
  <div class="page-header">
    <h2 class="page-title">{{ title }}</h2>
    <a-popover v-if="description || slots.description" placement="bottomLeft" trigger="hover">
      <template #content>
        <div style="max-width: 360px; line-height: 1.8">
          <slot name="description">{{ description }}</slot>
        </div>
      </template>
      <QuestionCircleOutlined class="page-help-icon" />
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
.page-help-icon {
  font-size: 16px;
  color: #999;
  cursor: help;
  transition: color 0.2s;
}
.page-help-icon:hover {
  color: #1890ff;
}
</style>
