<template>
  <div class="analysis-page">
    <PageHeader
      title="Unified Analysis"
      description="Run Coordination Discover, Propagation Analysis, semantic enrichment, Student review, and asynchronous Teacher review from one EventSnapshot."
    />

    <a-alert
      type="info"
      show-icon
      class="analysis-alert"
      message="V2 analysis runtime"
      description="This workbench uses /api/v2/analysis, EventSnapshot, AnalysisRun events, REST recovery, and SSE backlog through Last-Event-ID compatible cursors."
    />

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="8">
        <a-card title="1. EventSnapshot" size="small" class="analysis-card">
          <a-form layout="vertical" :model="snapshotForm">
            <a-form-item label="Event ID">
              <a-input v-model:value="snapshotForm.event_id" placeholder="trump_visit_2026_05_21" />
            </a-form-item>
            <a-form-item label="Platform filter">
              <a-select v-model:value="snapshotForm.platform" allow-clear placeholder="All platforms">
                <a-select-option value="weibo">weibo</a-select-option>
                <a-select-option value="douyin">douyin</a-select-option>
                <a-select-option value="xhs">xhs</a-select-option>
                <a-select-option value="news">news</a-select-option>
              </a-select>
            </a-form-item>
            <div class="form-grid">
              <a-form-item label="Core start">
                <a-input v-model:value="snapshotForm.core_window.start" />
              </a-form-item>
              <a-form-item label="Core end">
                <a-input v-model:value="snapshotForm.core_window.end" />
              </a-form-item>
              <a-form-item label="Context start">
                <a-input v-model:value="snapshotForm.context_window.start" />
              </a-form-item>
              <a-form-item label="Context end">
                <a-input v-model:value="snapshotForm.context_window.end" />
              </a-form-item>
            </div>
            <a-button type="primary" block :loading="snapshotLoading" @click="handleCreateSnapshot">
              Create snapshot
            </a-button>
          </a-form>

          <a-divider />
          <a-descriptions v-if="snapshot" size="small" :column="1" bordered>
            <a-descriptions-item label="snapshot_id">{{ snapshot.snapshot_id }}</a-descriptions-item>
            <a-descriptions-item label="platforms">{{ (snapshot.platforms || []).join(', ') || '-' }}</a-descriptions-item>
            <a-descriptions-item label="quality">{{ snapshot.quality_report?.status || '-' }}</a-descriptions-item>
            <a-descriptions-item label="fingerprint">{{ snapshot.data_fingerprint || '-' }}</a-descriptions-item>
          </a-descriptions>
          <a-empty v-else description="No snapshot yet" :image-style="{ height: '44px' }" />
        </a-card>

        <a-card title="2. AnalysisRun" size="small" class="analysis-card">
          <a-form layout="vertical" :model="runForm">
            <a-form-item label="Event ID">
              <a-input v-model:value="runForm.event_id" />
            </a-form-item>
            <a-form-item label="Snapshot ID">
              <a-input v-model:value="runForm.snapshot_id" />
            </a-form-item>
            <a-form-item label="Stages">
              <a-checkbox-group v-model:value="runForm.requested_stages" :options="stageOptions" />
            </a-form-item>
            <a-form-item label="Options JSON">
              <a-textarea v-model:value="runForm.options_json" :rows="9" />
            </a-form-item>
            <a-space direction="vertical" class="full-width">
              <a-button type="primary" block :loading="runLoading" @click="handleCreateRun">Create run</a-button>
              <a-button block :disabled="!currentRunId" :loading="executeLoading" @click="handleExecuteRun">
                Execute run
              </a-button>
              <a-button block :disabled="!currentRunId" @click="handleLoadRun">Refresh status</a-button>
            </a-space>
          </a-form>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="16">
        <a-card title="Run status" size="small" class="analysis-card">
          <a-descriptions v-if="runDetail" size="small" :column="2" bordered>
            <a-descriptions-item label="run_id">{{ runDetail.run_id }}</a-descriptions-item>
            <a-descriptions-item label="status">
              <a-tag :color="statusColor(runDetail.status)">{{ runDetail.status }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="snapshot_id">{{ runDetail.snapshot_id }}</a-descriptions-item>
            <a-descriptions-item label="stages">{{ (runDetail.requested_stages || []).join(', ') }}</a-descriptions-item>
          </a-descriptions>
          <a-empty v-else description="No run yet" :image-style="{ height: '44px' }" />
        </a-card>

        <div class="result-grid">
          <a-card title="Semantic enrichment" size="small" class="result-card semantic-card">
            <template v-if="semantic">
              <template v-if="semanticReady">
                <a-space wrap>
                  <a-tag color="green">{{ semantic.runtime_backend }}</a-tag>
                  <a-tag>{{ semantic.validation_status }}</a-tag>
                </a-space>
                <a-descriptions size="small" :column="1" bordered style="margin-top: 10px">
                  <a-descriptions-item label="Embeddings">{{ semantic.embedding_manifest?.count || 0 }}</a-descriptions-item>
                  <a-descriptions-item label="Model cache">{{ semantic.cache_dir }}</a-descriptions-item>
                </a-descriptions>
                <div class="semantic-summary-grid">
                  <section class="semantic-summary-panel">
                    <h4>Top keywords</h4>
                    <a-space v-if="semanticSummary.keywords.length" wrap>
                      <a-tag v-for="item in semanticSummary.keywords" :key="item.label" color="blue">
                        {{ item.label }} {{ item.count }}
                      </a-tag>
                    </a-space>
                    <span v-else class="semantic-empty">No keyword result</span>
                  </section>
                  <section class="semantic-summary-panel">
                    <h4>Topics</h4>
                    <a-space v-if="semanticSummary.topics.length" wrap>
                      <a-tag v-for="item in semanticSummary.topics" :key="item.label" color="purple">
                        {{ item.label }} {{ item.count }}
                      </a-tag>
                    </a-space>
                    <span v-else class="semantic-empty">No topic result</span>
                  </section>
                  <section class="semantic-summary-panel">
                    <h4>Sentiment</h4>
                    <div v-if="semanticSummary.sentiment.length" class="distribution-list">
                      <span v-for="item in semanticSummary.sentiment" :key="item.label" class="distribution-item">
                        <a-tag :color="sentimentColor(item.label)">{{ item.label }}</a-tag>
                        <strong>{{ item.count }}</strong>
                      </span>
                    </div>
                    <span v-else class="semantic-empty">No sentiment result</span>
                  </section>
                  <section class="semantic-summary-panel">
                    <h4>Stance</h4>
                    <div v-if="semanticSummary.stance.length" class="distribution-list">
                      <span v-for="item in semanticSummary.stance" :key="item.label" class="distribution-item">
                        <a-tag :color="stanceColor(item.label)">{{ item.label }}</a-tag>
                        <strong>{{ item.count }}</strong>
                      </span>
                    </div>
                    <span v-else class="semantic-empty">No stance result</span>
                  </section>
                  <section class="semantic-summary-panel">
                    <h4>Named entities</h4>
                    <a-space v-if="semanticSummary.entities.length" wrap>
                      <a-tag v-for="item in semanticSummary.entities" :key="item.label" color="cyan">
                        {{ item.label }} {{ item.count }}
                      </a-tag>
                    </a-space>
                    <span v-else class="semantic-empty">No entity result</span>
                  </section>
                </div>
              </template>
              <template v-else>
                <a-alert
                  type="error"
                  show-icon
                  :message="semantic.blocking_reason || 'Semantic models are not ready'"
                />
                <a-descriptions size="small" :column="1" bordered style="margin-top: 10px">
                  <a-descriptions-item label="Blocker">{{ semantic.blocking_reason || 'Model runtime is blocked' }}</a-descriptions-item>
                  <a-descriptions-item label="Weights cache">{{ semanticCacheDirectory }}</a-descriptions-item>
                </a-descriptions>
              </template>
            </template>
            <a-empty v-else description="Run semantic enrichment to view keywords, topics, sentiment, stance, and entities" :image-style="{ height: '36px' }" />
          </a-card>
          <a-card title="Coordination Discover communities" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(coordinationDiscover?.status)">{{ coordinationDiscover?.status || 'not run' }}</a-tag>
              <a-tag>{{ coordinationDiscover?.model_version || '-' }}</a-tag>
            </a-space>
            <a-statistic title="Evidence edges" :value="numberValue(coordinationDiscover?.summary?.evidence_edge_count)" />
            <a-statistic title="Lineages" :value="numberValue(coordinationDiscover?.summary?.lineage_count)" />
            <div class="mini-list">
              <div v-for="item in communityRows" :key="item.lineage_id" class="mini-row">
                <strong>{{ item.lineage_id }}</strong>
                <span>{{ item.support_count }} windows, stability {{ item.stability_score }}</span>
              </div>
            </div>
          </a-card>

          <a-card title="Propagation Analysis hindcast" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(propagationAnalysis?.status)">{{ propagationAnalysis?.status || 'not run' }}</a-tag>
              <a-tag>{{ propagationAnalysis?.model_version || propagationAnalysis?.model || '-' }}</a-tag>
            </a-space>
            <a-statistic title="Active accounts forecast" :value="numberValue(propagationAnalysis?.scale_forecast?.point)" />
            <div class="intervals">
              <span>80% {{ intervalText(propagationAnalysis?.conformal_intervals?.['80']) }}</span>
              <span>95% {{ intervalText(propagationAnalysis?.conformal_intervals?.['95']) }}</span>
            </div>
            <div class="mini-list">
              <div v-for="item in nextHopRows" :key="item.author_id" class="mini-row">
                <strong>#{{ item.rank }} {{ item.author_id }}</strong>
                <span>score {{ item.score }}</span>
              </div>
            </div>
          </a-card>

          <a-card title="Student Review" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(student?.status)">{{ student?.status || 'not run' }}</a-tag>
              <a-tag>{{ student?.model_status || '-' }}</a-tag>
              <a-tag>{{ student?.verdict_type || '-' }}</a-tag>
            </a-space>
            <a-statistic title="Score" :value="numberValue(student?.score)" :precision="3" />
            <p class="result-text">Label: {{ student?.label || '-' }}</p>
            <p class="result-text">Active learning: {{ activeLearningReasons }}</p>
          </a-card>

          <a-card title="Teacher Review" size="small" class="result-card">
            <a-space wrap>
              <a-tag :color="statusColor(teacher?.status)">{{ teacher?.status || 'not run' }}</a-tag>
              <a-tag>{{ teacher?.verdict_type || '-' }}</a-tag>
            </a-space>
            <p class="result-text">Decision: {{ teacher?.advisory?.decision || '-' }}</p>
            <p class="result-text">Canonical allowed: {{ teacher?.canonical_allowed === false ? 'no' : '-' }}</p>
            <div class="dag-strip">
              <a-tag v-for="node in teacherNodes" :key="node.node" :color="node.status === 'completed' || node.status === 'ok' ? 'green' : 'default'">
                {{ node.node }}
              </a-tag>
            </div>
          </a-card>
        </div>

        <template v-if="semanticReady">
          <a-card title="Main-post / comment semantic matrix" size="small" class="analysis-card">
            <div class="semantic-matrix-toolbar">
              <a-segmented v-model:value="semanticLayer" :options="semanticLayerOptions" />
              <a-select
                v-model:value="semanticPlatformFilter"
                class="semantic-platform-filter"
                allow-clear
                placeholder="All platforms"
                :options="semanticPlatformOptions"
              />
              <a-input v-model:value="semanticQuery" class="semantic-query" allow-clear placeholder="Filter text, keyword, topic, or entity" />
            </div>
            <a-table
              :columns="semanticMatrixColumns"
              :data-source="semanticMatrixRows"
              :pagination="semanticMatrixPagination"
              :scroll="{ x: 1250 }"
              row-key="id"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'source'">
                  <a-tag>{{ record.platform || '-' }}</a-tag>
                  <span class="matrix-id">{{ record.id }}</span>
                </template>
                <template v-else-if="column.key === 'timestamp'">
                  {{ formatTimestamp(record.timestamp) }}
                </template>
                <template v-else-if="column.key === 'text'">
                  <span class="semantic-text">{{ record.text || '-' }}</span>
                </template>
                <template v-else-if="column.key === 'sentiment'">
                  <a-tag :color="sentimentColor(semanticValueLabel(record.sentiment))">
                    {{ semanticValueLabel(record.sentiment) }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'stance'">
                  <a-tag :color="stanceColor(semanticValueLabel(record.stance))">
                    {{ semanticValueLabel(record.stance) }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'topics'">
                  <a-tag v-for="(item, index) in semanticEntries(record.topics).slice(0, 3)" :key="`${record.id}-topic-${index}`" color="purple">
                    {{ semanticEntryLabel(item, 'label') }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'keywords'">
                  <a-tag v-for="(item, index) in semanticEntries(record.keywords).slice(0, 3)" :key="`${record.id}-keyword-${index}`" color="blue">
                    {{ semanticEntryLabel(item, 'term') }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'entities'">
                  <a-tag v-for="(item, index) in semanticEntries(record.entities).slice(0, 3)" :key="`${record.id}-entity-${index}`" color="cyan">
                    {{ semanticEntryLabel(item, 'text') }}
                  </a-tag>
                </template>
              </template>
            </a-table>
          </a-card>

          <section class="semantic-cross-analysis" aria-label="Semantic cross analysis">
            <div class="semantic-section-heading">
              <div>
                <h3>Semantic cross analysis</h3>
                <p>Time, platform, coordination-community, and propagation-path evidence projections.</p>
              </div>
            </div>
            <div class="semantic-cross-grid">
              <section class="semantic-cross-panel">
                <h4>Time slices</h4>
                <a-list v-if="timeSliceRows.length" :data-source="timeSliceRows" size="small">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <span>{{ item.date || '-' }}</span>
                      <strong>{{ item.count || 0 }} records</strong>
                    </a-list-item>
                  </template>
                </a-list>
                <a-empty v-else description="No time slice" :image-style="{ height: '30px' }" />
              </section>
              <section class="semantic-cross-panel">
                <h4>Platform slices</h4>
                <a-list v-if="platformSliceRows.length" :data-source="platformSliceRows" size="small">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <div>
                        <strong>{{ item.platform || '-' }}</strong>
                        <span class="slice-detail">{{ formatCounter(item.sentiment) }}</span>
                      </div>
                      <strong>{{ item.count || 0 }}</strong>
                    </a-list-item>
                  </template>
                </a-list>
                <a-empty v-else description="No platform slice" :image-style="{ height: '30px' }" />
              </section>
              <section class="semantic-cross-panel">
                <h4>Coordination communities</h4>
                <a-list v-if="communitySliceRows.length" :data-source="communitySliceRows" size="small">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <div>
                        <strong>{{ item.community_id || '-' }}</strong>
                        <span class="slice-detail">{{ communitySummary(item) }}</span>
                      </div>
                      <strong>{{ item.item_count || 0 }}</strong>
                    </a-list-item>
                  </template>
                </a-list>
                <a-empty v-else :description="communitySlicesUnavailableReason || 'No coordination community available'" :image-style="{ height: '30px' }" />
              </section>
            </div>

            <section class="path-overlay-section">
              <div class="path-overlay-heading">
                <h4>Propagation path semantic overlays</h4>
                <span>{{ propagationPathOverlays.length }} paths</span>
              </div>
              <div v-if="propagationPathOverlays.length" class="path-overlay-grid">
                <article v-for="path in propagationPathOverlays.slice(0, 12)" :key="path.path_id" class="path-overlay-card">
                  <div class="path-overlay-title">
                    <strong>{{ path.path_id }}</strong>
                    <a-tag>{{ path.source || 'propagation path' }}</a-tag>
                  </div>
                  <dl class="path-overlay-details">
                    <div>
                      <dt>Sentiment</dt>
                      <dd>{{ formatCounter(path.semantic_overlay?.sentiment) }}</dd>
                    </div>
                    <div>
                      <dt>Stance</dt>
                      <dd>{{ formatCounter(path.semantic_overlay?.stance) }}</dd>
                    </div>
                    <div>
                      <dt>Platforms</dt>
                      <dd>{{ semanticTextList(path.semantic_overlay?.platforms) }}</dd>
                    </div>
                    <div>
                      <dt>Time</dt>
                      <dd>{{ formatTimeRange(path.semantic_overlay?.time_range) }}</dd>
                    </div>
                  </dl>
                  <div v-if="path.semantic_overlay?.associated_claim" class="path-overlay-claim">
                    <span>Claim</span>
                    <strong>{{ path.semantic_overlay.associated_claim }}</strong>
                  </div>
                  <div class="path-overlay-tags">
                    <span>Topics</span>
                    <a-tag v-for="(item, index) in semanticEntries(path.semantic_overlay?.topics).slice(0, 4)" :key="`${path.path_id}-topic-${index}`" color="purple">
                      {{ semanticEntryLabel(item, 'label') }}
                    </a-tag>
                  </div>
                  <div class="path-overlay-tags">
                    <span>Keywords</span>
                    <a-tag v-for="(item, index) in semanticEntries(path.semantic_overlay?.keywords).slice(0, 4)" :key="`${path.path_id}-keyword-${index}`" color="blue">
                      {{ semanticEntryLabel(item, 'term') }}
                    </a-tag>
                  </div>
                  <div class="path-overlay-tags">
                    <span>Entities</span>
                    <a-tag v-for="(item, index) in semanticEntries(path.semantic_overlay?.entities).slice(0, 4)" :key="`${path.path_id}-entity-${index}`" color="cyan">
                      {{ semanticEntryLabel(item, 'text') }}
                    </a-tag>
                  </div>
                  <div class="path-overlay-evidence">
                    <span>Evidence</span>
                    <a-tag v-for="(reference, index) in semanticTextEntries(path.semantic_overlay?.evidence_refs).slice(0, 4)" :key="`${path.path_id}-ref-${index}`">
                      {{ reference }}
                    </a-tag>
                  </div>
                </article>
              </div>
              <a-empty v-else description="No propagation-path evidence overlay" :image-style="{ height: '34px' }" />
            </section>
          </section>
        </template>

        <a-card title="Run events and recovery" size="small" class="analysis-card">
          <a-space class="event-actions" wrap>
            <a-input v-model:value="currentRunId" class="run-input" placeholder="run_id" />
            <a-input-number v-model:value="afterId" :min="0" />
            <a-button :disabled="!currentRunId" :loading="eventsLoading" @click="handleLoadEvents">
              REST refresh
            </a-button>
            <a-button :disabled="!currentRunId || streamLoading" @click="handleReadStream">
              SSE backlog
            </a-button>
            <a-button :disabled="!streamAbort" danger @click="stopStream">Stop stream</a-button>
          </a-space>
          <a-list v-if="events.length" :data-source="events" size="small" class="event-list">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="event-item">
                  <div class="event-meta">
                    <a-tag>{{ item.id }}</a-tag>
                    <strong>{{ item.event_type }}</strong>
                    <a-tag :color="statusColor(item.status)">{{ item.status }}</a-tag>
                  </div>
                  <pre>{{ formatJson(item.payload) }}</pre>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="No run events" :image-style="{ height: '44px' }" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  analysisAuthHeaders,
  analysisStreamUrl,
  createAnalysisRun,
  createAnalysisSnapshot,
  executeAnalysisRun,
  getAnalysisRun,
  listAnalysisRunEvents,
  getAnalysisArtifact,
  type AnalysisRunEvent,
  type AnalysisStage,
} from '@/api/analysis'

const defaultEventId = 'trump_visit_2026_05_21'

const snapshotForm = ref({
  event_id: defaultEventId,
  platform: undefined as string | undefined,
  core_window: {
    start: '2026-05-11T00:00:00Z',
    end: '2026-05-22T00:00:00Z',
  },
  context_window: {
    start: '2026-05-01T00:00:00Z',
    end: '2026-05-31T00:00:00Z',
  },
})

const runForm = ref({
  event_id: defaultEventId,
  snapshot_id: '',
  requested_stages: ['coordination_discover', 'propagation_analysis', 'semantic_enrichment', 'student', 'teacher'] as AnalysisStage[],
  options_json: JSON.stringify({
    coordination_discover: { time_window: 3600, min_participation: 2, edge_weight: 0.5 },
    propagation_analysis: { top_k: 10 },
    semantic_enrichment: { claim: '特朗普访华相关叙事' },
    student: {},
    teacher: { teacher_max_review_items: 20 },
  }, null, 2),
})

const stageOptions = [
  { label: 'Coordination Discover', value: 'coordination_discover' },
  { label: 'Propagation Analysis', value: 'propagation_analysis' },
  { label: 'Semantic enrichment', value: 'semantic_enrichment' },
  { label: 'Student review', value: 'student' },
  { label: 'Teacher review', value: 'teacher' },
]

const snapshot = ref<any>(null)
const runDetail = ref<any>(null)
const events = ref<AnalysisRunEvent[]>([])
const currentRunId = ref('precomputed_trump_visit_2026_05_21_semantic_v5')
const afterId = ref(0)
const snapshotLoading = ref(false)
const runLoading = ref(false)
const executeLoading = ref(false)
const eventsLoading = ref(false)
const streamLoading = ref(false)
const streamAbort = ref<AbortController | null>(null)

const latestEventId = computed(() => events.value.reduce((max, item) => Math.max(max, Number(item.id) || 0), 0))
const runResults = computed<Record<string, any>>(() => {
  return runDetail.value?.results || runDetail.value?.result?.results || {}
})
const coordinationDiscover = computed(() => runResults.value.coordination_discover || null)
const propagationAnalysis = computed(() => runResults.value.propagation_analysis || null)
const student = computed(() => runResults.value.student || null)
const teacher = computed(() => runResults.value.teacher || null)
const semantic = ref<any>(null)
const semanticLayer = ref<'posts' | 'comments'>('posts')
const semanticPlatformFilter = ref<string | undefined>()
const semanticQuery = ref('')
const semanticLayerOptions = [
  { label: 'Main posts', value: 'posts' },
  { label: 'Comments', value: 'comments' },
]
const semanticMatrixColumns = [
  { title: 'Source', key: 'source', width: 150, fixed: 'left' },
  { title: 'Time', key: 'timestamp', width: 172 },
  { title: 'Text', key: 'text', width: 280 },
  { title: 'Sentiment', key: 'sentiment', width: 128 },
  { title: 'Stance', key: 'stance', width: 150 },
  { title: 'Topics', key: 'topics', width: 180 },
  { title: 'Keywords', key: 'keywords', width: 210 },
  { title: 'Entities', key: 'entities', width: 210 },
]
const semanticMatrixPagination = { pageSize: 20, showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] }
const semanticReady = computed(() => semantic.value?.runtime_status === 'ready')
const semanticCacheDirectory = computed(() => String(semantic.value?.cache_dir || 'G:\\CISCN\\hf_models'))
const allSemanticRows = computed<any[]>(() => [
  ...semanticEntries(semantic.value?.layers?.posts),
  ...semanticEntries(semantic.value?.layers?.comments),
])
const semanticPlatformOptions = computed(() => {
  const platforms = new Set(allSemanticRows.value.map((row) => String(row.platform || '')).filter(Boolean))
  return Array.from(platforms).sort().map((value) => ({ label: value, value }))
})
const semanticMatrixRows = computed<any[]>(() => {
  const query = semanticQuery.value.trim().toLocaleLowerCase()
  return semanticEntries(semantic.value?.layers?.[semanticLayer.value]).filter((row) => {
    if (semanticPlatformFilter.value && row.platform !== semanticPlatformFilter.value) return false
    if (!query) return true
    return semanticSearchText(row).toLocaleLowerCase().includes(query)
  })
})
const semanticSummary = computed(() => ({
  keywords: summarizeSemanticEntries(allSemanticRows.value, 'keywords', 'term'),
  topics: summarizeSemanticEntries(allSemanticRows.value, 'topics', 'label'),
  sentiment: summarizeSemanticLabels(allSemanticRows.value, 'sentiment'),
  stance: summarizeSemanticLabels(allSemanticRows.value, 'stance'),
  entities: summarizeSemanticEntries(allSemanticRows.value, 'entities', 'text'),
}))
const timeSliceRows = computed<any[]>(() => semanticEntries(semantic.value?.cross_analysis?.time_slices))
const platformSliceRows = computed<any[]>(() => semanticEntries(semantic.value?.cross_analysis?.platform_slices))
const communitySliceRows = computed<any[]>(() => semanticEntries(semantic.value?.cross_analysis?.community_slices))
const communitySlicesUnavailableReason = computed(() => String(semantic.value?.cross_analysis?.community_slices_unavailable_reason || ''))
const propagationPathOverlays = computed<any[]>(() => semanticEntries(semantic.value?.cross_analysis?.propagation_path_overlays))
const communityRows = computed(() => (coordinationDiscover.value?.community_lineage || []).slice(0, 5))
const nextHopRows = computed(() => (propagationAnalysis.value?.next_hop_ranking?.items || []).slice(0, 5))
const teacherNodes = computed(() => teacher.value?.dag?.nodes || [])
const activeLearningReasons = computed(() => {
  const reasons = student.value?.signals?.active_learning?.reasons || []
  return reasons.length ? reasons.join(', ') : '-'
})

async function handleCreateSnapshot() {
  if (!snapshotForm.value.event_id.trim()) {
    message.warning('Event ID is required')
    return
  }
  snapshotLoading.value = true
  try {
    const res = await createAnalysisSnapshot(snapshotForm.value) as { data: any }
    snapshot.value = res.data
    runForm.value.event_id = res.data.event_id || snapshotForm.value.event_id
    runForm.value.snapshot_id = res.data.snapshot_id
    message.success('EventSnapshot created')
  } finally {
    snapshotLoading.value = false
  }
}

async function handleCreateRun() {
  if (!runForm.value.event_id.trim() || !runForm.value.snapshot_id.trim()) {
    message.warning('Event ID and Snapshot ID are required')
    return
  }
  if (!runForm.value.requested_stages.length) {
    message.warning('请至少选择一个分析阶段')
    return
  }
  runLoading.value = true
  try {
    const res = await createAnalysisRun({
      event_id: runForm.value.event_id,
      snapshot_id: runForm.value.snapshot_id,
      requested_stages: runForm.value.requested_stages,
      options: parseOptions(),
    }) as { data: any }
    runDetail.value = res.data
    currentRunId.value = res.data.run_id
    semantic.value = null
    await handleLoadEvents()
    message.success('AnalysisRun created')
  } finally {
    runLoading.value = false
  }
}

async function handleExecuteRun() {
  if (!currentRunId.value) return
  executeLoading.value = true
  try {
    semantic.value = null
    const res = await executeAnalysisRun(currentRunId.value) as { data: any }
    runDetail.value = res.data
    await loadSemanticArtifact()
    await handleLoadEvents()
    message.success('AnalysisRun executed')
  } finally {
    executeLoading.value = false
  }
}

async function loadSemanticArtifact() {
  if (!currentRunId.value) return
  semantic.value = null
  try {
    const res = await getAnalysisArtifact(currentRunId.value, 'stage:semantic_enrichment:result') as { data: any }
    semantic.value = res.data
  } catch {
    semantic.value = runResults.value.semantic_enrichment || null
  }
}

async function handleLoadRun() {
  if (!currentRunId.value) return
  semantic.value = null
  const res = await getAnalysisRun(currentRunId.value) as { data: any }
  runDetail.value = res.data
  await loadSemanticArtifact()
}

onMounted(() => {
  void handleLoadRun()
})

async function handleLoadEvents() {
  if (!currentRunId.value) return
  eventsLoading.value = true
  try {
    const res = await listAnalysisRunEvents(currentRunId.value, {
      after_id: afterId.value,
      limit: 200,
    }) as { data: { events: AnalysisRunEvent[] } }
    events.value = mergeEvents(events.value, res.data.events || [])
  } finally {
    eventsLoading.value = false
  }
}

async function handleReadStream() {
  if (!currentRunId.value) return
  stopStream()
  const controller = new AbortController()
  streamAbort.value = controller
  streamLoading.value = true
  try {
    const response = await fetch(analysisStreamUrl(currentRunId.value, latestEventId.value), {
      headers: analysisAuthHeaders(),
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new Error(`SSE backlog failed: ${response.status}`)
    }
    if (response.body) {
      await readSseBacklog(response.body.getReader())
    }
    message.success('SSE backlog loaded')
  } catch (error: any) {
    if (error?.name !== 'AbortError') {
      message.error(error?.message || 'SSE backlog failed')
    }
  } finally {
    streamAbort.value = null
    streamLoading.value = false
  }
}

async function readSseBacklog(reader: ReadableStreamDefaultReader<Uint8Array>) {
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\n\n/)
    buffer = parts.pop() || ''
    for (const part of parts) {
      const event = parseSseEvent(part)
      if (event) {
        events.value = mergeEvents(events.value, [event])
      }
    }
  }
}

function parseSseEvent(raw: string): AnalysisRunEvent | null {
  const lines = raw.split(/\n/).map((line) => line.trim())
  const idLine = lines.find((line) => line.startsWith('id:'))
  const typeLine = lines.find((line) => line.startsWith('event:'))
  const dataLine = lines.find((line) => line.startsWith('data:'))
  if (!idLine || !dataLine) return null
  try {
    const payload = JSON.parse(dataLine.replace(/^data:\s*/, ''))
    return {
      id: Number(idLine.replace(/^id:\s*/, '')),
      run_id: String(payload.run_id || currentRunId.value),
      event_type: typeLine ? typeLine.replace(/^event:\s*/, '') : 'message',
      status: String(payload.status || ''),
      payload: payload.payload || {},
    }
  } catch {
    return null
  }
}

function stopStream() {
  streamAbort.value?.abort()
  streamAbort.value = null
}

function parseOptions() {
  const text = runForm.value.options_json.trim()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    message.error('Options must be valid JSON')
    throw new Error('Invalid analysis options JSON')
  }
}

function mergeEvents(existing: AnalysisRunEvent[], incoming: AnalysisRunEvent[]) {
  const byId = new Map<number, AnalysisRunEvent>()
  for (const item of existing) {
    byId.set(Number(item.id), item)
  }
  for (const item of incoming) {
    byId.set(Number(item.id), item)
  }
  return Array.from(byId.values()).sort((a, b) => Number(a.id) - Number(b.id))
}

function formatJson(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}

function semanticEntries(value: unknown): any[] {
  return Array.isArray(value) ? value : []
}

function semanticTextEntries(value: unknown): string[] {
  return semanticEntries(value).map((item) => String(item || '')).filter(Boolean)
}

function semanticEntryLabel(entry: unknown, preferredKey: string): string {
  if (typeof entry === 'string' || typeof entry === 'number') return String(entry)
  if (!entry || typeof entry !== 'object') return '-'
  const row = entry as Record<string, unknown>
  return String(row[preferredKey] || row.label || row.text || row.term || row.id || '-')
}

function semanticValueLabel(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value)) return semanticValueLabel(value[0])
  if (!value || typeof value !== 'object') return 'unavailable'
  const row = value as Record<string, unknown>
  return String(row.label || row.status || 'unavailable')
}

