<template>
  <div class="coordination-page">
    <PageHeader
      title="协同检测"
      description="以群组为中心查看跨平台证据、协同结构和检测提示；模型输出只作为证据提示，最终结论由分析员确认。"
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
            运行归档复现
          </a-button>
        </div>
      </div>
    </a-card>

    <a-spin :spinning="loadingDetail || loadingResult">
      <div v-if="datasetDetailError" class="resource-error resource-error--detail" role="alert">
        <div>
          <strong>数据集详情加载失败</strong>
          <p>{{ datasetDetailError }}</p>
        </div>
        <a-button size="small" @click="retryDatasetDetail">重试数据集详情</a-button>
      </div>

      <div v-if="latestResultError" class="resource-error resource-error--result" role="alert">
        <div>
          <strong>历史结果加载失败</strong>
          <p>{{ latestResultError }}</p>
        </div>
        <a-button size="small" @click="retryLatestResult">重试历史结果</a-button>
      </div>

      <template v-if="selectedDataset && resultSnapshot">
        <section class="workbench-panel" aria-label="协同检测概览">
          <div v-if="detectionUnavailable" class="detection-status-strip" role="status">
            <div>
              <strong>检测结果暂不可用</strong>
              <p>{{ detectionUnavailableReason }}</p>
            </div>
            <span>协同结构与四维证据仍可用于人工核查。</span>
          </div>
          <div class="workbench-metrics">
            <div v-for="item in workbenchMetrics" :key="item.label" class="summary-item">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.hint }}</small>
            </div>
          </div>
        </section>

        <section class="characterization-panel" aria-labelledby="characterization-title">
          <div class="characterization-panel-head">
            <h2 id="characterization-title">四维刻画</h2>
            <a-tag v-if="activeCharacterizationClusterId" color="geekblue">
              群组 {{ activeCharacterizationClusterId }}
            </a-tag>
          </div>
          <div class="dimension-grid">
            <div
              v-for="item in characterizationDimensions"
              :key="item.key"
              class="dimension-card"
            >
              <div class="dimension-card-head">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <p>{{ item.summary }}</p>
              <small>{{ item.evidence }}</small>
            </div>
          </div>
        </section>

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
                <span>协同证据阈值</span>
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
          <p id="coordination-network-summary" class="network-summary">
            {{ networkAccessibilitySummary }}
          </p>
          <a-spin :spinning="loadingGraph">
            <div v-if="graphError" class="resource-error resource-error--graph" role="alert">
              <div>
                <strong>协同网络加载失败</strong>
                <p>{{ graphError }}</p>
              </div>
              <a-button size="small" @click="retryGraph">重试协同网络</a-button>
            </div>
            <CoordinationGraph3D
              v-else-if="graphPayload?.nodes?.length"
              ref="graph3dRef"
              :nodes="graphPayload.nodes"
              :links="graphPayload.links"
              :show-labels="showNodeLabels"
              :loading="loadingGraph"
              :active="pageActive"
              @node-click="handleNodeClick"
            />
            <a-empty
              v-else-if="!loadingGraph"
              class="graph-empty-state"
              description="暂无可展示的协同网络数据"
            />
          </a-spin>
        </a-card>

        <a-row :gutter="[16, 16]" class="panel-row panel-row--equal">
          <a-col :xs="24" :xl="12" class="stretch-col">
            <a-card size="small" title="社区发现结果" class="panel">
              <a-table
                :columns="communityColumns"
                :data-source="communityRows"
                row-key="cluster_id"
                :pagination="{ pageSize: 8 }"
                size="small"
                :scroll="{ x: 1160 }"
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
                  <template v-else-if="column.key === 'detection'">
                    <div class="table-verdict">
                      <a-tag :color="detectionTagColor(record.detection_verdict)">
                        {{ detectionDecisionLabel(record.detection_verdict) }}
                      </a-tag>
                      <span>{{ formatPercent(record.detection_verdict?.harmful_probability) }}</span>
                    </div>
                  </template>
                </template>
              </a-table>
            </a-card>
          </a-col>
          <a-col :xs="24" :xl="12" class="stretch-col">
            <a-card size="small" title="证据关键节点" class="panel">
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

      <a-empty v-else-if="!selectedDatasetId" class="panel" description="请选择一个历史数据集查看协同检测结果" />
      <a-empty v-else-if="!latestResultError && !loadingResult" class="panel" description="暂无历史协同检测结果" />
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
              <div><span>{{ drawerMode === 'community' ? '社区分数' : '证据分数' }}</span><strong>{{ formatMetric(drawerMode === 'community' ? communityDetail?.community_score : selectedNode?.node_score) }}</strong></div>
              <div><span>{{ drawerMode === 'community' ? '对象集中度' : '社区分数' }}</span><strong>{{ formatMetric(drawerMode === 'community' ? communityDetail?.object_concentration : selectedNode?.community_score) }}</strong></div>
              <div><span>社区规模</span><strong>{{ communityDetail?.size ?? selectedNode?.community_size ?? '-' }}</strong></div>
              <div><span>密度</span><strong>{{ formatMetric(communityDetail?.density) }}</strong></div>
              <div><span>对象集中度</span><strong>{{ formatMetric(communityDetail?.object_concentration) }}</strong></div>
              <div><span>社区</span><strong>{{ selectedNode?.cluster_id ?? communityDetail?.cluster_id ?? '-' }}</strong></div>
            </div>
          </div>

          <div class="drawer-section">
            <div class="section-head">四维刻画</div>
            <div class="dimension-grid dimension-grid--drawer">
              <div
                v-for="item in characterizationDimensions"
                :key="`drawer-${item.key}`"
                class="dimension-card"
              >
                <div class="dimension-card-head">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
                <p>{{ item.summary }}</p>
                <small>{{ item.evidence }}</small>
              </div>
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
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
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
const datasetDetailError = ref<string | null>(null)
const latestResultError = ref<string | null>(null)
const graphError = ref<string | null>(null)
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
const pageActive = ref(false)

