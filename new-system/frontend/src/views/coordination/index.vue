<!--
  协同检测页面
-->
<template>
  <div>
    <PageHeader title="协同检测">
      <template #description>
        基于 CooRTweet 算法检测协调行为：在同一共享对象（URL/标签）下，找出在<strong>时间窗口</strong>内发布的账户对，
        通过边权分位数阈值过滤偶然共振，保留异常高频协调对并构建网络图。需先在「数据采集」中创建任务。
      </template>
    </PageHeader>

    <!-- 参数 + 操作 -->
    <a-card size="small" style="margin-bottom: 16px">
      <a-form layout="inline" :model="params" @finish="handleDetect">
        <a-form-item label="时间窗口(秒)">
          <a-input-number v-model:value="params.time_window" :min="1" :max="3600" />
        </a-form-item>
        <a-form-item label="最低参与">
          <a-input-number v-model:value="params.min_participation" :min="1" :max="100" />
        </a-form-item>
        <a-form-item label="边权阈值">
          <a-slider v-model:value="params.edge_weight" :min="0" :max="1" :step="0.05" style="width: 140px" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="detecting">运行检测</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 概览 -->
    <a-row :gutter="16" style="margin-bottom: 16px" v-if="summary">
      <a-col :span="6"><a-card size="small"><a-statistic title="分析帖子" :value="summary.total_posts" suffix="条" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="协调配对" :value="summary.total_pairs" suffix="对" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="协调账户" :value="summary.coordinated_accounts" suffix="个" :valueStyle="{ color: '#f5222d' }" /></a-card></a-col>
      <a-col :span="6"><a-card size="small"><a-statistic title="群体数量" :value="summary.components" suffix="个" /></a-card></a-col>
    </a-row>

    <!-- 协同网络 -->
    <a-card size="small" title="协同网络" style="margin-bottom: 16px">
      <div ref="networkContainer" class="network-container">
        <a-empty v-if="!network || network.nodes.length === 0" description="运行检测后展示协同网络" :image-style="{ height: '40px' }" />
      </div>
    </a-card>

    <!-- 账户排名 -->
    <a-card size="small" style="margin-bottom: 16px">
      <template #title>协调账户排名</template>
      <template #extra v-if="accountStats.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="pageSize" />
      </template>
      <a-table v-if="accountStats.length > 0"
        :columns="accountColumns" :dataSource="accountStats" :pagination="{ pageSize }"
        rowKey="account_id" :size="tableSize"
      />
      <a-empty v-else description="暂无数据" :image-style="{ height: '40px' }" />
    </a-card>

    <!-- 共享对象 -->
    <a-card size="small">
      <template #title>高频共享对象</template>
      <a-table v-if="groupStats.length > 0"
        :columns="groupColumns" :dataSource="groupStats" :pagination="{ pageSize }"
        rowKey="object_id" :size="tableSize"
      />
      <a-empty v-else description="暂无数据" :image-style="{ height: '40px' }" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import { runCoordinationDetection } from '@/api/coordination'
import TableSettings from '@/components/TableSettings.vue'
import PageHeader from '@/components/PageHeader.vue'

const detecting = ref(false)
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)
const summary = ref<any>(null)
const network = ref<any>(null)
const accountStats = ref<any[]>([])
const groupStats = ref<any[]>([])
const networkContainer = ref<HTMLElement | null>(null)

const params = reactive({ time_window: 60, min_participation: 1, edge_weight: 0.5 })

const accountColumns = [
  { title: '账户ID', dataIndex: 'account_id', key: 'account_id', ellipsis: true },
  { title: '连接数', dataIndex: 'degree', key: 'degree', sorter: (a: any, b: any) => a.degree - b.degree },
  { title: '平均边权', dataIndex: 'avg_weight', key: 'avg_weight', sorter: (a: any, b: any) => a.avg_weight - b.avg_weight },
  { title: '平均时间差(秒)', dataIndex: 'avg_time_delta', key: 'avg_time_delta' },
  { title: '对称性', dataIndex: 'avg_edge_symmetry', key: 'avg_edge_symmetry' },
  { title: '协调分享数', dataIndex: 'coordinated_shares_count', key: 'coordinated_shares_count' },
]
const groupColumns = [
  { title: '共享对象', dataIndex: 'object_id', key: 'object_id', ellipsis: true },
  { title: '涉及账户数', dataIndex: 'num_accounts', key: 'num_accounts', sorter: (a: any, b: any) => a.num_accounts - b.num_accounts },
  { title: '协调配对数', dataIndex: 'num_pairs', key: 'num_pairs', sorter: (a: any, b: any) => a.num_pairs - b.num_pairs },
]

