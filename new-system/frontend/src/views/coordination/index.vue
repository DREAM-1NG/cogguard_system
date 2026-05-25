<template>
  <div class="coordination-page">
    <PageHeader
      title="协同检测"
      description="基于共享对象与时间窗识别协同配对，并对加权协同网络做社区发现与可视化展示。"
    />

    <a-card size="small" class="panel">
      <a-form layout="inline" :model="params" @finish="handleDetect">
        <a-form-item label="时间窗口(秒)">
          <a-input-number v-model:value="params.time_window" :min="1" :max="3600" />
        </a-form-item>
        <a-form-item label="最低参与">
          <a-input-number v-model:value="params.min_participation" :min="1" :max="100" />
        </a-form-item>
        <a-form-item label="边权阈值">
          <a-slider v-model:value="params.edge_weight" :min="0" :max="1" :step="0.05" style="width: 160px" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="detecting">运行检测</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-row :gutter="[16, 16]" class="metric-row" v-if="summary">
      <a-col :xs="12" :lg="6">
        <a-card size="small"><a-statistic title="分析帖子" :value="summary.total_posts" /></a-card>
      </a-col>
      <a-col :xs="12" :lg="6">
        <a-card size="small"><a-statistic title="协调配对" :value="summary.total_pairs" /></a-card>
      </a-col>
      <a-col :xs="12" :lg="6">
        <a-card size="small"><a-statistic title="协调账户" :value="summary.coordinated_accounts" /></a-card>
      </a-col>
      <a-col :xs="12" :lg="6">
        <a-card size="small"><a-statistic title="社区数量" :value="summary.cluster_count" /></a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]" class="metric-row" v-if="summary">
      <a-col :xs="12" :lg="8">
        <a-card size="small"><a-statistic title="协调边数" :value="summary.coordinated_edges" /></a-card>
      </a-col>
      <a-col :xs="12" :lg="8">
        <a-card size="small"><a-statistic title="连通分量" :value="summary.components" /></a-card>
      </a-col>
      <a-col :xs="12" :lg="8">
        <a-card size="small"><a-statistic title="用户聚类" :value="clusterStats.length" /></a-card>
      </a-col>
    </a-row>

    <a-card size="small" title="协同网络" class="panel">
      <div ref="networkRef" class="network-chart">
        <a-empty v-if="!hasNetwork" description="运行检测后展示协同网络" />
      </div>
    </a-card>

    <a-row :gutter="[16, 16]" class="metric-row">
      <a-col :xs="24" :xl="12">
        <a-card size="small" title="用户聚类统计" class="panel">
          <a-table
            v-if="clusterStats.length"
            :columns="clusterColumns"
            :data-source="clusterStats"
            :pagination="{ pageSize }"
            row-key="cluster_id"
            size="middle"
          />
          <a-empty v-else description="暂无聚类数据" />
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="12">
        <a-card size="small" title="协同账户排名" class="panel">
          <template #extra v-if="accountStats.length">
            <TableSettings v-model:size="tableSize" v-model:pageSize="pageSize" />
          </template>
          <a-table
            v-if="accountStats.length"
            :columns="accountColumns"
            :data-source="accountStats"
            :pagination="{ pageSize }"
            row-key="account_id"
            :size="tableSize"
          />
          <a-empty v-else description="暂无数据" />
        </a-card>
      </a-col>
    </a-row>

    <a-card size="small" title="高频共享对象" class="panel">
      <a-table
        v-if="groupStats.length"
        :columns="groupColumns"
        :data-source="groupStats"
        :pagination="{ pageSize }"
        row-key="object_id"
        :size="tableSize"
      />
      <a-empty v-else description="暂无数据" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import TableSettings from '@/components/TableSettings.vue'
import { runCoordinationDetection } from '@/api/coordination'

type NodeData = {
  id: string
  name?: string
  degree?: number
  cluster_id?: number
  cluster_size?: number
  cluster_degree?: number
  [key: string]: any
}

type EdgeData = {
  source: string
  target: string
  weight?: number
  avg_time_delta?: number
  edge_symmetry_score?: number
  [key: string]: any
}

const detecting = ref(false)
const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const pageSize = ref(10)
const summary = ref<any>(null)
const network = ref<{ nodes: NodeData[]; edges: EdgeData[]; clusters?: any[] } | null>(null)
const accountStats = ref<any[]>([])
const groupStats = ref<any[]>([])
const clusterStats = ref<any[]>([])
const networkRef = ref<HTMLDivElement | null>(null)
const chart = ref<ECharts | null>(null)
let resizeHandler: (() => void) | null = null

const params = reactive({ time_window: 60, min_participation: 2, edge_weight: 0.5 })

const hasNetwork = computed(() => Boolean(network.value?.nodes?.length && network.value?.edges?.length))