const networkAccessibilitySummary = computed(() => {
  const summary = graphPayload.value?.summary
  const nodes = Number(summary?.total_nodes ?? resultSnapshot.value?.network?.total_nodes ?? 0)
  const edges = Number(summary?.total_edges ?? resultSnapshot.value?.network?.total_edges ?? 0)
  const communities = communityRows.value.length
  if (!nodes && !edges && !communities) return '当前没有可读的网络摘要。'
  return `当前网络包含 ${formatInteger(nodes)} 个账号节点、${formatInteger(edges)} 条关联边，识别出 ${formatInteger(communities)} 个候选群组。图谱用于定位关系，详细证据请查看下方列表。`
})
let pollTimer: number | null = null
let graphReloadTimer: number | null = null
let initialDatasetLoad: Promise<void> | null = null
let graphRequestGeneration = 0
let datasetDetailRequestGeneration = 0
let latestResultRequestGeneration = 0

const selectedDataset = computed(() =>
  datasets.value.find((item) => item.dataset_id === selectedDatasetId.value) || null,
)

const coordinationResolution = computed(() => resultSnapshot.value?.coordination_resolution || null)
const resolutionReport = computed(() => coordinationResolution.value?.resolution_report || {})
const coordinationDiscovery = computed(() => resultSnapshot.value?.coordination_discovery || null)
const coordinationDetection = computed(() => resultSnapshot.value?.coordination_detection || null)
const detectionPrimaryRole = 'primary_socgfm_cross_attention'
const detectionStatus = computed(() => String(coordinationDetection.value?.status || resultSnapshot.value?.detection_status || 'not_connected'))
const detectionUnavailable = computed(() => ['model_unavailable', 'data_insufficient', 'not_connected'].includes(detectionStatus.value))
const detectionUnavailableReason = computed(() => {
  if (coordinationDetection.value?.blocking_reason) return String(coordinationDetection.value.blocking_reason)
  if (detectionStatus.value === 'not_connected') return '当前历史结果未包含检测提示，仅展示协同发现证据。'
  if (detectionStatus.value === 'data_insufficient') return '候选群组不足，无法形成检测提示。'
  return '未找到可用的协同攻击检测模型产物，系统不会回退到启发式结果。'
})

