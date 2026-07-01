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
        <a-form-item v-if="authStore.isPreviewMode">
          <a-button :disabled="detecting" @click="handleLoadDemo">加载示例网络</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-alert
      v-if="showPreviewAlert"
      class="panel"
      type="warning"
      show-icon
      :message="previewAlertTitle"
      :description="previewAlertDescription"
    >
      <template #action>
        <a-space v-if="authStore.isPreviewMode">
          <a-button size="small" @click="handleLoadDemo">加载示例</a-button>
          <a-button v-if="usingPreviewDemo" size="small" type="link" @click="handleDetect">重新获取真实结果</a-button>
        </a-space>
      </template>
    </a-alert>

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
            :data-source="clusterTableRows"
            :pagination="{ pageSize }"
            :scroll="{ x: 1180 }"
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
            :data-source="accountTableRows"
            :pagination="{ pageSize }"
            :scroll="{ x: 1480 }"
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
        :data-source="groupTableRows"
        :pagination="{ pageSize }"
        :scroll="{ x: 1120 }"
        row-key="object_id"
        :size="tableSize"
      />
      <a-empty v-else description="暂无数据" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, reactive, watch } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import TableSettings from '@/components/TableSettings.vue'
import { runCoordinationDetection } from '@/api/coordination'
import { useAuthStore } from '@/stores/auth'

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

type ClusterRepresentative = {
  account_id: string
  account_label?: string
  cluster_degree?: number
  cross_cluster_weight?: number
  cross_cluster_edge_count?: number
  bridge_score?: number
  first_seen_at?: string
  first_seen_ts?: number
  coordinated_object_count?: number
  coordinated_content_count?: number
  shared_objects_preview?: string[]
  [key: string]: any
}

type ClusterData = {
  cluster_id: number
  size: number
  total_weight?: number
  avg_degree?: number
  core_nodes?: ClusterRepresentative[]
  bridge_nodes?: ClusterRepresentative[]
  early_nodes?: ClusterRepresentative[]
  top_nodes?: ClusterRepresentative[]
  shared_objects?: Array<{ object_id: string; object_type?: string; preview?: string; count?: number }>
  shared_objects_preview?: string[]
  [key: string]: any
}

