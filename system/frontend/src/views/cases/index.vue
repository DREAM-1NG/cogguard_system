<template>
  <div class="case-page">
    <PageHeader title="案例闭环" description="围绕案例完成事件、证据、协同、传播、研判、处置和反馈闭环展示" />

    <div class="case-toolbar">
      <a-input
        v-model:value="eventId"
        class="event-input"
        allow-clear
        placeholder="trump_visit_2026_05_21"
        @pressEnter="loadCase"
      />
      <a-button type="primary" :loading="loading" @click="loadCase">刷新案例</a-button>
      <a-button @click="drawerOpen = true">证据下钻</a-button>
    </div>

    <a-alert
      v-if="errorText"
      class="case-alert"
      type="warning"
      show-icon
      :message="errorText"
    />

    <section v-if="caseDetail" class="case-context-bar">
      <div class="case-title-block">
        <div class="case-title-row">
          <h2>{{ caseDetail.title }}</h2>
          <a-tag :color="stateColor(caseDetail.state)">{{ caseDetail.state }}</a-tag>
          <a-tag>{{ caseDetail.event_id }}</a-tag>
        </div>
        <p>{{ caseDetail.workflow_summary.closed_loop || '事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈' }}</p>
      </div>
      <div class="case-claim-block">
        <span class="eyebrow">主核心主张</span>
        <strong>{{ caseDetail.primary_claim?.excerpt || '待审批' }}</strong>
        <small>
          {{ caseDetail.primary_claim?.source?.name || '-' }}
          · {{ caseDetail.primary_claim?.source?.tier || '-' }}
        </small>
      </div>
      <div class="case-blocker-block">
        <span class="eyebrow">阻塞项</span>
        <template v-if="caseDetail.active_blockers.length">
          <a-tag v-for="item in caseDetail.active_blockers" :key="item.blocker_id" color="orange">
            {{ item.code }}
          </a-tag>
        </template>
        <a-tag v-else color="green">无活动阻塞</a-tag>
      </div>
    </section>

    <a-card v-if="!caseDetail && loading" size="small" class="loading-card">
      <a-spin tip="正在加载案例闭环..." />
    </a-card>

    <template v-if="caseDetail">
      <div class="lifecycle-strip">
        <div
          v-for="step in caseDetail.lifecycle"
          :key="step.key"
          :class="['lifecycle-step', step.status]"
        >
          <span>{{ step.label }}</span>
        </div>
      </div>

      <a-tabs v-model:activeKey="activeTab" class="case-tabs">
        <a-tab-pane key="overview" tab="概览">
          <div class="overview-grid">
            <section class="panel">
              <div class="panel-title">事件证据</div>
              <a-descriptions size="small" :column="2" bordered>
                <a-descriptions-item label="Snapshot">{{ caseDetail.evidence.snapshot_id }}</a-descriptions-item>
                <a-descriptions-item label="Fingerprint">{{ compactHash(caseDetail.evidence.data_fingerprint) }}</a-descriptions-item>
                <a-descriptions-item label="帖子">{{ caseDetail.evidence.posts || 0 }}</a-descriptions-item>
                <a-descriptions-item label="评论">{{ caseDetail.evidence.comments || 0 }}</a-descriptions-item>
                <a-descriptions-item label="平台">{{ caseDetail.platforms.join(', ') || '-' }}</a-descriptions-item>
                <a-descriptions-item label="预期平台">{{ caseDetail.expected_platforms.join(', ') }}</a-descriptions-item>
              </a-descriptions>
            </section>
            <section class="panel">
              <div class="panel-title">分析运行</div>
              <a-table
                size="small"
                :columns="runColumns"
                :data-source="caseDetail.analysis_runs"
                row-key="run_id"
                :pagination="false"
              />
            </section>
          </div>
        </a-tab-pane>

        <a-tab-pane key="evidence" tab="证据矩阵">
          <div class="matrix-grid">
            <section class="panel">
              <div class="panel-title">权威主张</div>
              <a-table
                size="small"
                :columns="claimColumns"
                :data-source="claimRows"
                row-key="claim_id"
                :pagination="false"
              />
            </section>
            <section class="panel">
              <div class="panel-title">语义辅助</div>
              <a-space wrap class="semantic-tags">
                <a-tag color="blue">{{ semanticStatus }}</a-tag>
                <a-tag color="orange">candidate_unvalidated</a-tag>
                <a-tag>证据叠加，不改风险分</a-tag>
              </a-space>
              <div class="semantic-section">
                <h3>关键词</h3>
                <a-tag v-for="item in topKeywords" :key="item.term">{{ item.term }} {{ item.count }}</a-tag>
              </div>
              <div class="semantic-section">
                <h3>主题</h3>
                <div v-for="item in topicItems" :key="item.topic_id" class="topic-row">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.size }} 条 · {{ (item.keywords || []).join(', ') }}</span>
                </div>
              </div>
              <div class="semantic-section">
                <h3>实体</h3>
                <a-tag v-for="item in entityItems" :key="item.entity">{{ item.entity }}</a-tag>
              </div>
            </section>
          </div>
        </a-tab-pane>

        <a-tab-pane key="graph" tab="图谱">
          <section class="panel graph-panel">
            <div class="panel-title">协调与传播证据图谱</div>
            <div class="graph-summary">
              <a-statistic title="节点" :value="graphNodes.length" />
              <a-statistic title="边" :value="graphEdges.length" />
              <a-statistic title="来源" :value="caseDetail.graph.provenance || '-'" />
            </div>
            <div class="node-list">
              <a-tag v-for="node in graphNodes" :key="node.id">{{ node.label || node.id }}</a-tag>
            </div>
          </section>
        </a-tab-pane>

        <a-tab-pane key="actions" tab="处置">
          <section class="panel">
            <div class="panel-title">处置与反馈</div>
            <a-table
              size="small"
              :columns="actionColumns"
              :data-source="caseDetail.actions"
              row-key="action_id"
              :pagination="false"
            />
            <a-textarea class="feedback-box" :rows="3" placeholder="记录人工反馈或结案复核说明" />
          </section>
        </a-tab-pane>

        <a-tab-pane key="reports" tab="报告">
          <section class="panel reports-panel">
            <div class="panel-title">冻结报告版本</div>
            <a-table
              size="small"
              :columns="reportColumns"
              :data-source="caseDetail.reports"
              row-key="version"
              :pagination="false"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'actions'">
                  <a-space>
                    <a-button size="small" :disabled="!record.html_url" @click="openReport(record.html_url)">预览</a-button>
                    <a-button size="small" :disabled="!record.pdf_url" @click="openReport(record.pdf_url)">PDF</a-button>
                  </a-space>
                </template>
                <template v-else-if="column.key === 'hash'">
                  {{ compactHash(record.content_hash) }}
                </template>
              </template>
            </a-table>
          </section>
        </a-tab-pane>
      </a-tabs>

      <a-drawer v-model:open="drawerOpen" title="EvidenceDrawer" width="560">
        <a-list :data-source="caseDetail.evidence.recent_posts || []" size="small">
          <template #renderItem="{ item }">
            <a-list-item>
              <div class="drawer-post">
                <div>
                  <a-tag>{{ item.platform }}</a-tag>
                  <strong>{{ item.author_name || '-' }}</strong>
                  <span>{{ formatTime(item.timestamp) }}</span>
                </div>
                <p>{{ item.content }}</p>
              </div>
            </a-list-item>
          </template>
        </a-list>
      </a-drawer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import { getCase, listCases } from '@/api/cases'