const detectionVerdicts = computed(() => (
  Array.isArray(coordinationDetection.value?.verdicts) ? coordinationDetection.value.verdicts : []
))
const primaryDetectionVerdicts = computed(() => (
  detectionVerdicts.value.filter((verdict: any) => {
    return String(verdict?.model_role || '').trim() === detectionPrimaryRole
  })
))

const detectionVerdictMap = computed(() => {
  const mapping = new Map<string, any>()
  for (const verdict of primaryDetectionVerdicts.value) {
    const clusterId = String(verdict?.cluster_id || '').trim()
    if (clusterId) mapping.set(clusterId, verdict)
  }
  return mapping
})

const communityRows = computed(() => {
  const rows = Array.isArray(resultSnapshot.value?.communities) ? resultSnapshot.value.communities : []
  return rows.map((community: any) => ({
    ...community,
    detection_verdict: detectionVerdictForCluster(community?.cluster_id),
  }))
})

const highRiskClusterCount = computed(() => (
  primaryDetectionVerdicts.value.filter((verdict: any) => isHighRiskVerdict(verdict)).length
))

const averageEvidenceCoverage = computed(() => {
  const clusters = Array.isArray(coordinationDiscovery.value?.candidate_clusters)
    ? coordinationDiscovery.value.candidate_clusters
    : []
  const values = clusters
    .map((cluster: any) => Number(cluster?.coordination_metrics?.evidence_coverage))
    .filter((value: number) => Number.isFinite(value))
  if (!values.length) return null
  return values.reduce((sum: number, value: number) => sum + value, 0) / values.length
})

const workbenchMetrics = computed(() => [
  {
    label: '跨平台归并',
    value: formatInteger(resolutionReport.value?.cross_platform_merge_count),
    hint: `同名不自动合并：${formatInteger(resolutionReport.value?.blocked_same_name_merge_count)}`,
  },
  {
    label: '候选群组',
    value: formatInteger(communityRows.value.length),
    hint: `${formatInteger(resultSnapshot.value?.network?.total_nodes)} 个账号节点`,
  },
  {
    label: '高风险群组',
    value: formatInteger(highRiskClusterCount.value),
    hint: detectionUnavailable.value ? '未生成检测结果' : '来自已激活的检测模型产物',
  },
  {
    label: '证据覆盖',
    value: formatPercent(averageEvidenceCoverage.value),
    hint: `${formatInteger(resolutionReport.value?.canonical_url_count)} 个网址 / ${formatInteger(resolutionReport.value?.canonical_claim_count)} 条主张`,
  },
])

const activeCommunityRecord = computed(() => {
  const detailId = communityDetail.value?.cluster_id ?? selectedNode.value?.cluster_id
  if (detailId !== null && detailId !== undefined) {
    const matched = communityRows.value.find((community: any) => String(community?.cluster_id) === String(detailId))
    if (matched) {
      return {
        ...matched,
        ...(communityDetail.value || {}),
        detection_verdict: detectionVerdictForCluster(detailId),
      }
    }
    return {
      ...(communityDetail.value || {}),
      cluster_id: detailId,
      detection_verdict: detectionVerdictForCluster(detailId),
    }
  }
  return communityRows.value[0] || null
})

const activeCharacterizationClusterId = computed(() => activeCommunityRecord.value?.cluster_id ?? null)

const characterizationDimensions = computed(() => {
  const record = activeCommunityRecord.value || {}
  return [
    authenticitySummary(record),
    harmfulnessSummary(record),
    orchestrationSummary(record),
    timeVarianceSummary(record),
  ]
})