function semanticSearchText(row: any): string {
  return [
    row.text,
    row.platform,
    semanticValueLabel(row.sentiment),
    semanticValueLabel(row.stance),
    ...semanticEntries(row.keywords).map((item) => semanticEntryLabel(item, 'term')),
    ...semanticEntries(row.topics).map((item) => semanticEntryLabel(item, 'label')),
    ...semanticEntries(row.entities).map((item) => semanticEntryLabel(item, 'text')),
  ].filter(Boolean).join(' ')
}

function summarizeSemanticEntries(rows: any[], field: string, preferredKey: string) {
  const counts = new Map<string, number>()
  for (const row of rows) {
    for (const item of semanticEntries(row?.[field])) {
      const label = semanticEntryLabel(item, preferredKey)
      if (label !== '-') counts.set(label, (counts.get(label) || 0) + 1)
    }
  }
  return Array.from(counts, ([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
    .slice(0, 12)
}

function summarizeSemanticLabels(rows: any[], field: string) {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const label = semanticValueLabel(row?.[field])
    if (label !== 'unavailable') counts.set(label, (counts.get(label) || 0) + 1)
  }
  return Array.from(counts, ([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
}

function formatCounter(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '-'
  const entries = Object.entries(value as Record<string, unknown>)
  return entries.length ? entries.map(([label, count]) => `${label}: ${count}`).join(', ') : '-'
}

function semanticTextList(value: unknown): string {
  const entries = semanticTextEntries(value)
  return entries.length ? entries.join(', ') : '-'
}

function formatTimestamp(value: unknown): string {
  const raw = String(value || '')
  if (!raw) return '-'
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleString()
}

function formatTimeRange(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '-'
  const range = value as Record<string, unknown>
  const start = formatTimestamp(range.start)
  const end = formatTimestamp(range.end)
  return start === end ? start : `${start} - ${end}`
}

function sentimentColor(label: string): string {
  const normalized = label.toLocaleLowerCase()
  if (normalized.includes('negative') || normalized.includes('neg') || normalized.includes('消极')) return 'red'
  if (normalized.includes('positive') || normalized.includes('pos') || normalized.includes('积极')) return 'green'
  return 'default'
}

function stanceColor(label: string): string {
  const normalized = label.toLocaleLowerCase()
  if (normalized.includes('entail') || normalized.includes('support') || normalized.includes('支持')) return 'green'
  if (normalized.includes('contradict') || normalized.includes('oppose') || normalized.includes('反对')) return 'red'
  if (normalized.includes('blocked') || normalized.includes('unavailable')) return 'warning'
  return 'blue'
}

function communitySummary(item: any): string {
  const memberCount = semanticEntries(item?.members).length
  const keywords = semanticEntries(item?.top_keywords)
    .map((entry) => semanticEntryLabel(entry, 'term'))
    .filter((label) => label !== '-')
  const summary = [
    memberCount ? `${memberCount} members` : '',
    item?.sentiment_distribution ? formatCounter(item.sentiment_distribution) : '',
    keywords.length ? `keywords: ${keywords.join(', ')}` : '',
  ].filter(Boolean)
  return summary.length ? summary.join(' | ') : 'Coordination membership only'
}

function numberValue(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function intervalText(interval?: { low?: number; high?: number }) {
  if (!interval) return '-'
  return `[${interval.low ?? '-'}, ${interval.high ?? '-'}]`
}

function statusColor(status?: string) {
  return ({
    queued: 'default',
    running: 'processing',
    needs_evidence: 'warning',
    awaiting_review: 'purple',
    completed: 'success',
    failed: 'error',
    cancelled: 'default',
    ok: 'success',
    data_insufficient: 'warning',
    missing_checkpoint: 'warning',
    unavailable: 'warning',
  } as Record<string, string>)[status || ''] || 'default'
}

onBeforeUnmount(() => {
  stopStream()
})
</script>

<style scoped lang="less">
.analysis-page {
  min-height: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.analysis-alert {
  margin-bottom: 16px;
}

.analysis-card {
  margin-bottom: 16px;
  min-width: 0;
  max-width: 100%;
}

.full-width {
  width: 100%;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.result-card {
  min-height: 260px;
}

.result-text {
  margin: 8px 0 0;
  color: #475569;
}

.intervals,
.dag-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0;
}

.intervals span {
  padding: 4px 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  color: #334155;
  font-size: 12px;
}

.mini-list {
  margin-top: 10px;
}

.mini-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 0;
  border-bottom: 1px solid #eef2f7;
  color: #475569;
  font-size: 12px;
}

.semantic-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.semantic-summary-panel {
  min-width: 0;
  padding: 9px;
  border: 1px solid #e5e7eb;
  background: #fafcff;
}

.semantic-summary-panel h4,
.semantic-cross-panel h4,
.path-overlay-heading h4 {
  margin: 0 0 8px;
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
}

.semantic-summary-panel:last-child {
  grid-column: 1 / -1;
}

.semantic-empty,
.slice-detail,
.semantic-section-heading p,
.path-overlay-heading span,
.path-overlay-evidence span,
.path-overlay-tags > span {
  color: #64748b;
  font-size: 12px;
}

.distribution-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.distribution-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.semantic-matrix-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.semantic-platform-filter {
  min-width: 150px;
}

.semantic-query {
  flex: 1 1 280px;
  min-width: 220px;
}

.matrix-id {
  display: block;
  max-width: 130px;
  margin-top: 4px;
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.semantic-text {
  display: -webkit-box;
  overflow: hidden;
  color: #334155;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.analysis-page :deep(.ant-table-wrapper),
.analysis-page :deep(.ant-table-container) {
  max-width: 100%;
}

.analysis-page :deep(.ant-table-content) {
  overflow-x: auto;
}

.semantic-cross-analysis {
  margin-bottom: 16px;
}

.semantic-section-heading {
  display: flex;
  justify-content: space-between;
  align-items: end;
  margin-bottom: 10px;
}

.semantic-section-heading h3 {
  margin: 0;
  color: #1f2937;
  font-size: 16px;
}

.semantic-section-heading p {
  margin: 4px 0 0;
}

.semantic-cross-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.semantic-cross-panel,
.path-overlay-section {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.semantic-cross-panel :deep(.ant-list-item) {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.semantic-cross-panel :deep(.ant-list-item > div) {
  min-width: 0;
}

.slice-detail {
  display: block;
  margin-top: 2px;
  line-height: 1.45;
}

.path-overlay-section {
  margin-top: 12px;
}

.path-overlay-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.path-overlay-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.path-overlay-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe4ee;
  background: #fbfdff;
}

.path-overlay-title {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.path-overlay-title strong {
  min-width: 0;
  overflow: hidden;
  color: #1e3a5f;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-overlay-details {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0;
}

.path-overlay-details dt {
  color: #64748b;
  font-size: 11px;
}

.path-overlay-details dd {
  margin: 2px 0 0;
  overflow-wrap: anywhere;
  color: #334155;
  font-size: 12px;
}

.path-overlay-tags,
.path-overlay-evidence {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  margin-top: 7px;
}

.path-overlay-claim {
  display: flex;
  gap: 6px;
  margin-top: 7px;
  color: #475569;
  font-size: 12px;
}

.path-overlay-claim span {
  flex: 0 0 52px;
  color: #64748b;
}

.path-overlay-claim strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.path-overlay-tags > span,
.path-overlay-evidence > span {
  min-width: 52px;
}

.event-actions {
  margin-bottom: 12px;
}

.run-input {
  width: 360px;
}

.event-list {
  max-height: 520px;
  overflow: auto;
}

.event-item {
  width: 100%;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

pre {
  margin: 0;
  padding: 10px;
  max-height: 180px;
  overflow: auto;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
}

@media (max-width: 992px) {
  .result-grid,
  .form-grid,
  .semantic-cross-grid,
  .path-overlay-grid {
    grid-template-columns: 1fr;
  }

  .run-input {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .semantic-summary-grid,
  .path-overlay-details {
    grid-template-columns: 1fr;
  }

  .analysis-page :deep(.ant-table-wrapper) {
    overflow-x: hidden;
  }
}
</style>
