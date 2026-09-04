<template>
  <div class="coordination-page">
    <PageHeader
      title="协同检测"
      description="查看历史协同数据集，展示 MAGNN + Leiden 的协同网络发现结果，以及 SBERT + fusion_gnn 的关键节点识别结果。"
    />

    <a-card size="small" class="panel">
      <div class="toolbar">
        <div class="toolbar-left">
          <a-button @click="loadDatasets" :loading="loadingDatasets">刷新数据集</a-button>
          <a-upload :show-upload-list="false" :before-upload="beforeUpload">
            <a-button type="primary" :loading="uploading">上传标准事件表</a-button>
          </a-upload>
        </div>
        <div class="toolbar-right">
          <a-button v-if="selectedDatasetId" type="primary" :loading="running" @click="handleRerun">
            重新运行主线模型
          </a-button>
        </div>
      </div>
    </a-card>

    <a-spin :spinning="loadingDetail">
      <template v-if="selectedDataset">
        <a-card size="small" class="panel">
          <template #title>
            <div class="network-panel-head">
              <span>协同网络发现</span>
              <a-select
                v-if="datasets.length"
                v-model:value="selectedDatasetId"
                class="dataset-select"
                size="middle"
                placeholder="选择数据集"
                @change="handleDatasetSelect"
              >
                <a-select-option v-for="item in datasets" :key="item.dataset_id" :value="item.dataset_id">
                  {{ datasetOptionLabel(item) }}
                </a-select-option>
              </a-select>
            </div>
          </template>
          <div class="network-toolbar">
            <div class="network-meta">
              <span>
                当前显示 {{ graphPayload?.summary?.rendered_node_count || 0 }} /
                {{ graphPayload?.summary?.total_nodes || resultSnapshot?.network?.total_nodes || 0 }} 个节点
              </span>
              <span>
                显示边 {{ graphPayload?.summary?.rendered_edge_count || 0 }} /
                {{ graphPayload?.summary?.total_edges || resultSnapshot?.network?.total_edges || 0 }}
              </span>
            </div>
            <div class="network-controls">
              <a-select v-model:value="nodeLimit" size="small" class="node-limit-select" @change="loadGraph">
                <a-select-option :value="50">前 50</a-select-option>
                <a-select-option :value="100">前 100</a-select-option>
                <a-select-option :value="200">前 200</a-select-option>
                <a-select-option :value="500">前 500</a-select-option>
                <a-select-option :value="1000">前 1000</a-select-option>
                <a-select-option :value="0">全部</a-select-option>
              </a-select>
              <div class="score-filter">
                <span>风险阈值</span>
                <a-slider
                  v-model:value="minNodeScore"
                  class="score-slider"
                  :min="0"
                  :max="1"
                  :step="0.01"
                  :tooltip-formatter="(value: number | undefined) => formatMetric(value)"
                  @change="scheduleGraphReload"
                />
                <span class="score-value">{{ formatMetric(minNodeScore) }}</span>
              </div>
              <a-switch v-model:checked="showNodeLabels" size="small" />
              <span class="switch-label">显示节点标签</span>
              <a-button size="small" @click="resetGraphCamera">重置视角</a-button>
            </div>
          </div>
          <CoordinationGraph3D
            ref="graph3dRef"
            :nodes="graphPayload?.nodes || []"
            :links="graphPayload?.links || []"
            :show-labels="showNodeLabels"
            :loading="loadingGraph"
            @node-click="handleNodeClick"
          />
        </a-card>

        <a-row :gutter="[16, 16]" class="panel-row panel-row--equal">
          <a-col :xs="24" :xl="12" class="stretch-col">
            <a-card size="small" title="社区发现结果" class="panel">
              <a-table
                :columns="communityColumns"
                :data-source="resultSnapshot?.communities || []"
                row-key="cluster_id"
                :pagination="{ pageSize: 8 }"
                size="small"
                :scroll="{ x: 960 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'cluster_id'">
                    <a class="table-action-link" @click.prevent="handleCommunityIdClick(record)">
                      {{ record.cluster_id }}
                    </a>
                  </template>
                  <template v-else-if="column.key === 'top_nodes'">
                    <div class="inline-link-list">
                      <a
                        v-for="nodeId in (record.top_nodes || []).slice(0, 5)"
                        :key="`${record.cluster_id}-${nodeId}`"
                        class="table-action-link"
                        @click.prevent="handleCommunityTopNodeClick(String(nodeId), record)"
                      >
                        {{ nodeId }}
                      </a>
                    </div>
                  </template>
                </template>
              </a-table>
            </a-card>
          </a-col>
          <a-col :xs="24" :xl="12" class="stretch-col">
            <a-card size="small" title="全局关键节点" class="panel">
              <a-table
                :columns="keyNodeColumns"
                :data-source="resultSnapshot?.global_key_nodes || []"
                row-key="account_id"
                :pagination="{ pageSize: 10 }"
                size="small"
                :scroll="{ x: 1100 }"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'account_id'">
                    <div class="account-cell">
                      <div class="account-main">
                        <a class="table-action-link account-nickname" @click.prevent="handleKeyNodeClick(record)">
                          {{ record.nickname || record.account_id }}
                        </a>
                        <a
                          v-if="record.profile_url"
                          class="external-link"
                          :href="record.profile_url"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                        >
                          主页
                        </a>
                      </div>
                      <div class="account-sub">{{ record.account_id }}</div>
                    </div>
                  </template>
                  <template v-else-if="column.key === 'cluster_id'">
                    <a class="table-action-link" @click.prevent="handleCommunityIdClick(record)">
                      {{ record.cluster_id }}
                    </a>
                  </template>
                </template>
              </a-table>
            </a-card>
          </a-col>
        </a-row>
      </template>

      <a-empty v-else class="panel" description="请选择一个历史数据集查看协同检测结果" />
    </a-spin>

    <a-drawer
      v-model:open="communityDrawerOpen"
      width="620"
      :title="drawerMode === 'community' ? '社区详情' : '账户详情'"
      placement="right"
      :destroy-on-close="false"
    >
      <a-spin :spinning="loadingCommunity">
        <template v-if="selectedNode || communityDetail">
          <div class="drawer-section">
            <div class="drawer-title">
              {{ drawerMode === 'community' ? `社区 ${communityDetail?.cluster_id ?? '-'}` : (selectedNode?.label || selectedNode?.id || '-') }}
            </div>
            <div class="drawer-grid">
              <div><span>{{ drawerMode === 'community' ? '社区 ID' : '账号' }}</span><strong>{{ drawerMode === 'community' ? (communityDetail?.cluster_id ?? '-') : (selectedNode?.id ?? '-') }}</strong></div>
              <div><span>{{ drawerMode === 'community' ? '成员规模' : '平台' }}</span><strong>{{ drawerMode === 'community' ? (communityDetail?.size ?? '-') : formatPlatformLabel(selectedNode?.platform) }}</strong></div>
              <div><span>{{ drawerMode === 'community' ? '社区分数' : '节点分数' }}</span><strong>{{ formatMetric(drawerMode === 'community' ? communityDetail?.community_score : selectedNode?.node_score) }}</strong></div>
              <div><span>{{ drawerMode === 'community' ? '对象集中度' : '社区分数' }}</span><strong>{{ formatMetric(drawerMode === 'community' ? communityDetail?.object_concentration : selectedNode?.community_score) }}</strong></div>
              <div><span>社区规模</span><strong>{{ communityDetail?.size ?? selectedNode?.community_size ?? '-' }}</strong></div>
              <div><span>密度</span><strong>{{ formatMetric(communityDetail?.density) }}</strong></div>
              <div><span>对象集中度</span><strong>{{ formatMetric(communityDetail?.object_concentration) }}</strong></div>
              <div><span>社区</span><strong>{{ selectedNode?.cluster_id ?? communityDetail?.cluster_id ?? '-' }}</strong></div>
            </div>
          </div>

          <div class="drawer-section">
            <div class="section-head">{{ drawerMode === 'community' ? '社区共享对象证据' : '该用户参与的共享对象证据' }}</div>
            <div v-if="communityDetail?.top_objects?.length" class="object-evidence-list">
              <div
                v-for="item in communityDetail?.top_objects || []"
                :key="`${item.relation || 'relation'}:${item.object_id}`"
                class="object-evidence-card"
              >
                <div class="object-evidence-head">
                  <div class="object-evidence-meta">
                    <a-tag color="blue">{{ item.relation_label || '共享对象' }}</a-tag>
                    <span>次数 {{ item.count ?? '-' }}</span>
                    <span>占比 {{ formatPercent(item.share) }}</span>
                  </div>
                  <a
                    v-if="item.object_url"
                    :href="item.object_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="object-evidence-link"
                  >
                    打开原始链接
                  </a>
                </div>
                <div class="object-evidence-value">{{ formatObjectDisplayText(item) }}</div>
                <div v-if="item.evidence_examples?.length" class="object-example-list">
                  <template v-if="drawerMode === 'account'">
                    <div v-if="getMyExamples(item.evidence_examples).length" class="object-example-group">
                      <div class="object-example-group-title">我的样例</div>
                      <div
                        v-for="(example, index) in getMyExamples(item.evidence_examples)"
                        :key="`${item.object_id}:mine:${index}`"
                        class="object-example-card object-example-card--mine"
                      >
                        <div class="object-example-head">
                          <strong>{{ example.nickname || example.account_id || '当前账号' }}</strong>
                          <a
                            v-if="example.post_url"
                            :href="example.post_url"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="object-example-link"
                          >
                            原帖
                          </a>
                        </div>
                        <div class="object-example-content">{{ example.content || '无内容摘要' }}</div>
                      </div>
                    </div>
                    <div v-if="getReferenceExamples(item.evidence_examples).length" class="object-example-group">
                      <div class="object-example-group-title">
                        {{ getMyExamples(item.evidence_examples).length ? '社区参考样例' : '样例' }}
                      </div>
                      <div
                        v-for="(example, index) in getReferenceExamples(item.evidence_examples)"
                        :key="`${item.object_id}:ref:${index}`"
                        class="object-example-card"
                      >
                        <div class="object-example-head">
                          <strong>{{ example.nickname || example.account_id || '样例账号' }}</strong>
                          <a
                            v-if="example.post_url"
                            :href="example.post_url"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="object-example-link"
                          >
                            原帖
                          </a>
                        </div>
                        <div class="object-example-content">{{ example.content || '无内容摘要' }}</div>
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    <div
                      v-for="(example, index) in getPreviewExamples(item.evidence_examples)"
                      :key="`${item.object_id}:example:${index}`"
                      class="object-example-card"
                    >
                      <div class="object-example-head">
                        <strong>{{ example.nickname || example.account_id || '样例账号' }}</strong>
                        <a
                          v-if="example.post_url"
                          :href="example.post_url"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="object-example-link"
                        >
                          原帖
                        </a>
                      </div>
                      <div class="object-example-content">{{ example.content || '无内容摘要' }}</div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
            <a-empty v-else description="暂无共享对象证据" />
          </div>

          <div class="drawer-section">
            <div class="section-head">社区成员</div>
            <a-table
              :columns="memberColumns"
              :data-source="communityDetail?.members || []"
              row-key="id"
              :pagination="{ pageSize: 8 }"
              size="small"
              :scroll="{ x: 900 }"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'id'">
                  <div class="account-cell">
                    <div class="account-main">
                      <a class="table-action-link account-nickname" @click.prevent="handleMemberClick(record)">
                        {{ record.nickname || record.id }}
                      </a>
                      <a
                        v-if="record.profile_url"
                        class="external-link"
                        :href="record.profile_url"
                        target="_blank"
                        rel="noopener noreferrer"
                        @click.stop
                      >
                        主页
                      </a>
                    </div>
                    <div class="account-sub">{{ record.id }}</div>
                  </div>
                </template>
              </template>
            </a-table>
          </div>
        </template>
        <a-empty v-else description="点击网络节点查看社区详情" />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { message } from 'ant-design-vue'