const palette = ['#2563eb', '#059669', '#dc2626', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#16a34a']

const accountColumns = [
  { title: '账户ID', dataIndex: 'account_id', key: 'account_id', ellipsis: true },
  { title: '度数', dataIndex: 'degree', key: 'degree', sorter: (a: any, b: any) => a.degree - b.degree },
  { title: '加权度', dataIndex: 'avg_weight', key: 'avg_weight', sorter: (a: any, b: any) => a.avg_weight - b.avg_weight },
  { title: '平均时差', dataIndex: 'avg_time_delta', key: 'avg_time_delta' },
  { title: '对称性', dataIndex: 'avg_edge_symmetry', key: 'avg_edge_symmetry' },
  { title: '协同分享数', dataIndex: 'coordinated_shares_count', key: 'coordinated_shares_count' },
]

const groupColumns = [
  { title: '共享对象', dataIndex: 'object_id', key: 'object_id', ellipsis: true },
  { title: '涉及账户数', dataIndex: 'num_accounts', key: 'num_accounts', sorter: (a: any, b: any) => a.num_accounts - b.num_accounts },
  { title: '协同配对数', dataIndex: 'num_pairs', key: 'num_pairs', sorter: (a: any, b: any) => a.num_pairs - b.num_pairs },
]

const clusterColumns = [
  { title: '社区ID', dataIndex: 'cluster_id', key: 'cluster_id', sorter: (a: any, b: any) => a.cluster_id - b.cluster_id },
  { title: '规模', dataIndex: 'size', key: 'size', sorter: (a: any, b: any) => a.size - b.size },
  { title: '总权重', dataIndex: 'total_weight', key: 'total_weight', sorter: (a: any, b: any) => a.total_weight - b.total_weight },
  { title: '平均度', dataIndex: 'avg_degree', key: 'avg_degree', sorter: (a: any, b: any) => a.avg_degree - b.avg_degree },
]

async function handleDetect() {
  detecting.value = true
  try {
    const res = (await runCoordinationDetection(params)) as { data: any }
    const data = res.data
    if (data.error) {
      message.warning(data.error)
      return
    }
    summary.value = data.summary
    network.value = data.network
    accountStats.value = data.account_stats || []
    groupStats.value = data.group_stats || []
    clusterStats.value = data.cluster_stats || data.network?.clusters || []
    await nextTick()
    renderNetwork()
    message.success(`检测完成：发现 ${data.summary.coordinated_accounts} 个协调账户`)
  } catch (error) {
    message.error('协同检测失败')
  } finally {
    detecting.value = false
  }
}

function buildOption(): EChartsOption {
  const net = network.value
  if (!net) return {}

  const nodes = net.nodes.map((node) => ({
    ...node,
    name: node.name || node.id,
    symbolSize: Math.max(18, Math.min(48, (node.cluster_degree || node.degree || 1) * 3)),
    category: node.cluster_id ?? 0,
    itemStyle: {
      color: palette[(node.cluster_id ?? 0) % palette.length],
    },
  }))

  const categories = clusterStats.value.map((cluster) => ({
    name: `C${cluster.cluster_id}`,
    itemStyle: {
      color: palette[cluster.cluster_id % palette.length],
    },
  }))

  const links = net.edges.map((edge) => ({
    ...edge,
    lineStyle: {
      width: Math.max(1, Math.min(8, Number(edge.weight || 1))),
      opacity: 0.55,
      color: '#94a3b8',
    },
  }))

  return {
    animationDuration: 900,
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => buildTooltip(params),
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      data: categories.map((item) => item.name),
      textStyle: { color: '#475569' },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links,
        categories,
        roam: true,
        label: {
          show: true,
          position: 'right',
          formatter: '{b}',
          color: '#1f2937',
        },
        force: {
          repulsion: 260,
          edgeLength: [70, 160],
          gravity: 0.05,
        },
        lineStyle: {
          curveness: 0.08,
        },
        emphasis: {
          focus: 'adjacency',
          label: {
            show: true,
          },
        },
      },
    ],
  }
}

function buildTooltip(params: any) {
  const data = params.data || {}
  if (data.source && data.target) {
    return [
      `<strong>${data.source} → ${data.target}</strong>`,
      `权重：${data.weight ?? 0}`,
      `平均时差：${data.avg_time_delta ?? '-'}`,
      `对称性：${data.edge_symmetry_score ?? '-'}`,
    ].join('<br/>')
  }
  return [
    `<strong>${data.name || data.id}</strong>`,
    `cluster_id：${data.cluster_id ?? '-'}`,
    `cluster_size：${data.cluster_size ?? '-'}`,
    `cluster_degree：${data.cluster_degree ?? '-'}`,
  ].join('<br/>')
}

function renderNetwork() {
  if (!networkRef.value || !hasNetwork.value) return
  if (!chart.value) {
    chart.value = echarts.init(networkRef.value)
  }
  chart.value.setOption(buildOption(), true)
  chart.value.resize()
}

function resizeChart() {
  chart.value?.resize()
}

watch(network, () => {
  void nextTick().then(renderNetwork)
})

onBeforeUnmount(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
  }
  chart.value?.dispose()
  chart.value = null
})

resizeHandler = resizeChart
window.addEventListener('resize', resizeHandler)
</script>

<style scoped lang="less">
.coordination-page {
  color: #1f2937;
}

.panel {
  margin-bottom: 16px;
}

.metric-row {
  margin-bottom: 16px;
}

.network-chart {
  width: 100%;
  min-height: 520px;
  background:
    radial-gradient(circle at 20% 20%, rgba(37, 99, 235, 0.08), transparent 32%),
    radial-gradient(circle at 80% 20%, rgba(16, 185, 129, 0.08), transparent 28%),
    linear-gradient(180deg, #ffffff, #f8fafc);
}
</style>