const communityColumns = [
  { title: '社区 ID', dataIndex: 'cluster_id', key: 'cluster_id', width: 90 },
  { title: '规模', dataIndex: 'size', key: 'size', width: 80 },
  { title: '社区分数', dataIndex: 'community_score', key: 'community_score', width: 110, customRender: ({ text }: any) => formatMetric(text) },
  { title: '协同攻击检测', dataIndex: 'detection_verdict', key: 'detection', width: 150 },
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
  { title: '证据分数', dataIndex: 'node_score', key: 'node_score', width: 120, customRender: ({ text }: any) => formatMetric(text) },
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
  { title: '证据分数', dataIndex: 'node_score', key: 'node_score', width: 110, customRender: ({ text }: any) => formatMetric(text) },
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

function detectionVerdictForCluster(clusterId: any) {
  const normalizedId = clusterId === null || clusterId === undefined ? '' : String(clusterId).trim()
  if (!normalizedId) return null
  return (
    detectionVerdictMap.value.get(normalizedId) ||
    detectionVerdictMap.value.get(`resolved-${normalizedId}`) ||
    (normalizedId.startsWith('resolved-') ? detectionVerdictMap.value.get(normalizedId.slice('resolved-'.length)) : null) ||
    null
  )
}

function candidateClusterFor(clusterId: any) {
  const normalizedId = clusterId === null || clusterId === undefined ? '' : String(clusterId).trim()
  if (!normalizedId) return null
  const clusters = Array.isArray(coordinationDiscovery.value?.candidate_clusters)
    ? coordinationDiscovery.value.candidate_clusters
    : []
  return clusters.find((cluster: any) => {
    const candidateId = String(cluster?.cluster_id || '').trim()
    return candidateId === normalizedId || candidateId === `resolved-${normalizedId}` || `resolved-${candidateId}` === normalizedId
  }) || null
}

function isHighRiskVerdict(verdict: any) {
  if (!verdict) return false
  const decision = String(verdict.decision || '').toLowerCase()
  const probability = Number(verdict.harmful_probability)
  return ['harmful', 'malicious', 'cib', 'coordinated_attack', 'harmful_coordination'].includes(decision) || (Number.isFinite(probability) && probability >= 0.5)
}

function detectionDecisionLabel(verdict: any) {
  if (detectionUnavailable.value) return '暂不可用'
  if (!verdict) return '待检测'
  const decision = String(verdict.decision || '').toLowerCase()
  if (['harmful', 'malicious', 'cib', 'coordinated_attack', 'harmful_coordination'].includes(decision)) return '高风险提示'
  if (['benign', 'legitimate', 'non_harmful', 'benign_coordination'].includes(decision)) return '暂未提示危害'
  return verdict.decision || '证据不足'
}

function detectionTagColor(verdict: any) {
  if (detectionUnavailable.value) return 'default'
  if (!verdict) return 'default'
  if (isHighRiskVerdict(verdict)) return 'volcano'
  return 'green'
}

function authenticitySummary(record: any) {
  const members = activeMembersFor(record)
  const suspicious = members.filter((member: any) => {
    const label = String(member?.botrhg_prediction ?? '').toLowerCase()
    const score = Number(member?.botrhg_probability ?? member?.final_bot_probability)
    return label.includes('bot') || label.includes('suspicious') || (Number.isFinite(score) && score >= 0.75)
  })
  if (!members.length) {
    return {
      key: 'authenticity',
      label: '真实性',
      value: '待展开',
      summary: '账户画像页已承载社交机器人检测；打开群组后汇总成员真实性。',
      evidence: '可从成员表跳转账号画像，复核 Bot 概率、活跃节律和相似账号。',
    }
  }
  return {
    key: 'authenticity',
    label: '真实性',
    value: formatPercent(suspicious.length / Math.max(members.length, 1)),
    summary: `${suspicious.length}/${members.length} 个成员带有机器人或可疑账号信号。`,
    evidence: '来源：账户画像页社交机器人检测与群组成员列表。',
  }
}

function harmfulnessSummary(record: any) {
  const verdict = detectionVerdictForCluster(record?.cluster_id)
  const probability = Number(verdict?.harmful_probability)
  if (detectionUnavailable.value) {
    return {
      key: 'harmfulness',
      label: '危害性',
      value: '暂不可用',
      summary: '当前结果没有可用的检测提示，不能把协同群组直接定性为有害。',
      evidence: '语义辅助分析仍可作为主张、立场、情绪和内容样例来源。',
    }
  }
  return {
    key: 'harmfulness',
    label: '危害性',
    value: Number.isFinite(probability) ? formatPercent(probability) : '待检测',
    summary: verdict ? `模型给出 ${detectionDecisionLabel(verdict)}，需结合内容证据复核。` : '当前群组未出现在检测输出中。',
    evidence: '来源：预计算成员概率聚合、群组特征与语义辅助分析。',
  }
}

function orchestrationSummary(record: any) {
  const candidate = candidateClusterFor(record?.cluster_id)
  const metrics = candidate?.coordination_metrics || {}
  const relationCount = relationTypeCount(record, candidate)
  const density = firstFinite(record?.density, metrics?.tsgs_spectral_density)
  const objectConcentration = firstFinite(record?.object_concentration, metrics?.mhcr_hyperedge_coherence)
  return {
    key: 'orchestration',
    label: '组织性',
    value: formatMetric(firstFinite(record?.community_score, metrics?.overall_coordination_score)),
    summary: `密度 ${formatMetric(density)}，对象集中度 ${formatMetric(objectConcentration)}，关系类型 ${relationCount} 类。`,
    evidence: '来源：共享网址/话题/主张/文本相似/原生关系形成的账号-对象证据网络。',
  }
}

function timeVarianceSummary(record: any) {
  const candidate = candidateClusterFor(record?.cluster_id)
  const windows = Array.isArray(candidate?.window_ids) ? candidate.window_ids : []
  const delta = Number(candidate?.coordination_metrics?.temporal_sync_delta_seconds)
  if (windows.length) {
    return {
      key: 'timeVariance',
      label: '时间变化',
      value: `${windows.length} 窗`,
      summary: `该群组出现在 ${windows.length} 个观测窗口，平均同步间隔 ${formatSeconds(delta)}。`,
      evidence: '来源：1h/6h/24h 窗口谱系和动态社区结果。',
    }
  }
  return {
    key: 'timeVariance',
    label: '时间变化',
    value: '待同步',
    summary: '当前历史结果没有窗口级 lineage；可在传播监测页核验时间线、爆发点和持续性。',
    evidence: '来源待补：窗口级动态图、成员进入/退出和同步峰值。',
  }
}

function activeMembersFor(record: any) {
  const recordId = String(record?.cluster_id ?? '')
  const detailId = String(communityDetail.value?.cluster_id ?? '')
  if (recordId && detailId && recordId === detailId && Array.isArray(communityDetail.value?.members)) {
    return communityDetail.value.members
  }
  return []
}

function relationTypeCount(record: any, candidate: any) {
  const relationBreakdown = record?.relation_breakdown
  if (relationBreakdown && typeof relationBreakdown === 'object') {
    return Object.keys(relationBreakdown).length
  }
  if (Array.isArray(candidate?.relation_types)) {
    return candidate.relation_types.length
  }
  return 0
}

function firstFinite(...values: any[]) {
  for (const value of values) {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) return numeric
  }
  return null
}

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
  datasetDetail.value = null
  resultSnapshot.value = null
  graphPayload.value = null
  datasetDetailError.value = null
  latestResultError.value = null
  graphError.value = null
  communityDrawerOpen.value = false
  selectedNode.value = null
  communityDetail.value = null
  await Promise.all([loadDatasetDetail(datasetId), loadLatestResult(datasetId), loadGraph()])
}