import PageHeader from '@/components/PageHeader.vue'
import {
  createCoordinationRun,
  getCoordinationCommunityDetail,
  getCoordinationDatasetDetail,
  getCoordinationDatasetLatestResult,
  getCoordinationGraph,
  getCoordinationRun,
  listCoordinationDatasets,
  uploadCoordinationDataset,
} from '@/api/coordination'
import type { CoordinationCommunityDetail, CoordinationGraphNode, CoordinationGraphPayload } from '@/api/coordination'
import CoordinationGraph3D from './CoordinationGraph3D.vue'

type DatasetItem = {
  dataset_id: number
  slug?: string
  display_name: string
  source_type: string
  has_labels: boolean
  event_rows: number
  account_nodes: number
  object_ids: number
  user_user_edges: number
  available_relations: string[]
  latest_status?: string
  latest_metrics?: Record<string, number | null>
}

const datasets = ref<DatasetItem[]>([])
const selectedDatasetId = ref<number | null>(null)
const datasetDetail = ref<any>(null)
const resultSnapshot = ref<any>(null)
const loadingDatasets = ref(false)
const loadingDetail = ref(false)
const loadingResult = ref(false)
const loadingGraph = ref(false)
const loadingCommunity = ref(false)
const uploading = ref(false)
const running = ref(false)
const pollingRunId = ref<number | null>(null)
const graphPayload = ref<CoordinationGraphPayload | null>(null)
const nodeLimit = ref<number>(200)
const minNodeScore = ref<number>(0)
const showNodeLabels = ref(false)
const graph3dRef = ref<InstanceType<typeof CoordinationGraph3D> | null>(null)
const communityDrawerOpen = ref(false)
const selectedNode = ref<CoordinationGraphNode | null>(null)
const communityDetail = ref<CoordinationCommunityDetail | null>(null)
const drawerMode = ref<'account' | 'community'>('account')
let pollTimer: number | null = null
let graphReloadTimer: number | null = null
let datasetDetailRequestGeneration = 0
let latestResultRequestGeneration = 0
let graphRequestGeneration = 0
let communityDetailRequestGeneration = 0

