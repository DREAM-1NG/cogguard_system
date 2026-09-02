<!--
  表格设置组件（密度切换 + 每页条数选择）
  通过 v-model 暴露 size 和 pageSize
-->
<template>
  <div class="table-settings">
    <a-space>
      <a-radio-group v-model:value="innerSize" size="small" @change="emitSize">
        <a-radio-button value="small">紧凑</a-radio-button>
        <a-radio-button value="middle">中等</a-radio-button>
        <a-radio-button value="default">宽松</a-radio-button>
      </a-radio-group>
      <a-select v-model:value="innerPageSize" size="small" style="width: 100px" @change="emitPageSize">
        <a-select-option :value="10">10 条/页</a-select-option>
        <a-select-option :value="30">30 条/页</a-select-option>
        <a-select-option :value="50">50 条/页</a-select-option>
        <a-select-option :value="100">100 条/页</a-select-option>
      </a-select>
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  size?: 'small' | 'middle' | 'default'
  pageSize?: number
}>()

const emit = defineEmits<{
  (e: 'update:size', val: string): void
  (e: 'update:pageSize', val: number): void
}>()

const innerSize = ref(props.size || 'middle')
const innerPageSize = ref(props.pageSize || 10)

watch(() => props.size, (v) => { if (v) innerSize.value = v })
watch(() => props.pageSize, (v) => { if (v) innerPageSize.value = v })

function emitSize() { emit('update:size', innerSize.value) }
function emitPageSize() { emit('update:pageSize', innerPageSize.value) }
</script>

<style scoped>
.table-settings {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
</style>