const previewDetectionResult = {
  network: {
    nodes: [
      {
        id: 'acct_alpha',
        name: 'acct_alpha',
        account_label: 'acct_alpha',
        degree: 3,
        cluster_id: 0,
        cluster_size: 3,
        cluster_degree: 6.4,
        cross_cluster_weight: 0.8,
        bridge_score: 0.18,
        first_seen_at: '2026-05-21T00:00:03+00:00',
        coordinated_object_count: 3,
        coordinated_content_count: 4,
        shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        content_previews: ['首批转发统一话题主帖', '沿用统一海报图传播', '评论区补充相同链接摘要'],
      },
      {
        id: 'acct_beta',
        name: 'acct_beta',
        account_label: 'acct_beta',
        degree: 4,
        cluster_id: 0,
        cluster_size: 3,
        cluster_degree: 7.1,
        cross_cluster_weight: 2.4,
        bridge_score: 0.68,
        first_seen_at: '2026-05-21T00:00:06+00:00',
        coordinated_object_count: 4,
        coordinated_content_count: 5,
        shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        content_previews: ['二次扩散统一口径文案', '同步转发摘要链接', '桥接到另一簇的引流评论'],
      },
      {
        id: 'acct_gamma',
        name: 'acct_gamma',
        account_label: 'acct_gamma',
        degree: 2,
        cluster_id: 0,
        cluster_size: 3,
        cluster_degree: 4.6,
        cross_cluster_weight: 0,
        bridge_score: 0,
        first_seen_at: '2026-05-21T00:00:18+00:00',
        coordinated_object_count: 2,
        coordinated_content_count: 3,
        shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief'],
        content_previews: ['跟进转发同主题话题', '补发短评并附上同一链接'],
      },
      {
        id: 'acct_delta',
        name: 'acct_delta',
        account_label: 'acct_delta',
        degree: 4,
        cluster_id: 1,
        cluster_size: 3,
        cluster_degree: 6.9,
        cross_cluster_weight: 2.4,
        bridge_score: 0.63,
        first_seen_at: '2026-05-21T00:00:09+00:00',
        coordinated_object_count: 4,
        coordinated_content_count: 5,
        shared_objects_preview: ['#联动话题扩散', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        content_previews: ['从另一社区接力扩散链接', '图文同步转发统一海报', '补充评论引导跳转'],
      },
      {
        id: 'acct_epsilon',
        name: 'acct_epsilon',
        account_label: 'acct_epsilon',
        degree: 2,
        cluster_id: 1,
        cluster_size: 3,
        cluster_degree: 4.8,
        cross_cluster_weight: 0.3,
        bridge_score: 0.07,
        first_seen_at: '2026-05-21T00:00:14+00:00',
        coordinated_object_count: 3,
        coordinated_content_count: 3,
        shared_objects_preview: ['#联动话题扩散', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        content_previews: ['快速转载图文卡片', '评论区复用同一短链说明'],
      },
      {
        id: 'acct_zeta',
        name: 'acct_zeta',
        account_label: 'acct_zeta',
        degree: 1,
        cluster_id: 1,
        cluster_size: 3,
        cluster_degree: 3.5,
        cross_cluster_weight: 0,
        bridge_score: 0,
        first_seen_at: '2026-05-21T00:00:27+00:00',
        coordinated_object_count: 2,
        coordinated_content_count: 2,
        shared_objects_preview: ['https://media.example/assets/banner-a.jpg', 'https://coord.example/shared-brief'],
        content_previews: ['复用同一张海报图片', '附带统一跳转链接'],
      },
    ],
    edges: [
      {
        source: 'acct_alpha',
        target: 'acct_beta',
        weight: 4.2,
        avg_time_delta: 6,
        edge_symmetry_score: 0.94,
        shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief'],
        shared_content_previews: ['统一转发主帖文案', '短链摘要同步扩散'],
      },
      {
        source: 'acct_beta',
        target: 'acct_gamma',
        weight: 3.4,
        avg_time_delta: 9,
        edge_symmetry_score: 0.88,
        shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief'],
        shared_content_previews: ['话题评论同步补发', '摘要链接二次扩散'],
      },
      {
        source: 'acct_alpha',
        target: 'acct_gamma',
        weight: 2.2,
        avg_time_delta: 14,
        edge_symmetry_score: 0.73,
        shared_objects_preview: ['#联合话题'],
        shared_content_previews: ['统一话题下的跟进帖子'],
      },
      {
        source: 'acct_delta',
        target: 'acct_epsilon',
        weight: 4.0,
        avg_time_delta: 7,
        edge_symmetry_score: 0.91,
        shared_objects_preview: ['#联动话题扩散', 'https://media.example/assets/banner-a.jpg'],
        shared_content_previews: ['图文卡片同步搬运', '统一海报素材转发'],
      },
      {
        source: 'acct_delta',
        target: 'acct_zeta',
        weight: 2.8,
        avg_time_delta: 12,
        edge_symmetry_score: 0.79,
        shared_objects_preview: ['https://media.example/assets/banner-a.jpg'],
        shared_content_previews: ['海报素材复用', '引流评论同步配图'],
      },
      {
        source: 'acct_epsilon',
        target: 'acct_zeta',
        weight: 2.1,
        avg_time_delta: 15,
        edge_symmetry_score: 0.7,
        shared_objects_preview: ['https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        shared_content_previews: ['短链说明同步发布'],
      },
      {
        source: 'acct_beta',
        target: 'acct_delta',
        weight: 1.8,
        avg_time_delta: 22,
        edge_symmetry_score: 0.58,
        shared_objects_preview: ['https://coord.example/shared-brief'],
        shared_content_previews: ['跨社区引流评论', '桥接账号同步转发'],
      },
    ],
    node_count: 6,
    edge_count: 7,
    component_count: 1,
    components: [['acct_alpha', 'acct_beta', 'acct_gamma', 'acct_delta', 'acct_epsilon', 'acct_zeta']],
    cluster_count: 2,
    clusters: [
      {
        cluster_id: 0,
        size: 3,
        total_weight: 9.8,
        avg_degree: 3,
        members: ['acct_alpha', 'acct_beta', 'acct_gamma'],
        shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        core_nodes: [
          { account_id: 'acct_beta', account_label: 'acct_beta', cluster_degree: 7.1, first_seen_at: '2026-05-21T00:00:06+00:00' },
          { account_id: 'acct_alpha', account_label: 'acct_alpha', cluster_degree: 6.4, first_seen_at: '2026-05-21T00:00:03+00:00' },
        ],
        bridge_nodes: [
          {
            account_id: 'acct_beta',
            account_label: 'acct_beta',
            cluster_degree: 7.1,
            cross_cluster_weight: 2.4,
            bridge_score: 0.68,
            first_seen_at: '2026-05-21T00:00:06+00:00',
          },
        ],
        early_nodes: [{ account_id: 'acct_alpha', account_label: 'acct_alpha', first_seen_at: '2026-05-21T00:00:03+00:00' }],
        top_nodes: [
          { account_id: 'acct_beta', account_label: 'acct_beta', cluster_degree: 7.1, first_seen_at: '2026-05-21T00:00:06+00:00' },
          { account_id: 'acct_alpha', account_label: 'acct_alpha', cluster_degree: 6.4, first_seen_at: '2026-05-21T00:00:03+00:00' },
        ],
      },
      {
        cluster_id: 1,
        size: 3,
        total_weight: 8.9,
        avg_degree: 2.33,
        members: ['acct_delta', 'acct_epsilon', 'acct_zeta'],
        shared_objects_preview: ['#联动话题扩散', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
        core_nodes: [
          { account_id: 'acct_delta', account_label: 'acct_delta', cluster_degree: 6.9, first_seen_at: '2026-05-21T00:00:09+00:00' },
        ],
        bridge_nodes: [
          {
            account_id: 'acct_delta',
            account_label: 'acct_delta',
            cluster_degree: 6.9,
            cross_cluster_weight: 2.4,
            bridge_score: 0.63,
            first_seen_at: '2026-05-21T00:00:09+00:00',
          },
        ],
        early_nodes: [{ account_id: 'acct_delta', account_label: 'acct_delta', first_seen_at: '2026-05-21T00:00:09+00:00' }],
        top_nodes: [
          { account_id: 'acct_delta', account_label: 'acct_delta', cluster_degree: 6.9, first_seen_at: '2026-05-21T00:00:09+00:00' },
        ],
      },
    ],
  },
  account_stats: [
    {
      account_id: 'acct_beta',
      account_label: 'acct_beta',
      degree: 4,
      avg_weight: 3.13,
      avg_time_delta: 12.33,
      avg_edge_symmetry: 0.8,
      coordinated_shares_count: 5,
      shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
      content_previews: ['二次扩散统一口径文案', '同步转发摘要链接'],
    },
    {
      account_id: 'acct_delta',
      account_label: 'acct_delta',
      degree: 4,
      avg_weight: 2.87,
      avg_time_delta: 13.67,
      avg_edge_symmetry: 0.76,
      coordinated_shares_count: 5,
      shared_objects_preview: ['#联动话题扩散', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
      content_previews: ['从另一社区接力扩散链接', '图文同步转发统一海报'],
    },
    {
      account_id: 'acct_alpha',
      account_label: 'acct_alpha',
      degree: 3,
      avg_weight: 3.2,
      avg_time_delta: 10,
      avg_edge_symmetry: 0.84,
      coordinated_shares_count: 4,
      shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief', 'https://media.example/assets/banner-a.jpg'],
      content_previews: ['首批转发统一话题主帖', '沿用统一海报图传播'],
    },
    {
      account_id: 'acct_epsilon',
      account_label: 'acct_epsilon',
      degree: 2,
      avg_weight: 3.05,
      avg_time_delta: 11,
      avg_edge_symmetry: 0.81,
      coordinated_shares_count: 3,
      shared_objects_preview: ['#联动话题扩散', 'https://coord.example/shared-brief'],
      content_previews: ['快速转载图文卡片'],
    },
    {
      account_id: 'acct_gamma',
      account_label: 'acct_gamma',
      degree: 2,
      avg_weight: 2.8,
      avg_time_delta: 11.5,
      avg_edge_symmetry: 0.76,
      coordinated_shares_count: 3,
      shared_objects_preview: ['#联合话题', 'https://coord.example/shared-brief'],
      content_previews: ['跟进转发同主题话题'],
    },
    {
      account_id: 'acct_zeta',
      account_label: 'acct_zeta',
      degree: 1,
      avg_weight: 2.45,
      avg_time_delta: 13.5,
      avg_edge_symmetry: 0.74,
      coordinated_shares_count: 2,
      shared_objects_preview: ['https://media.example/assets/banner-a.jpg', 'https://coord.example/shared-brief'],
      content_previews: ['复用同一张海报图片'],
    },
  ],
  group_stats: [
    { object_id: '#联合话题', object_type: '话题', num_accounts: 4, num_pairs: 5 },
    { object_id: 'https://coord.example/shared-brief', object_type: '链接', num_accounts: 5, num_pairs: 6 },
    { object_id: 'https://media.example/assets/banner-a.jpg', object_type: '图片', num_accounts: 3, num_pairs: 3 },
  ],
  cluster_stats: [],
  summary: {
    event_id: 'preview-demo',
    platform: 'preview',
    total_posts: 18,
    total_comments: 9,
    total_items: 27,
    total_pairs: 18,
    coordinated_accounts: 6,
    coordinated_edges: 7,
    components: 1,
    cluster_count: 2,
  },
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
const authStore = useAuthStore()
const dataMode = ref<'live' | 'demo'>('live')

const params = reactive({ time_window: 60, min_participation: 2, edge_weight: 0.5 })

const hasNetwork = computed(() => Boolean(network.value?.nodes?.length && network.value?.edges?.length))

const clusterRoleMap = computed(() => {
  const roleMap = new Map<string, string[]>()
  const appendRole = (accountId: string, role: string) => {
    const current = roleMap.get(accountId) || []
    if (!current.includes(role)) {
      current.push(role)
      roleMap.set(accountId, current)
    }
  }

  ;(clusterStats.value as ClusterData[]).forEach((cluster) => {
    ;(cluster.core_nodes || cluster.top_nodes || []).forEach((item) => appendRole(String(item.account_id), '核心'))
    ;(cluster.bridge_nodes || []).forEach((item) => appendRole(String(item.account_id), '桥接'))
    ;(cluster.early_nodes || []).forEach((item) => appendRole(String(item.account_id), '早发'))
  })

  return roleMap
})

const clusterTableRows = computed(() =>
  (clusterStats.value as ClusterData[]).map((cluster) => ({
    ...cluster,
    core_nodes_preview: formatCoreNodes(cluster.core_nodes || cluster.top_nodes || []),
    bridge_nodes_preview: formatBridgeNodes(cluster.bridge_nodes || []),
    early_nodes_preview: formatEarlyNodes(cluster.early_nodes || []),
    shared_objects_preview_text: formatPreviewList(cluster.shared_objects_preview || cluster.shared_objects || []),
  })),
)

const accountTableRows = computed(() =>
  accountStats.value.map((account) => ({
    ...account,
    account_display: formatAccountName(account.account_label, account.account_id),
    shared_objects_display: formatPreviewList(account.shared_object_entries || account.shared_objects_preview || [], 8),
    content_previews_display: formatPreviewList(account.content_preview_entries || account.content_previews || [], 8),
  })),
)

const groupTableRows = computed(() =>
  groupStats.value.map((group) => ({
    ...group,
    object_display: formatGroupObject(group.object_type, group.object_id),
  })),
)

const nodeLabelMap = computed(() => {
  const labels = new Map<string, string>()
  ;(network.value?.nodes || []).forEach((node) => {
    labels.set(String(node.id), formatAccountName(node.account_label, node.id))
  })
  return labels
})

const usingPreviewDemo = computed(() => dataMode.value === 'demo')
const showPreviewAlert = computed(() => authStore.isPreviewMode || usingPreviewDemo.value)
const previewAlertTitle = computed(() =>
  usingPreviewDemo.value ? '当前显示的是示例协同网络' : '当前处于预览登录态',
)
const previewAlertDescription = computed(() =>
  usingPreviewDemo.value
    ? '图中的账号名称、链接与协同对象来自本地示例数据，仅用于界面预览，不代表真实检测结果。'
    : '页面会优先请求后端真实协同数据。若接口无数据或未检出协同行为，将保留真实空结果，不再自动伪造示例账号名称。',
)

const palette = ['#2563eb', '#059669', '#dc2626', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#16a34a']

const accountColumns = [
  {
    title: '账户',
    dataIndex: 'account_display',
    key: 'account_display',
    width: 200,
    customRender: ({ record }: any) => renderAccountCell(record),
  },
  { title: '度数', dataIndex: 'degree', key: 'degree', width: 90, sorter: (a: any, b: any) => a.degree - b.degree },
  { title: '加权度', dataIndex: 'avg_weight', key: 'avg_weight', width: 110, sorter: (a: any, b: any) => a.avg_weight - b.avg_weight },
  { title: '平均时差', dataIndex: 'avg_time_delta', key: 'avg_time_delta', width: 110 },
  { title: '对称性', dataIndex: 'avg_edge_symmetry', key: 'avg_edge_symmetry', width: 100 },
  { title: '协同分享数', dataIndex: 'coordinated_shares_count', key: 'coordinated_shares_count', width: 110 },
  {
    title: '协同对象',
    dataIndex: 'shared_object_entries',
    key: 'shared_object_entries',
    width: 420,
    customRender: ({ record }: any) => renderObjectListCell(record.shared_object_entries || record.shared_objects_preview || []),
  },
  {
    title: '内容示例',
    dataIndex: 'content_preview_entries',
    key: 'content_preview_entries',
    width: 340,
    customRender: ({ record }: any) => renderPreviewListCell(record.content_preview_entries || record.content_previews || []),
  },
]

const groupColumns = [
  { title: '对象类型', dataIndex: 'object_type', key: 'object_type', width: 100 },
  {
    title: '共享对象',
    dataIndex: 'object_display',
    key: 'object_display',
    width: 660,
    customRender: ({ record }: any) => renderSingleObjectCell(record.object_id, record.object_type),
  },
  { title: '涉及账户数', dataIndex: 'num_accounts', key: 'num_accounts', width: 120, sorter: (a: any, b: any) => a.num_accounts - b.num_accounts },
  { title: '协同配对数', dataIndex: 'num_pairs', key: 'num_pairs', width: 120, sorter: (a: any, b: any) => a.num_pairs - b.num_pairs },
]

const clusterColumns = [
  { title: '社区ID', dataIndex: 'cluster_id', key: 'cluster_id', width: 90, sorter: (a: any, b: any) => a.cluster_id - b.cluster_id },
  { title: '规模', dataIndex: 'size', key: 'size', width: 80, sorter: (a: any, b: any) => a.size - b.size },
  { title: '总权重', dataIndex: 'total_weight', key: 'total_weight', width: 100, sorter: (a: any, b: any) => a.total_weight - b.total_weight },
  { title: '平均度', dataIndex: 'avg_degree', key: 'avg_degree', width: 100, sorter: (a: any, b: any) => a.avg_degree - b.avg_degree },
  { title: '核心节点', dataIndex: 'core_nodes_preview', key: 'core_nodes_preview', width: 210, ellipsis: true },
  { title: '桥接节点', dataIndex: 'bridge_nodes_preview', key: 'bridge_nodes_preview', width: 210, ellipsis: true },
  { title: '早发节点', dataIndex: 'early_nodes_preview', key: 'early_nodes_preview', width: 210, ellipsis: true },
  {
    title: '协同对象',
    dataIndex: 'shared_objects',
    key: 'shared_objects',
    width: 320,
    customRender: ({ record }: any) => renderObjectListCell(record.shared_objects || record.shared_objects_preview || []),
  },
]

const accountLabelPaths = [
  ['account_label'],
  ['account_name'],
  ['author_name'],
  ['author_username'],
  ['author_screen_name'],
  ['author_nickname'],
  ['nickname'],
  ['screen_name'],
  ['user_name'],
  ['username'],
  ['display_name'],
  ['label'],
  ['name'],
  ['author_profile', 'author_name'],
  ['author_profile', 'display_name'],
  ['author_profile', 'screen_name'],
  ['author_profile', 'nickname'],
  ['author_profile', 'user_name'],
  ['author_profile', 'username'],
  ['author_profile', 'name'],
  ['raw_data', 'author_name'],
  ['raw_data', 'display_name'],
  ['raw_data', 'screen_name'],
  ['raw_data', 'nickname'],
  ['raw_data', 'username'],
  ['raw_data', 'user_name'],
  ['raw_data', 'user', 'screen_name'],
  ['raw_data', 'user', 'nickname'],
  ['raw_data', 'user', 'name'],
  ['raw_data', 'mblog', 'user', 'screen_name'],
  ['raw_data', 'mblog', 'user', 'nickname'],
  ['raw_data', 'mblog', 'user', 'name'],
  ['raw_data', 'post_details_raw', 'mblog', 'user', 'screen_name'],
  ['raw_data', 'post_details_raw', 'mblog', 'user', 'nickname'],
  ['raw_data', 'post_details_raw', 'mblog', 'user', 'name'],
]

function getNestedValue(source: any, path: string[]) {
  let current = source
  for (const key of path) {
    if (!current || typeof current !== 'object') {
      return ''
    }
    current = current[key]
  }
  return current
}

function resolveAccountLabel(source: any, fallbackId?: unknown) {
  const accountId = String(fallbackId ?? source?.account_id ?? source?.author_id ?? source?.id ?? '').trim()
  let fallback = ''
  for (const path of accountLabelPaths) {
    const value = String(getNestedValue(source, path) || '').trim()
    if (!value) continue
    if (!fallback) {
      fallback = value
    }
    if (value !== accountId) {
      return value
    }
  }
  return fallback || accountId || '-'
}

function normalizeClusterRepresentative(record: any) {
  return {
    ...record,
    account_label: resolveAccountLabel(record, record?.account_id),
  }
}

function normalizeClusterRecord(record: any): ClusterData {
  return {
    ...record,
    core_nodes: (record?.core_nodes || []).map((item: any) => normalizeClusterRepresentative(item)),
    bridge_nodes: (record?.bridge_nodes || []).map((item: any) => normalizeClusterRepresentative(item)),
    early_nodes: (record?.early_nodes || []).map((item: any) => normalizeClusterRepresentative(item)),
    top_nodes: (record?.top_nodes || []).map((item: any) => normalizeClusterRepresentative(item)),
  }
}

function normalizeNodeRecord(record: any): NodeData {
  return {
    ...record,
    account_label: resolveAccountLabel(record, record?.id),
  }
}

function normalizeAccountRecord(record: any) {
  return {
    ...record,
    account_label: resolveAccountLabel(record, record?.account_id),
  }
}

function hasRenderableDetection(data: any) {
  return Boolean(data?.network?.nodes?.length && data?.network?.edges?.length)
}

async function applyDetectionResult(data: any) {
  const normalizedClusters = ((data.cluster_stats?.length ? data.cluster_stats : data.network?.clusters) || []).map((cluster: any) =>
    normalizeClusterRecord(cluster),
  )
  const rawNetwork = data.network || { nodes: [], edges: [], clusters: [] }

  dataMode.value = 'live'
  summary.value = data.summary || null
  network.value = {
    ...rawNetwork,
    nodes: (rawNetwork.nodes || []).map((node: any) => normalizeNodeRecord(node)),
    edges: rawNetwork.edges || [],
    clusters: normalizedClusters,
  }
  accountStats.value = (data.account_stats || []).map((account: any) => normalizeAccountRecord(account))
  groupStats.value = data.group_stats || []
  clusterStats.value = normalizedClusters
  await nextTick()
  renderNetwork()
}

async function loadPreviewDetectionResult(notice?: string) {
  dataMode.value = 'demo'
  await applyDetectionResult({
    ...previewDetectionResult,
    cluster_stats: previewDetectionResult.network.clusters,
  })
  dataMode.value = 'demo'
  if (notice) {
    message.info(notice)
  }
}

async function runDetection(options: { silent?: boolean } = {}) {
  detecting.value = true
  try {
    const res = (await runCoordinationDetection(params)) as { data: any }
    const data = res.data
    await applyDetectionResult(data)

    if (data.error) {
      if (!options.silent) {
        message.warning(data.error)
      }
      return
    }

    if (!hasRenderableDetection(data)) {
      if (!options.silent) {
        message.info('未检测到满足当前阈值的协同行为，已保留真实空结果。')
      }
      return
    }

    if (!options.silent) {
      message.success(`检测完成：发现 ${data.summary?.coordinated_accounts ?? 0} 个协同账户`)
    }
  } catch (error) {
    if (!options.silent) {
      message.error('协同检测失败，请检查后端接口或数据库连接。')
    }
  } finally {
    detecting.value = false
  }
}

async function handleDetect() {
  await runDetection()
}

async function handleLoadDemo() {
  await loadPreviewDetectionResult('已加载本地示例网络，仅用于界面预览。')
}

function buildOption(): EChartsOption {
  const net = network.value
  if (!net) return {}

  const nodes = net.nodes.map((node) => ({
    ...node,
    name: formatAccountName(node.account_label, node.name || node.id),
    symbolSize: Math.max(18, Math.min(48, (node.cluster_degree || node.degree || 1) * 3)),
    category: node.cluster_id ?? 0,
    itemStyle: {
      color: palette[(node.cluster_id ?? 0) % palette.length],
    },
  }))

  const categories = clusterStats.value.map((cluster) => ({
    name: formatClusterLegend(cluster),
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
      enterable: true,
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
    const sourceLabel = nodeLabelMap.value.get(String(data.source)) || String(data.source)
    const targetLabel = nodeLabelMap.value.get(String(data.target)) || String(data.target)
    return [
      `<strong>${escapeHtml(sourceLabel)} → ${escapeHtml(targetLabel)}</strong>`,
      `权重：${data.weight ?? 0}`,
      `平均时差：${data.avg_time_delta ?? '-'}`,
      `对称性：${data.edge_symmetry_score ?? '-'}`,
      `协同对象：<br/>${formatTooltipList(data.shared_object_entries || data.shared_objects_preview || [], { linkify: true })}`,
      `内容示例：<br/>${formatTooltipList(data.shared_content_entries || data.shared_content_previews || [], { linkify: false })}`,
    ].join('<br/>')
  }
  const roles = clusterRoleMap.value.get(String(data.id || data.name || '')) || []
  const accountName = formatAccountName(data.account_label, data.name || data.id)
  return [
    `<strong>${escapeHtml(accountName)}</strong>`,
    data.account_label && data.id && data.account_label !== data.id
      ? `账户ID：${escapeHtml(String(data.id))}`
      : '',
    `cluster_id：${data.cluster_id ?? '-'}`,
    `cluster_size：${data.cluster_size ?? '-'}`,
    `cluster_degree：${data.cluster_degree ?? '-'}`,
    `角色：${roles.length ? roles.join(' / ') : '普通成员'}`,
    `bridge_score：${formatNumber(data.bridge_score)}`,
    `cross_cluster_weight：${data.cross_cluster_weight ?? 0}`,
    `首次出现：${data.first_seen_at ?? '-'}`,
    `协同对象数：${data.coordinated_object_count ?? 0}`,
    `协同内容数：${data.coordinated_content_count ?? 0}`,
    `协同对象：<br/>${formatTooltipList(data.shared_object_entries || data.shared_objects_preview || [], { linkify: true })}`,
    `内容示例：<br/>${formatTooltipList(data.content_preview_entries || data.content_previews || [], { linkify: false })}`,
  ]
    .filter(Boolean)
    .join('<br/>')
}

function formatNumber(value: unknown, digits = 4) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toFixed(digits).replace(/\.?0+$/, '')
}

function escapeHtml(value: unknown) {
  return String(value ?? '-')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function parseSafeExternalUrl(value: unknown) {
  const text = String(value || '').trim()
  if (!/^https?:\/\//i.test(text)) return null
  try {
    const parsed = new URL(text)
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    if (!parsed.hostname || parsed.username || parsed.password) return null
    return parsed.toString()
  } catch {
    return null
  }
}

function normalizePreviewItems(value: unknown, limit = 8) {
  if (!value) return []
  const source = Array.isArray(value) ? value : [value]
  return source
    .map((item) => {
      if (typeof item === 'string') {
        const text = item.trim()
        const href = parseSafeExternalUrl(text)
        return text ? { text: href || text, href, type: '' } : null
      }
      if (item && typeof item === 'object') {
        const hrefSource = item.object_id || item.primary_url || ''
        const href = parseSafeExternalUrl(hrefSource)
        const previewText = String(item.preview || item.content_preview || item.object_id || item.content_id || '').trim()
        const text = href || previewText
        return text
          ? {
              text,
              href,
              type: String(item.object_type || item.content_type || '').trim(),
            }
          : null
      }
      const text = String(item || '').trim()
      const href = parseSafeExternalUrl(text)
      return text ? { text: href || text, href, type: '' } : null
    })
    .filter((item): item is { text: string; href: string | null; type: string } => Boolean(item))
    .slice(0, limit)
}

function formatTooltipList(value: unknown, options: { linkify?: boolean; limit?: number } = {}) {
  const items = normalizePreviewItems(value, options.limit ?? 5)
  if (!items.length) return '-'
  return items
    .map((item) => {
      const label = item.type ? `[${item.type}] ${item.text}` : item.text
      if (options.linkify && item.href) {
        return `<a class="tooltip-link" href="${escapeHtml(item.href)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`
      }
      return escapeHtml(label)
    })
    .join('<br/>')
}

function formatAccountName(accountLabel: unknown, accountId: unknown) {
  const label = String(accountLabel || '').trim()
  const id = String(accountId || '').trim()
  return label || id || '-'
}

function formatGroupObject(objectType: unknown, objectId: unknown) {
  const preview = String(objectId || '').trim() || '-'
  const type = String(objectType || '').trim()
  return type ? `[${type}] ${preview}` : preview
}

function formatClusterLegend(cluster: ClusterData) {
  const clusterLabel = `社区 ${Number(cluster.cluster_id ?? 0) + 1}`
  const topObject = normalizePreviewItems(cluster.shared_objects || cluster.shared_objects_preview || [], 1)[0]
  if (!topObject) return clusterLabel
  const suffix = topObject.type ? `[${topObject.type}] ${topObject.text}` : topObject.text
  return `${clusterLabel} · ${suffix}`
}

function formatPreviewList(value: unknown, limit = 3) {
  const items = normalizePreviewItems(value, limit)
  if (!items.length) return '-'
  return items
    .map((item) => (item.type ? `[${item.type}] ${item.text}` : item.text))
    .join(' / ')
}

function renderAccountCell(record: any) {
  const label = formatAccountName(record.account_label, record.account_id)
  const accountId = String(record.account_id || '').trim()
  return h('div', { class: 'account-cell' }, [
    h('div', { class: 'account-cell__label' }, label),
    record.account_label && accountId && record.account_label !== accountId
      ? h('div', { class: 'account-cell__id' }, accountId)
      : null,
  ])
}

function renderSingleObjectCell(objectId: unknown, objectType?: unknown) {
  return renderObjectListCell([{ object_id: objectId, object_type: objectType, preview: objectId }], 1)
}

function renderObjectListCell(value: unknown, limit = 50) {
  const items = normalizePreviewItems(value, limit)
  if (!items.length) {
    return h('span', '-')
  }
  return h(
    'div',
    { class: 'object-link-list' },
    items.map((item) => {
      const label = item.type ? `[${item.type}] ${item.text}` : item.text
      return item.href
        ? h(
            'a',
            {
              class: 'object-link-list__item object-link-list__item--link',
              href: item.href,
              target: '_blank',
              rel: 'noreferrer',
              title: item.href,
            },
            label,
          )
        : h(
            'span',
            {
              class: 'object-link-list__item',
              title: item.text,
            },
            label,
          )
    }),
  )
}

function renderPreviewListCell(value: unknown, limit = 50) {
  const items = normalizePreviewItems(value, limit)
  if (!items.length) {
    return h('span', '-')
  }
  return h(
    'div',
    { class: 'preview-text-list' },
    items.map((item) =>
      h(
        'div',
        {
          class: 'preview-text-list__item',
          title: item.text,
        },
        item.text,
      ),
    ),
  )
}

function formatCoreNodes(nodes: ClusterRepresentative[]) {
  return nodes.length
    ? nodes
        .slice(0, 3)
        .map((node) => `${formatAccountName(node.account_label, node.account_id)} (度 ${node.cluster_degree ?? 0})`)
        .join(' / ')
    : '-'
}

function formatBridgeNodes(nodes: ClusterRepresentative[]) {
  return nodes.length
    ? nodes
        .slice(0, 3)
        .map((node) => `${formatAccountName(node.account_label, node.account_id)} (跨簇 ${node.cross_cluster_weight ?? 0})`)
        .join(' / ')
    : '-'
}

function formatEarlyNodes(nodes: ClusterRepresentative[]) {
  return nodes.length
    ? nodes
        .slice(0, 3)
        .map((node) => `${formatAccountName(node.account_label, node.account_id)} (${formatTime(node.first_seen_at)})`)
        .join(' / ')
    : '-'
}

function formatTime(value: unknown) {
  if (!value) return '-'
  const text = String(value)
  return text.replace('T', ' ').replace('+00:00', ' UTC')
}

function renderNetwork() {
  if (!networkRef.value) return
  if (!hasNetwork.value) {
    chart.value?.clear()
    return
  }
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

onMounted(() => {
  if (authStore.isPreviewMode) {
    void runDetection({ silent: true })
  }
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

:deep(.tooltip-link) {
  color: #2563eb;
  text-decoration: underline;
}

.account-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.account-cell__label {
  color: #111827;
  font-weight: 500;
}

.account-cell__id {
  color: #64748b;
  font-size: 12px;
}

.object-link-list,
.preview-text-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 300px;
}

.object-link-list__item,
.preview-text-list__item {
  color: #334155;
  line-height: 1.5;
  word-break: break-all;
}

.object-link-list__item--link {
  color: #2563eb;
  text-decoration: underline;
}
</style>