const selectedDataset = computed(() =>
  datasets.value.find((item) => item.dataset_id === selectedDatasetId.value) || null,
)

const communityColumns = [
  { title: '社区 ID', dataIndex: 'cluster_id', key: 'cluster_id', width: 90 },
  { title: '规模', dataIndex: 'size', key: 'size', width: 80 },
  { title: '社区分数', dataIndex: 'community_score', key: 'community_score', width: 110, customRender: ({ text }: any) => formatMetric(text) },
  { title: '密度', dataIndex: 'density', key: 'density', width: 90, customRender: ({ text }: any) => formatMetric(text) },
  { title: '对象集中度', dataIndex: 'object_concentration', key: 'object_concentration', width: 120, customRender: ({ text }: any) => formatMetric(text) },
  {
    title: '关键节点',
    dataIndex: 'top_nodes',
    key: 'top_nodes',
    width: 300,
    customRender: ({ record }: any) => (record.top_nodes || []).slice(0, 5).join(', '),
  },
]

const keyNodeColumns = [
  { title: '账号', dataIndex: 'account_id', key: 'account_id', width: 240 },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 90, customRender: ({ text }: any) => formatPlatformLabel(text) },
  { title: '节点分数', dataIndex: 'node_score', key: 'node_score', width: 120, customRender: ({ text }: any) => formatMetric(text) },
  { title: '社区 ID', dataIndex: 'cluster_id', key: 'cluster_id', width: 90 },
  { title: '社区分数', dataIndex: 'community_score', key: 'community_score', width: 110, customRender: ({ text }: any) => formatMetric(text) },
  { title: '社区规模', dataIndex: 'community_size', key: 'community_size', width: 100 },
  {
    title: '共享对象',
    dataIndex: 'shared_objects',
    key: 'shared_objects',
    width: 340,
    customRender: ({ record }: any) => formatSharedObjectPreview(record.shared_objects),
  },
]