async function loadDatasetDetail(datasetId: number) {
  const requestGeneration = ++datasetDetailRequestGeneration
  loadingDetail.value = true
  datasetDetailError.value = null
  try {
    const resp = await getCoordinationDatasetDetail(datasetId)
    if (requestGeneration !== datasetDetailRequestGeneration || datasetId !== selectedDatasetId.value) return
    datasetDetail.value = resp.data
  } catch (error) {
    if (requestGeneration !== datasetDetailRequestGeneration || datasetId !== selectedDatasetId.value) return
    datasetDetail.value = null
    datasetDetailError.value = resourceErrorMessage(error, '数据集详情加载失败')
  } finally {
    if (requestGeneration === datasetDetailRequestGeneration) {
      loadingDetail.value = false
    }
  }
}

async function loadLatestResult(datasetId: number) {
  const requestGeneration = ++latestResultRequestGeneration
  loadingResult.value = true
  latestResultError.value = null
  try {
    const resp = await getCoordinationDatasetLatestResult(datasetId)
    if (requestGeneration !== latestResultRequestGeneration || datasetId !== selectedDatasetId.value) return
    resultSnapshot.value = resp.data
  } catch (error) {
    if (requestGeneration !== latestResultRequestGeneration || datasetId !== selectedDatasetId.value) return
    resultSnapshot.value = null
    latestResultError.value = resourceErrorMessage(error, '历史结果加载失败')
  } finally {
    if (requestGeneration === latestResultRequestGeneration) {
      loadingResult.value = false
    }
  }
}