import type { CaseClaim, CaseDetail } from '@/types/case'

const DEFAULT_EVENT_ID = 'trump_visit_2026_05_21'

const eventId = ref(DEFAULT_EVENT_ID)
const caseDetail = ref<CaseDetail | null>(null)
const activeTab = ref('overview')
const loading = ref(false)
const errorText = ref('')
const drawerOpen = ref(false)

const claimRows = computed<CaseClaim[]>(() => {
  if (!caseDetail.value) return []
  return [
    ...(caseDetail.value.primary_claim ? [caseDetail.value.primary_claim] : []),
    ...caseDetail.value.supplementary_claims,
  ]
})
const semanticArtifact = computed(() => caseDetail.value?.semantic_artifacts?.[0] || null)
const semanticStatus = computed(() => semanticArtifact.value?.status || 'not_run')
const topKeywords = computed<any[]>(() => semanticArtifact.value?.summary?.top_keywords || [])
const topicItems = computed<any[]>(() => semanticArtifact.value?.summary?.topics?.items || [])
const entityItems = computed<any[]>(() => semanticArtifact.value?.summary?.entities || [])
const graphNodes = computed<any[]>(() => caseDetail.value?.graph?.nodes || [])
const graphEdges = computed<any[]>(() => caseDetail.value?.graph?.edges || [])