const memberColumns = [
  { title: '账号', dataIndex: 'id', key: 'id', width: 240 },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 90, customRender: ({ text }: any) => formatPlatformLabel(text) },
  { title: '节点分数', dataIndex: 'node_score', key: 'node_score', width: 110, customRender: ({ text }: any) => formatMetric(text) },
  { title: '出向权重', dataIndex: 'directed_out_weight', key: 'directed_out_weight', width: 110, customRender: ({ text }: any) => formatMetric(text) },
  { title: '入向权重', dataIndex: 'directed_in_weight', key: 'directed_in_weight', width: 110, customRender: ({ text }: any) => formatMetric(text) },
]

const communityNodeMap = computed(() => {
  const mapping = new Map<string, any>()
  const communities = Array.isArray(resultSnapshot.value?.communities) ? resultSnapshot.value.communities : []
  const keyNodes = Array.isArray(resultSnapshot.value?.global_key_nodes) ? resultSnapshot.value.global_key_nodes : []
  for (const node of keyNodes) {
    if (node?.account_id) {
      mapping.set(String(node.account_id), node)
    }
  }
  for (const community of communities) {
    const topNodes = Array.isArray(community?.top_nodes) ? community.top_nodes : []
    for (const nodeId of topNodes) {
      const key = String(nodeId)
      if (!mapping.has(key)) {
        mapping.set(key, {
          account_id: key,
          nickname: key,
          cluster_id: community?.cluster_id,
          community_score: community?.community_score,
          community_size: community?.size,
        })
      }
    }
  }
  return mapping
})