async function loadGraph() {
  if (!pageActive.value || !selectedDatasetId.value) return
  const datasetId = selectedDatasetId.value
  const requestGeneration = ++graphRequestGeneration
  loadingGraph.value = true
  graphError.value = null
  try {
    const resp = await getCoordinationGraph(datasetId, {
      node_limit: nodeLimit.value,
      min_node_score: minNodeScore.value,
    })
    if (!pageActive.value || requestGeneration !== graphRequestGeneration || datasetId !== selectedDatasetId.value) return
    graphPayload.value = resp.data
  } catch (error) {
    if (!pageActive.value || requestGeneration !== graphRequestGeneration || datasetId !== selectedDatasetId.value) return
    graphPayload.value = null
    graphError.value = resourceErrorMessage(error, '协同网络加载失败')
  } finally {
    if (requestGeneration === graphRequestGeneration) {
      loadingGraph.value = false
    }
  }
}

function retryDatasetDetail() {
  if (selectedDatasetId.value) void loadDatasetDetail(selectedDatasetId.value)
}

function retryLatestResult() {
  if (selectedDatasetId.value) void loadLatestResult(selectedDatasetId.value)
}

function retryGraph() {
  void loadGraph()
}

function resourceErrorMessage(error: unknown, fallback: string) {
  if (error && typeof error === 'object') {
    const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return `${fallback}：${detail}`
  }
  if (error instanceof Error && error.message) return `${fallback}：${error.message}`
  return fallback
}