const runColumns = [
  { title: 'Run', dataIndex: 'run_id', key: 'run_id' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '阶段', dataIndex: 'requested_stages', key: 'requested_stages', customRender: ({ text }: { text: string[] }) => text?.join(', ') || '-' },
]

const claimColumns = [
  { title: '角色', dataIndex: 'role', key: 'role' },
  { title: '来源', key: 'source', customRender: ({ record }: { record: CaseClaim }) => `${record.source?.name || '-'} · ${record.source?.tier || '-'}` },
  { title: '原句', dataIndex: 'excerpt', key: 'excerpt' },
  { title: 'Hash', dataIndex: 'excerpt_hash', key: 'excerpt_hash', customRender: ({ text }: { text: string }) => compactHash(text) },
]

const actionColumns = [
  { title: '处置项', dataIndex: 'title', key: 'title' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '负责人', dataIndex: 'assignee', key: 'assignee' },
]

const reportColumns = [
  { title: '版本', dataIndex: 'version', key: 'version' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '内容 Hash', key: 'hash' },
  { title: '操作', key: 'actions' },
]

async function loadCase() {
  loading.value = true
  errorText.value = ''
  try {
    const list = await listCases({ event_id: eventId.value.trim() || DEFAULT_EVENT_ID })
    const first = list.data.items?.[0]
    if (!first) {
      caseDetail.value = null
      errorText.value = '未找到匹配案例'
      return
    }
    const targetId = first.case_id
    const detail = await getCase(targetId)
    caseDetail.value = detail.data
  } catch (error: any) {
    errorText.value = error?.message || '案例加载失败'
    message.warning(errorText.value)
  } finally {
    loading.value = false
  }
}

function stateColor(state?: string) {
  return ({
    draft: 'default',
    collecting: 'processing',
    evidence_ready: 'blue',
    analyzing: 'purple',
    awaiting_review: 'orange',
    actioning: 'gold',
    ready_to_close: 'cyan',
    closed: 'green',
  } as Record<string, string>)[state || ''] || 'default'
}

function compactHash(value?: string | null) {
  if (!value) return '-'
  return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function openReport(url?: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  void loadCase()
})
</script>

<style scoped lang="less">
.case-page {
  min-height: 100%;
}

.case-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.event-input {
  width: min(420px, 100%);
}

.case-alert,
.loading-card {
  margin-bottom: 16px;
}

.case-context-bar {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 1fr) minmax(180px, 0.5fr);
  gap: 16px;
  align-items: stretch;
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fbff;
}

.case-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;

  h2 {
    margin: 0;
    font-size: 18px;
  }
}

.case-title-block p {
  margin: 8px 0 0;
  color: #475569;
}

.case-claim-block,
.case-blocker-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.case-claim-block strong {
  color: #111827;
  line-height: 1.5;
}

.case-claim-block small,
.eyebrow {
  color: #64748b;
}

.eyebrow {
  font-size: 12px;
}

.lifecycle-strip {
  display: grid;
  grid-template-columns: repeat(7, minmax(100px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
  overflow-x: auto;
}

.lifecycle-step {
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #64748b;
  white-space: nowrap;
}

.lifecycle-step.done {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}

.lifecycle-step.active {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #c2410c;
  font-weight: 700;
}

.case-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 14px;
}

.overview-grid,
.matrix-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fff;
}

.panel-title {
  margin-bottom: 12px;
  color: #111827;
  font-weight: 700;
}

.semantic-tags,
.semantic-section {
  margin-bottom: 12px;
}

.semantic-section h3 {
  margin: 0 0 8px;
  color: #334155;
  font-size: 13px;
}

.topic-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}

.topic-row span {
  color: #64748b;
}

.graph-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.node-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.feedback-box {
  margin-top: 12px;
}

.drawer-post div {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: #64748b;
}

.drawer-post p {
  margin: 8px 0 0;
  color: #1f2329;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .case-context-bar,
  .overview-grid,
  .matrix-grid,
  .graph-summary {
    grid-template-columns: 1fr;
  }
}

@media print {
  .case-toolbar,
  :deep(.ant-tabs-nav),
  :deep(.ant-drawer) {
    display: none !important;
  }

  .case-context-bar,
  .panel {
    box-shadow: none;
    break-inside: avoid;
  }
}
</style>
