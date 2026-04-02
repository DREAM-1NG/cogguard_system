<!--
  监测看板页面

  展示系统概览统计卡片。当前为占位数据，
  后续接入后端 /dashboard/* 接口后替换为真实数据。
-->
<template>
  <div>
    <h2 style="margin-bottom: 24px">监测看板</h2>

    <!-- 统计卡片 -->
    <a-row :gutter="16">
      <a-col :span="6" v-for="card in statCards" :key="card.title">
        <a-card>
          <a-statistic :title="card.title" :value="card.value" :prefix="card.prefix">
            <template #suffix>
              <span style="font-size: 14px; color: #999">{{ card.suffix }}</span>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 占位提示 -->
    <a-card style="margin-top: 24px">
      <a-empty description="图表区域（后续接入 ECharts 可视化组件）" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

/** 概览统计卡片数据（占位） */
const statCards = reactive([
  { title: '监测任务', value: 0, prefix: '', suffix: '个' },
  { title: '采集数据', value: 0, prefix: '', suffix: '条' },
  { title: '风险预警', value: 0, prefix: '', suffix: '条' },
  { title: '协同群体', value: 0, prefix: '', suffix: '个' },
])
</script>