function scheduleGraphReload() {
  if (!pageActive.value) return
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
  drawerMode.value = 'community'
  communityDrawerOpen.value = true
  loadingCommunity.value = true
  try {
    const resp = await getCoordinationCommunityDetail(selectedDatasetId.value, clusterId)
    communityDetail.value = resp.data
    if (!options.preserveSelectedNode) {
      selectedNode.value = null
    }
  } finally {
    loadingCommunity.value = false
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
  running.value = true
  try {
    const resp = await createCoordinationRun(selectedDatasetId.value)
    const runId = resp.data?.run_id
    if (!runId) {
      throw new Error('未返回运行任务 ID')
    }
    pollingRunId.value = runId
    message.success(`已提交归档复现任务 #${runId}`)
    await loadDatasetDetail(selectedDatasetId.value)
    startPolling(runId)
  } catch (error: any) {
    running.value = false
    throw error
  }
}

function startPolling(runId: number) {
  stopPolling()
  const loop = async () => {
    if (!pageActive.value) return
    try {
      const resp = await getCoordinationRun(runId)
      if (!pageActive.value) return
      const run = resp.data
      if (datasetDetail.value?.runs?.length) {
        datasetDetail.value.runs = [run, ...datasetDetail.value.runs.filter((item: any) => item.run_id !== run.run_id)].slice(0, 10)
      }
      if (run.status === 'completed') {
        stopPolling()
        running.value = false
        pollingRunId.value = null
        if (selectedDatasetId.value) {
          await Promise.all([loadDatasets(), loadDatasetDetail(selectedDatasetId.value), loadGraph()])
          await loadLatestResult(selectedDatasetId.value)
        }
        message.success('归档复现运行完成')
        return
      }
      if (run.status === 'failed') {
        stopPolling()
        running.value = false
        pollingRunId.value = null
        await loadDatasetDetail(selectedDatasetId.value as number)
        message.error(run.error || '归档复现运行失败')
        return
      }
    } catch {
      stopPolling()
      running.value = false
      return
    }
    pollTimer = window.setTimeout(loop, 3000)
  }
  loop()
}

async function initializeCoordinationPage() {
  if (initialDatasetLoad) return initialDatasetLoad
  if (selectedDatasetId.value && datasets.value.length) return

  const load = (async () => {
    await loadDatasets()
    if (selectedDatasetId.value) {
      await selectDataset(selectedDatasetId.value)
    }
  })()
  initialDatasetLoad = load
  try {
    await load
  } finally {
    if (initialDatasetLoad === load) {
      initialDatasetLoad = null
    }
  }
}

function activateCoordinationPage() {
  pageActive.value = true
  if (!selectedDatasetId.value || !datasets.value.length) {
    void initializeCoordinationPage()
    return
  }
  if (running.value && pollingRunId.value !== null) {
    startPolling(pollingRunId.value)
  }
}

function deactivateCoordinationPage() {
  pageActive.value = false
  datasetDetailRequestGeneration += 1
  latestResultRequestGeneration += 1
  graphRequestGeneration += 1
  stopPolling()
  if (graphReloadTimer !== null) {
    window.clearTimeout(graphReloadTimer)
    graphReloadTimer = null
  }
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

function formatInteger(value: any) {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.round(numeric).toLocaleString('zh-CN') : String(value)
}

function formatSeconds(value: any) {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return numeric >= 60 ? `${(numeric / 60).toFixed(1)} 分钟` : `${numeric.toFixed(1)} 秒`
}

function formatPercent(value: any) {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(2)}%` : String(value)
}

function formatRelationLabel(value: any) {
  const mapping: Record<string, string> = {
    url_share: '共享网址',
    hashtag_share: '共享话题',
    retweet_target: '同转推目标',
    reply_target: '同回复目标',
    quote_target: '同引用目标',
    mention_target: '同提及目标',
    fast_retweet: '快速转推',
    tweet_similarity: '文本相似',
    courl: '共链网址',
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
  deactivateCoordinationPage()
})

onMounted(() => {
  activateCoordinationPage()
})

onActivated(() => {
  activateCoordinationPage()
})

onDeactivated(() => {
  deactivateCoordinationPage()
})
</script>

<style scoped>
.coordination-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-variant-numeric: tabular-nums;
}

.coordination-page :deep(.ant-spin-container) > * + * {
  margin-top: 20px;
}

.panel {
  border-radius: 14px;
}

.workbench-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detection-status-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 12px 14px;
  border: 1px solid #cbd8e5;
  border-left: 3px solid #63809e;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
}

.detection-status-strip > div {
  min-width: 0;
}

.detection-status-strip strong {
  color: #1e293b;
  font-size: 14px;
}

.detection-status-strip p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.detection-status-strip > span {
  max-width: 300px;
  color: #52667c;
  font-size: 13px;
  line-height: 1.5;
}

.workbench-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.workbench-metrics .summary-item {
  min-height: 92px;
  border: 1px solid #d7e1eb;
  background: #fbfcfe;
}

.workbench-metrics .summary-item small {
  color: #64748b;
  line-height: 1.4;
}

.characterization-panel {
  min-width: 0;
  padding-top: 2px;
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.dimension-grid--drawer {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dimension-card {
  min-width: 0;
  border: 1px solid #d7e1eb;
  border-left: 3px solid #63809e;
  border-radius: 8px;
  background: #fbfcfe;
  box-shadow: none;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 148px;
}

.characterization-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.characterization-panel-head h2 {
  margin: 0;
  color: #1e293b;
  font-size: 16px;
  font-weight: 650;
  line-height: 1.5;
}

.dimension-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.dimension-card-head span {
  color: #475569;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.dimension-card-head strong {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.dimension-card p {
  margin: 0;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.6;
}

.dimension-card small {
  color: #64748b;
  line-height: 1.5;
}

.table-verdict {
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.network-summary {
  margin: 0 0 10px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
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

@media (max-width: 1400px) {
  .dimension-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .workbench-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

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

@media (max-width: 720px) {
  .workbench-metrics,
  .dimension-grid {
    grid-template-columns: 1fr;
  }

  .detection-status-strip {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .detection-status-strip > span {
    max-width: none;
  }
}
</style>
