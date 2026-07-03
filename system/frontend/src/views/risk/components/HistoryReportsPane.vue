<template>
  <a-card class="history-pane" size="small" title="历史报告">
    <a-table
      :columns="columns"
      :dataSource="items"
      :pagination="{ current: page, pageSize: 10, total }"
      :loading="loading"
      :locale="{ emptyText: '暂无数据' }"
      :customRow="historyRowProps"
      rowKey="report_id"
      size="small"
      @change="handleTableChange"
    />
  </a-card>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'

const props = defineProps<{
  items: any[]
  total: number
  page: number
  loading: boolean
}>()

const emit = defineEmits<{
  (event: 'page-change', page: number): void
  (event: 'open-report', reportId: string): void
}>()

const riskLevelLabels: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '严重',
}

const columns = [
  { title: '序号', width: 90, customRender: ({ index }: any) => `第 ${(props.page - 1) * 10 + index + 1} 条` },
  { title: '平台', dataIndex: 'platform', width: 120, customRender: ({ text }: any) => displayText(text) },
  { title: '事件', dataIndex: 'event_id', ellipsis: true, customRender: ({ text }: any) => displayText(text) },
  { title: '风险等级', dataIndex: 'risk_level', width: 120, customRender: ({ text }: any) => riskLevelLabel(text) },
  { title: '生成时间', dataIndex: 'created_at', width: 180, customRender: ({ text }: any) => formatTime(text) },
]

function displayText(value: any) {
  const text = String(value ?? '').trim()
  return text || '暂无'
}

function riskLevelLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (riskLevelLabels[key] || '待核验') : '待核验'
}

function formatTime(value: string | undefined) {
  if (!value) return '暂无'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm') : '暂无'
}

function historyRowProps(record: any) {
  return {
    style: { cursor: 'pointer' },
    onClick: () => emit('open-report', record.report_id),
  }
}

function handleTableChange(pagination: any) {
  emit('page-change', pagination.current || 1)
}
</script>

<style scoped>
.history-pane {
  border-radius: 18px;
}
</style>