async function loadDatasets() {
  loadingDatasets.value = true
  try {
    const resp = await listCoordinationDatasets()
    datasets.value = resp.data || []
    if (!selectedDatasetId.value && datasets.value.length) {
      const preferredDataset =
        datasets.value.find((item) => isPreferredRealDataset(item) && item.latest_status === 'completed') ||
        datasets.value.find((item) => isPreferredRealDataset(item) && item.latest_status === 'archived') ||
        datasets.value.find((item) => item.latest_status === 'completed') ||
        datasets.value.find((item) => item.slug === 'russia') ||
        datasets.value[0]
      selectedDatasetId.value = preferredDataset.dataset_id
    }
  } finally {
    loadingDatasets.value = false
  }
}

async function handleDatasetSelect(datasetId: number) {
  await selectDataset(datasetId)
}

async function selectDataset(datasetId: number) {
  selectedDatasetId.value = datasetId
  datasetDetailRequestGeneration += 1
  latestResultRequestGeneration += 1
  graphRequestGeneration += 1
  communityDetailRequestGeneration += 1
  communityDrawerOpen.value = false
  selectedNode.value = null
  communityDetail.value = null
  datasetDetail.value = null
  resultSnapshot.value = null
  graphPayload.value = null
  stopPolling()
  running.value = false
  try {
    await Promise.all([loadDatasetDetail(datasetId), loadGraph()])
  } finally {
    if (selectedDatasetId.value === datasetId) {
      void loadLatestResult(datasetId)
    }
  }
}

async function loadDatasetDetail(datasetId: number) {
  const requestGeneration = ++datasetDetailRequestGeneration
  loadingDetail.value = true
  try {
    const resp = await getCoordinationDatasetDetail(datasetId)
    if (
      requestGeneration !== datasetDetailRequestGeneration
      || datasetId !== selectedDatasetId.value
    ) {
      return
    }
    datasetDetail.value = resp.data
  } finally {
    if (
      requestGeneration === datasetDetailRequestGeneration
      && datasetId === selectedDatasetId.value
    ) {
      loadingDetail.value = false
    }
  }
}

async function loadLatestResult(datasetId: number) {
  const requestGeneration = ++latestResultRequestGeneration
  loadingResult.value = true
  try {
    const resp = await getCoordinationDatasetLatestResult(datasetId)
    if (
      requestGeneration !== latestResultRequestGeneration
      || datasetId !== selectedDatasetId.value
    ) {
      return
    }
    resultSnapshot.value = resp.data
  } finally {
    if (
      requestGeneration === latestResultRequestGeneration
      && datasetId === selectedDatasetId.value
    ) {
      loadingResult.value = false
    }
  }
}

async function loadGraph() {
  const requestedDatasetId = selectedDatasetId.value
  if (!requestedDatasetId) return
  const requestGeneration = ++graphRequestGeneration
  loadingGraph.value = true
  try {
    const resp = await getCoordinationGraph(requestedDatasetId, {
      node_limit: nodeLimit.value,
      min_node_score: minNodeScore.value,
    })
    if (
      requestGeneration !== graphRequestGeneration
      || requestedDatasetId !== selectedDatasetId.value
    ) {
      return
    }
    graphPayload.value = resp.data
  } finally {
    if (
      requestGeneration === graphRequestGeneration
      && requestedDatasetId === selectedDatasetId.value
    ) {
      loadingGraph.value = false
    }
  }
}

function scheduleGraphReload() {
  if (graphReloadTimer !== null) {
    window.clearTimeout(graphReloadTimer)
  }
  graphReloadTimer = window.setTimeout(() => {
    graphReloadTimer = null
    loadGraph()
  }, 180)
}