async function handleDetect() {
  detecting.value = true
  try {
    const res = (await runCoordinationDetection(params)) as { data: any }
    const data = res.data
    if (data.error) { message.warning(data.error); return }
    summary.value = data.summary
    network.value = data.network
    accountStats.value = data.account_stats || []
    groupStats.value = data.group_stats || []
    if (data.network?.nodes?.length > 0) { await nextTick(); renderNetwork(data.network) }
    message.success(`检测完成：发现 ${data.summary.coordinated_accounts} 个协调账户`)
  } catch { /* handled */ } finally { detecting.value = false }
}

function renderNetwork(net: any) {
  if (!networkContainer.value) return
  const container = networkContainer.value
  container.innerHTML = ''
  const width = container.clientWidth || 800, height = 420
  const canvas = document.createElement('canvas')
  canvas.width = width; canvas.height = height
  canvas.style.width = '100%'; canvas.style.height = `${height}px`
  container.appendChild(canvas)
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const nodes = net.nodes.map((n: any, i: number) => ({
    ...n,
    x: width / 2 + Math.cos(2 * Math.PI * i / net.nodes.length) * Math.min(width, height) / 2.5,
    y: height / 2 + Math.sin(2 * Math.PI * i / net.nodes.length) * Math.min(width, height) / 2.5,
  }))
  const nodeMap = new Map(nodes.map((n: any) => [n.id, n]))

  for (let iter = 0; iter < 100; iter++) {
    for (const n1 of nodes) for (const n2 of nodes) {
      if (n1.id === n2.id) continue
      const dx = n1.x - n2.x, dy = n1.y - n2.y
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
      const f = 2000 / (dist * dist)
      n1.x += dx / dist * f; n1.y += dy / dist * f
    }
    for (const e of net.edges) {
      const s = nodeMap.get(e.source), t = nodeMap.get(e.target)
      if (!s || !t) continue
      const dx = t.x - s.x, dy = t.y - s.y
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
      const f = (dist - 120) * 0.01
      s.x += dx / dist * f; s.y += dy / dist * f
      t.x -= dx / dist * f; t.y -= dy / dist * f
    }
  }
  const xs = nodes.map((n: any) => n.x), ys = nodes.map((n: any) => n.y)
  const pad = 50, sx = (width - 2 * pad) / ((Math.max(...xs) - Math.min(...xs)) || 1)
  const sy = (height - 2 * pad) / ((Math.max(...ys) - Math.min(...ys)) || 1)
  const sc = Math.min(sx, sy), mx = Math.min(...xs), my = Math.min(...ys)
  for (const n of nodes) { n.x = pad + (n.x - mx) * sc; n.y = pad + (n.y - my) * sc }

  ctx.strokeStyle = 'rgba(24,144,255,0.3)'
  for (const e of net.edges) {
    const s = nodeMap.get(e.source), t = nodeMap.get(e.target)
    if (!s || !t) continue
    ctx.lineWidth = Math.min(e.weight || 1, 5)
    ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); ctx.stroke()
  }
  for (const n of nodes) {
    ctx.fillStyle = n.id.includes('coord') ? '#f5222d' : '#1890ff'
    ctx.beginPath(); ctx.arc(n.x, n.y, 6, 0, 2 * Math.PI); ctx.fill()
    ctx.fillStyle = '#333'; ctx.font = '10px sans-serif'
    ctx.fillText(n.id.slice(0, 15), n.x + 8, n.y + 3)
  }
}
</script>

<style scoped>
.network-container { width: 100%; min-height: 420px; border: 1px solid #f0f0f0; border-radius: 4px; background: #fafafa; display: flex; align-items: center; justify-content: center; }
</style>