function resetGraphCamera() {
  graph3dRef.value?.resetCamera()
}

async function openCommunityDetail(
  clusterId: string | number | null | undefined,
  options: { preserveSelectedNode?: boolean } = {},
) {
  if (!selectedDatasetId.value || clusterId === null || clusterId === undefined) return
  const requestedDatasetId = selectedDatasetId.value
  const requestGeneration = ++communityDetailRequestGeneration
  drawerMode.value = 'community'
  communityDrawerOpen.value = true
  loadingCommunity.value = true
  try {
    const resp = await getCoordinationCommunityDetail(requestedDatasetId, clusterId)
    if (
      requestGeneration !== communityDetailRequestGeneration
      || requestedDatasetId !== selectedDatasetId.value
    ) {
      return
    }
    communityDetail.value = resp.data
    if (!options.preserveSelectedNode) {
      selectedNode.value = null
    }
  } finally {
    if (
      requestGeneration === communityDetailRequestGeneration
      && requestedDatasetId === selectedDatasetId.value
    ) {
      loadingCommunity.value = false
    }
  }
}

async function openAccountDetail(nodeLike: any) {
  const accountId = String(nodeLike?.id || nodeLike?.account_id || '')
  if (!accountId) return
  drawerMode.value = 'account'
  selectedNode.value = {
    id: accountId,
    label: String(nodeLike?.nickname || nodeLike?.label || accountId),
    nickname: nodeLike?.nickname || nodeLike?.label || accountId,
    platform: nodeLike?.platform || null,
    profile_url: nodeLike?.profile_url || null,
    cluster_id: nodeLike?.cluster_id ?? null,
    node_score: nodeLike?.node_score ?? null,
    community_score: nodeLike?.community_score ?? null,
    community_size: nodeLike?.community_size ?? null,
  }
  communityDrawerOpen.value = true
  communityDetail.value = null
  if (selectedNode.value.cluster_id === null || selectedNode.value.cluster_id === undefined) return
  await openCommunityDetail(selectedNode.value.cluster_id, { preserveSelectedNode: true })
  drawerMode.value = 'account'
}

async function handleNodeClick(node: CoordinationGraphNode) {
  await openAccountDetail(node)
}

async function handleCommunityIdClick(record: any) {
  await openCommunityDetail(record?.cluster_id)
}

async function handleKeyNodeClick(record: any) {
  await openAccountDetail(record)
}

async function handleMemberClick(record: any) {
  await openAccountDetail({
    ...record,
    cluster_id: communityDetail.value?.cluster_id ?? selectedNode.value?.cluster_id ?? null,
    community_score: communityDetail.value?.community_score ?? selectedNode.value?.community_score ?? null,
    community_size: communityDetail.value?.size ?? selectedNode.value?.community_size ?? null,
  })
}

async function handleCommunityTopNodeClick(accountId: string, communityRecord: any) {
  const fallback = communityNodeMap.value.get(String(accountId)) || {}
  await openAccountDetail({
    ...fallback,
    account_id: String(accountId),
    nickname: fallback?.nickname || String(accountId),
    cluster_id: communityRecord?.cluster_id ?? fallback?.cluster_id ?? null,
    community_score: communityRecord?.community_score ?? fallback?.community_score ?? null,
    community_size: communityRecord?.size ?? fallback?.community_size ?? null,
  })
}

async function beforeUpload(file: File) {
  uploading.value = true
  try {
    const resp = await uploadCoordinationDataset(file)
    message.success('数据集上传成功')
    await loadDatasets()
    if (resp.data?.dataset_id) {
      await selectDataset(resp.data.dataset_id)
    }
  } finally {
    uploading.value = false
  }
  return false
}

async function handleRerun() {
  if (!selectedDatasetId.value) return
  const requestedDatasetId = selectedDatasetId.value
  running.value = true
  try {
    const resp = await createCoordinationRun(requestedDatasetId)
    const runId = resp.data?.run_id
    if (!runId) {
      throw new Error('未返回运行任务 ID')
    }
    pollingRunId.value = runId
    message.success(`已提交运行任务 #${runId}`)
    if (requestedDatasetId !== selectedDatasetId.value) return
    await loadDatasetDetail(requestedDatasetId)
    if (requestedDatasetId !== selectedDatasetId.value) return
    startPolling(runId, requestedDatasetId)
  } catch (error: any) {
    running.value = false
    throw error
  }
}

function startPolling(runId: number, datasetId = selectedDatasetId.value) {
  stopPolling()
  const requestedDatasetId = datasetId
  const loop = async () => {
    try {
      const resp = await getCoordinationRun(runId)
      if (
        requestedDatasetId !== selectedDatasetId.value
        || pollingRunId.value !== runId
      ) {
        return
      }
      const run = resp.data
      if (datasetDetail.value?.runs?.length) {
        datasetDetail.value.runs = [run, ...datasetDetail.value.runs.filter((item: any) => item.run_id !== run.run_id)].slice(0, 10)
      }
      if (run.status === 'completed') {
        stopPolling()
        running.value = false
        if (selectedDatasetId.value) {
          await Promise.all([loadDatasets(), loadDatasetDetail(selectedDatasetId.value), loadLatestResult(selectedDatasetId.value), loadGraph()])
        }
        message.success('协同检测模型运行完成')
        return
      }
      if (run.status === 'failed') {
        stopPolling()
        running.value = false
        await loadDatasetDetail(selectedDatasetId.value as number)
        message.error(run.error || '协同检测模型运行失败')
        return
      }
    } catch {
      if (
        requestedDatasetId !== selectedDatasetId.value
        || pollingRunId.value !== runId
      ) {
        return
      }
      stopPolling()
      running.value = false
      return
    }
    pollTimer = window.setTimeout(loop, 3000)
  }
  loop()
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer)
    pollTimer = null
  }
}

function formatMetric(value: any) {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toFixed(4) : String(value)
}

function formatPercent(value: any) {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(2)}%` : String(value)
}

function formatRelationLabel(value: any) {
  const mapping: Record<string, string> = {
    url_share: '共享 URL',
    hashtag_share: '共享话题',
    retweet_target: '同转推目标',
    reply_target: '同回复目标',
    quote_target: '同引用目标',
    mention_target: '同提及目标',
    fast_retweet: '快速转推',
    tweet_similarity: '文本相似',
    courl: '共链 URL',
    cort: '共转推',
    fastrt: '快速转推',
    hashseq: '话题序列',
    profile: '账号画像',
  }
  const key = String(value || '').toLowerCase()
  return mapping[key] || String(value || '-')
}

function formatPlatformLabel(value: any) {
  const key = String(value || '').toLowerCase()
  if (!key) {
    if (isPreferredRealDataset(selectedDataset.value)) return '微博'
    return '-'
  }
  if (key === 'weibo') return '微博'
  if (key === 'twitter') return 'X/Twitter'
  if (key === 'xiaohongshu') return '小红书'
  if (key === 'douyin') return '抖音'
  return String(value)
}

function formatSharedObjectPreview(value: any) {
  const items = Array.isArray(value) ? value : []
  if (!items.length) return '-'
  return items
    .slice(0, 2)
    .map((item: any) => {
      const relation = item?.relation_label || formatRelationLabel(item?.relation)
      const objectText = item?.display_value || item?.object_url || item?.object_id || '-'
      return `${relation}：${objectText}`
    })
    .join('；')
}

function isPreferredRealDataset(item: DatasetItem | null | undefined) {
  const slug = String(item?.slug || '').toLowerCase()
  const name = String(item?.display_name || '').toLowerCase()
  return slug.includes('weibo-trump-visit-2026-05-21-2') || name.includes('weibo trump visit 2026-05-21')
}

function datasetOptionLabel(item: DatasetItem) {
  const source = item.source_type === 'system_archive' ? '归档' : '上传'
  const tag = isPreferredRealDataset(item) ? '真实微博' : source
  return `${item.display_name} · ${tag}`
}

function formatObjectDisplayText(item: any) {
  return item?.display_value || item?.object_url || item?.object_id || '-'
}

function splitExamplesForSelectedNode(examples: any[] | undefined) {
  const rows = Array.isArray(examples) ? examples : []
  const selectedId = String(selectedNode.value?.id || '')
  if (!selectedId) {
    return {
      mine: [] as any[],
      refs: rows.slice(0, 3),
    }
  }

  const matched = rows.filter((example: any) => String(example?.account_id || '') === selectedId)
  const rest = rows.filter((example: any) => String(example?.account_id || '') !== selectedId)
  return {
    mine: matched.slice(0, 3),
    refs: (matched.length ? rest : rows).slice(0, 3),
  }
}

function getMyExamples(examples: any[] | undefined) {
  return splitExamplesForSelectedNode(examples).mine
}

function getReferenceExamples(examples: any[] | undefined) {
  return splitExamplesForSelectedNode(examples).refs
}

function getPreviewExamples(examples: any[] | undefined) {
  const rows = Array.isArray(examples) ? examples : []
  return rows.slice(0, 3)
}

onBeforeUnmount(() => {
  stopPolling()
  if (graphReloadTimer !== null) {
    window.clearTimeout(graphReloadTimer)
    graphReloadTimer = null
  }
})

loadDatasets().then(async () => {
  if (selectedDatasetId.value) {
    await selectDataset(selectedDatasetId.value)
  }
})
</script>

<style scoped>
.coordination-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  border-radius: 14px;
}

.panel-row {
  margin-top: 0;
}

.panel-row--equal {
  align-items: stretch;
}

.stretch-col {
  display: flex;
}

.stretch-col :deep(.ant-card) {
  width: 100%;
}

.stretch-col :deep(.ant-card-body) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.stretch-col :deep(.ant-table-wrapper) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.stretch-col :deep(.ant-spin-nested-loading),
.stretch-col :deep(.ant-spin-container),
.stretch-col :deep(.ant-table) {
  height: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.network-panel-head {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.dataset-select {
  min-width: 320px;
}

.summary-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-item span {
  color: #64748b;
  font-size: 12px;
}

.summary-item strong {
  color: #0f172a;
  font-size: 14px;
  word-break: break-all;
}

.network-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 13px;
}

.network-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.network-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.node-limit-select {
  width: 124px;
}

.score-filter {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 320px;
  color: #475569;
  font-size: 13px;
}

.score-slider {
  flex: 1;
  min-width: 180px;
  margin: 0 4px;
}

.score-value {
  min-width: 52px;
  color: #0f172a;
  font-weight: 600;
}

.switch-label {
  color: #475569;
  font-size: 13px;
}

.account-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.account-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.account-nickname {
  color: #0f172a;
  font-weight: 600;
  word-break: break-word;
}

.account-sub {
  color: #64748b;
  font-size: 12px;
  word-break: break-all;
}

.external-link {
  color: #2563eb;
  font-size: 12px;
  text-decoration: none;
}

.external-link:hover {
  text-decoration: underline;
}

.table-action-link {
  color: #2563eb;
  text-decoration: none;
  cursor: pointer;
}

.table-action-link:hover {
  text-decoration: underline;
}

.inline-link-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.drawer-section {
  margin-bottom: 22px;
}

.drawer-title {
  margin-bottom: 12px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
  word-break: break-all;
}

.drawer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.drawer-grid div {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-grid span {
  color: #64748b;
  font-size: 12px;
}

.drawer-grid strong {
  color: #0f172a;
  font-size: 14px;
  word-break: break-all;
}

.section-head {
  margin-bottom: 10px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.object-evidence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.object-evidence-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.object-evidence-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.object-evidence-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: #475569;
  font-size: 12px;
}

.object-evidence-link,
.object-example-link {
  color: #2563eb;
  font-size: 12px;
  text-decoration: none;
}

.object-evidence-link:hover,
.object-example-link:hover {
  text-decoration: underline;
}

.object-evidence-value {
  margin-top: 10px;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-all;
}

.object-example-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.object-example-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.object-example-group-title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.object-example-card {
  border-radius: 12px;
  background: #f8fafc;
  padding: 10px 12px;
}

.object-example-card--mine {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.object-example-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.object-example-head strong {
  color: #0f172a;
  font-size: 13px;
  word-break: break-all;
}

.object-example-content {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

@media (max-width: 960px) {
  .network-panel-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .dataset-select {
    min-width: 100%;
  }

  .network-toolbar {
    align-items: flex-start;
  }

  .network-controls {
    justify-content: flex-start;
  }

  .score-filter {
    min-width: 100%;
  }

  .drawer-grid {
    grid-template-columns: 1fr;
  }
}
</style>
