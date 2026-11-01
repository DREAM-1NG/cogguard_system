<template>
  <div class="semantic-workspace">
    <PageHeader
      title="事件研判 · 语义证据"
      description="在同一事件范围内关联查看语义信号与可定位的快照内容。"
    />

    <RiskSectionTabs :event-id="eventId.trim()" :case-id="caseId" />

    <section class="scope-bar" aria-label="事件范围">
      <label class="scope-field" for="semantic-event-id">
        <span>事件 ID</span>
        <AInput
          id="semantic-event-id"
          v-model:value="eventId"
          allow-clear
          name="semantic-event-id"
          autocomplete="off"
          placeholder="输入事件 ID…"
          @press-enter="refreshWorkspace"
        />
      </label>
      <ATooltip title="刷新当前事件的语义证据">
        <AButton :loading="loading" aria-label="刷新语义证据" @click="refreshWorkspace">
          <ReloadOutlined />
        </AButton>
      </ATooltip>
      <router-link class="review-link" :to="reviewDestination">查看事件研判</router-link>
      <span v-if="projection?.snapshot_id" class="scope-meta">快照 {{ projection.snapshot_id }}</span>
    </section>

    <AAlert
      v-if="loadError"
      class="state-alert"
      type="warning"
      show-icon
      message="语义证据加载失败"
      :description="loadError"
    />
    <ASkeleton v-else-if="loading && !workspace" active :paragraph="{ rows: 8 }" />
    <AResult
      v-else-if="!workspace"
      status="info"
      :title="emptyTitle"
      :sub-title="emptyDescription"
    />

    <template v-else>
      <section class="workspace-status" aria-label="语义证据状态">
        <div>
          <span class="status-label">当前范围</span>
          <strong>{{ summary.record_count }}</strong>
          <span>条内容</span>
        </div>
        <div>
          <span class="status-label">涉及平台</span>
          <strong>{{ summary.platform_count }}</strong>
          <span>个</span>
        </div>
        <div class="status-note">
          <span class="status-label">联动状态</span>
          <span>{{ hasActiveFilters ? '已按当前条件更新全部语义切片' : '显示当前事件的语义切片' }}</span>
          <ASpin v-if="loading" size="small" />
        </div>
      </section>

      <section class="workspace-controls" aria-label="语义证据筛选">
        <div class="control-group control-layer">
          <span class="control-label">内容范围</span>
          <ASegmented aria-label="内容范围" :options="layerOptions" :value="filters.layer" size="small" @update:value="setLayer" />
        </div>
        <div class="control-group control-platforms">
          <span class="control-label">平台</span>
          <button
            v-for="item in platformRows"
            :key="item.key"
            class="platform-button"
            :class="{ 'is-selected': filters.platforms.includes(item.key) }"
            type="button"
            :aria-pressed="filters.platforms.includes(item.key)"
            @click="togglePlatform(item.key)"
          >
            {{ item.label }} <b>{{ item.count }}</b>
          </button>
        </div>
        <ATooltip title="清除全部筛选">
          <AButton
            class="clear-filter-button"
            :disabled="!hasActiveFilters"
            size="small"
            type="text"
            aria-label="清除全部筛选"
            @click="clearFilters"
          >
            <ClearOutlined />
          </AButton>
        </ATooltip>
      </section>

      <div v-if="activeFilters.length" class="active-filters" aria-label="当前筛选">
        <span class="control-label">当前筛选</span>
        <button
          v-for="item in activeFilters"
          :key="item.field"
          class="active-filter"
          type="button"
          :aria-label="`移除筛选 ${item.label}`"
          @click="clearFilter(item.field)"
        >
          {{ item.label }} <CloseOutlined />
        </button>
      </div>

      <section v-if="selectedRelation" class="linked-context" aria-label="当前关联摘要">
        <div>
          <span class="section-kicker">关联摘要</span>
          <strong>{{ selectedRelation.label }}</strong>
          <span>{{ selectedRelation.count }} 条匹配内容</span>
        </div>
        <div class="context-signals">
          <span v-if="compactCounts(selectedRelation.sentiment)">情感 {{ compactCounts(selectedRelation.sentiment, 'sentiment') }}</span>
          <span v-if="compactCounts(selectedRelation.stance)">立场 {{ compactCounts(selectedRelation.stance, 'stance') }}</span>
          <span v-if="compactCounts(selectedRelation.topics)">主题 {{ compactCounts(selectedRelation.topics) }}</span>
        </div>
      </section>

      <section class="workspace-grid overview-grid">
        <article class="workspace-panel keyword-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">语义证据</span>
              <h3>关键词词云</h3>
            </div>
            <span>{{ keywordCloud.length }} 个高频词</span>
          </div>
          <SemanticKeywordCloud
            v-if="showKeywordCloud && keywordCloud.length"
            :items="keywordCloud"
            :selected-term="filters.keyword"
            @select="(term) => toggleSingle('keyword', term)"
          />
          <ASkeleton v-else-if="keywordCloud.length" active :paragraph="{ rows: 5 }" />
          <AEmpty v-else description="当前条件下没有可展示的关键词" :image-style="{ height: '42px' }" />
        </article>

        <article class="workspace-panel distribution-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">内容信号</span>
              <h3>情感与立场</h3>
            </div>
            <span>{{ summary.record_count }} 条内容</span>
          </div>
          <div class="distribution-block">
            <strong>情感</strong>
            <button
              v-for="item in sentimentRows"
              :key="item.key"
              class="distribution-row"
              :class="{ 'is-selected': filters.sentiment === item.key }"
              type="button"
              :aria-pressed="filters.sentiment === item.key"
              @click="toggleSingle('sentiment', item.key)"
            >
              <span>{{ semanticLabel('sentiment', item.label) }}</span>
              <span class="distribution-track"><i :style="{ width: `${ratio(item.count, sentimentRows)}%` }" /></span>
              <b>{{ item.count }}</b>
            </button>
          </div>
          <div class="distribution-block">
            <strong>立场</strong>
            <button
              v-for="item in stanceRows"
              :key="item.key"
              class="distribution-row"
              :class="{ 'is-selected': filters.stance === item.key }"
              type="button"
              :aria-pressed="filters.stance === item.key"
              @click="toggleSingle('stance', item.key)"
            >
              <span>{{ semanticLabel('stance', item.label) }}</span>
              <span class="distribution-track"><i :style="{ width: `${ratio(item.count, stanceRows)}%` }" /></span>
              <b>{{ item.count }}</b>
            </button>
          </div>
        </article>
      </section>

      <section class="workspace-grid ledger-grid">
        <article class="workspace-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">语义聚类</span>
              <h3>主题轨道</h3>
            </div>
            <span>按内容量排序</span>
          </div>
          <div v-if="topicRows.length" class="facet-list">
            <button
              v-for="item in topicRows.slice(0, 12)"
              :key="item.key"
              class="facet-row topic-row"
              :class="{ 'is-selected': filters.topic === item.key }"
              type="button"
              :aria-pressed="filters.topic === item.key"
              @click="toggleSingle('topic', item.key)"
            >
              <span>{{ item.label }}</span>
              <i><em :style="{ width: `${ratio(item.count, topicRows)}%` }" /></i>
              <b>{{ item.count }}</b>
            </button>
          </div>
          <AEmpty v-else description="当前条件下未形成主题聚类" :image-style="{ height: '42px' }" />
        </article>

        <article class="workspace-panel entity-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">命名实体</span>
              <h3>实体清单</h3>
            </div>
            <AButton
              v-if="entityGroups.length > 3"
              class="entity-toggle"
              size="small"
              type="link"
              :aria-expanded="entityGroupsExpanded"
              @click="entityGroupsExpanded = !entityGroupsExpanded"
            >{{ entityGroupsExpanded ? '收起' : '展开' }}</AButton>
          </div>
          <div v-if="visibleEntityGroups.length" class="entity-groups">
            <div v-for="group in visibleEntityGroups" :key="group.type" class="entity-group">
              <span class="entity-type">{{ entityTypeLabel(group.type) }}</span>
              <button
                v-for="item in group.items.slice(0, 6)"
                :key="item.key"
                class="facet-row entity-row"
                :class="{ 'is-selected': filters.entity === `${group.type}:${item.key}` }"
                type="button"
                :aria-pressed="filters.entity === `${group.type}:${item.key}`"
                @click="toggleSingle('entity', `${group.type}:${item.key}`)"
              >
                <span>{{ item.label }}</span>
                <i><em :style="{ width: `${ratio(item.count, group.items)}%` }" /></i>
                <b>{{ item.count }}</b>
              </button>
            </div>
          </div>
          <AEmpty v-else description="当前条件下没有可展示的实体" :image-style="{ height: '42px' }" />
        </article>
      </section>

      <section class="workspace-grid timeline-grid">
        <article class="workspace-panel timeline-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">时间变化</span>
              <h3>内容时间条带</h3>
            </div>
            <span>点击日期筛选</span>
          </div>
          <div v-if="timeRows.length" class="time-strip" role="group" :aria-label="temporalAriaLabel">
            <button
              v-for="item in timeRows"
              :key="item.key"
              class="time-column"
              :class="{ 'is-selected': filters.date === item.key }"
              type="button"
              :aria-pressed="filters.date === item.key"
              :aria-label="`${item.label}，${item.count} 条内容`"
              @click="toggleSingle('date', item.key)"
            >
              <b>{{ item.count }}</b>
              <i><em :style="{ height: `${ratio(item.count, timeRows)}%` }" /></i>
              <span>{{ shortDate(item.label) }}</span>
            </button>
          </div>
          <AEmpty v-else description="当前条件下没有时间切片" :image-style="{ height: '42px' }" />
        </article>

        <article class="workspace-panel platform-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">跨平台</span>
              <h3>内容来源分布</h3>
            </div>
            <span>{{ platformRows.length }} 个平台</span>
          </div>
          <div v-if="platformRows.length" class="facet-list">
            <button
              v-for="item in platformRows"
              :key="item.key"
              class="facet-row platform-row"
              :class="{ 'is-selected': filters.platforms.includes(item.key) }"
              type="button"
              :aria-pressed="filters.platforms.includes(item.key)"
              @click="togglePlatform(item.key)"
            >
              <span>{{ item.label }}</span>
              <i><em :style="{ width: `${ratio(item.count, platformRows)}%` }" /></i>
              <b>{{ item.count }}</b>
            </button>
          </div>
          <AEmpty v-else description="当前条件下没有平台分布" :image-style="{ height: '42px' }" />
        </article>
      </section>

      <AAlert
        class="traceability-alert"
        type="info"
        show-icon
        message="可核验仅表示可定位回事件快照中的原始内容和引用，不等于事实已被证实。"
      />
      <section class="workspace-panel traceable-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">快照证据</span>
            <h3>可核验内容</h3>
          </div>
          <span>{{ traceableRecords.length }} / {{ traceableTotal }} 条</span>
        </div>
        <div v-if="traceableRecords.length" class="traceable-table-wrap">
          <table class="traceable-table">
            <thead>
              <tr>
                <th>内容</th>
                <th>关键词</th>
                <th>主题</th>
                <th>情感</th>
                <th>立场</th>
                <th>实体</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in traceableRecords" :key="record.evidence_ref">
                <td data-label="内容" class="record-cell">
                  <div class="record-meta">
                    <ATag>{{ record.layer === 'posts' ? '主帖' : '评论' }}</ATag>
                    <span>{{ record.platform }}</span>
                    <span>{{ formatTimestamp(record.timestamp) }}</span>
                  </div>
                  <p>{{ record.text || '快照未保存可展示原文。' }}<span v-if="record.text_truncated">…</span></p>
                  <div class="record-reference">
                    <code>{{ record.evidence_ref }}</code>
                    <a v-if="record.source_url" :href="record.source_url" target="_blank" rel="noopener noreferrer">原始链接</a>
                  </div>
                </td>
                <td data-label="关键词"><span class="value-list"><button v-for="value in record.keywords || []" :key="value" type="button" @click="toggleSingle('keyword', value)">{{ value }}</button></span></td>
                <td data-label="主题"><span class="value-list"><button v-for="value in record.topics || []" :key="value" type="button" @click="toggleSingle('topic', value)">{{ value }}</button></span></td>
                <td data-label="情感"><button v-if="record.sentiment" class="plain-value" type="button" @click="toggleSingle('sentiment', record.sentiment)">{{ semanticLabel('sentiment', record.sentiment) }}</button></td>
                <td data-label="立场"><button v-if="record.stance" class="plain-value" type="button" @click="toggleSingle('stance', record.stance)">{{ semanticLabel('stance', record.stance) }}</button></td>
                <td data-label="实体"><span class="value-list"><button v-for="entity in record.entities || []" :key="entity.key" type="button" @click="toggleSingle('entity', entity.key)">{{ entity.text }}</button></span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <AEmpty v-else description="没有内容符合当前语义筛选" :image-style="{ height: '42px' }" />
        <APagination
          v-if="traceableTotal > traceablePageSize"
          class="traceable-pagination"
          :current="traceablePage"
          :page-size="traceablePageSize"
          :show-size-changer="false"
          :total="traceableTotal"
          @change="loadWorkspace"
        />
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ClearOutlined, CloseOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import {
  AAlert,
  AButton,
  AEmpty,
  AInput,
  APagination,
  AResult,
  ASegmented,
  ASkeleton,
  ASpin,
  ATag,
  ATooltip,
} from '@/ui/semanticWorkspaceControls'
import PageHeader from '@/components/PageHeader.vue'
import RiskSectionTabs from '@/views/risk/RiskSectionTabs.vue'
import SemanticKeywordCloud from '@/components/SemanticKeywordCloud.vue'
import {
  getSemanticWorkspace,
  type SemanticCount,
  type SemanticFacetRelation,
  type SemanticTraceableRecord,
  type SemanticWorkspaceContent,
  type SemanticWorkspaceFilters,
  type SemanticWorkspaceLayer,
  type SemanticWorkspaceProjection,
} from '@/api/analysis'
import { buildKeywordCloudFromCounts, displaySemanticLabel } from '@/features/semantic-evidence/model'

const DEFAULT_EVENT_ID = 'trump_visit_2026_05_21'
const EMPTY_COUNTS: SemanticCount[] = []
const EMPTY_RECORDS: SemanticTraceableRecord[] = []
const EMPTY_SUMMARY = { record_count: 0, platform_count: 0 }
const DEFAULT_FILTERS: SemanticWorkspaceFilters = {
  layer: 'all',
  platforms: [],
  date: null,
  keyword: null,
  topic: null,
  sentiment: null,
  stance: null,
  entity: null,
}

type SingleFilter = Exclude<keyof SemanticWorkspaceFilters, 'layer' | 'platforms'>

const route = useRoute()
const eventId = ref(readQueryEventId() || DEFAULT_EVENT_ID)
const caseId = computed(() => readQueryCaseId())
const projection = ref<SemanticWorkspaceProjection | null>(null)
const filters = ref<SemanticWorkspaceFilters>(copyFilters(DEFAULT_FILTERS))
const loading = ref(false)
const loadError = ref('')
const showKeywordCloud = ref(false)
const entityGroupsExpanded = ref(false)
let requestSequence = 0
let keywordCloudFrame: number | null = null

const workspace = computed<SemanticWorkspaceContent | null>(() => (
  projection.value?.status === 'ready' && projection.value.content ? projection.value.content : null
))
const summary = computed(() => workspace.value ? projection.value?.summary || EMPTY_SUMMARY : EMPTY_SUMMARY)
const keywordRows = computed(() => workspace.value?.evidence.keywords || EMPTY_COUNTS)
const keywordCloud = computed(() => buildKeywordCloudFromCounts(keywordRows.value))
const sentimentRows = computed(() => workspace.value?.evidence.sentiment || EMPTY_COUNTS)
const stanceRows = computed(() => workspace.value?.evidence.stance || EMPTY_COUNTS)
const topicRows = computed(() => workspace.value?.clusters.topics || EMPTY_COUNTS)
const entityGroups = computed(() => workspace.value?.entities.groups || [])
const visibleEntityGroups = computed(() => (
  entityGroupsExpanded.value ? entityGroups.value : entityGroups.value.slice(0, 3)
))
const timeRows = computed(() => workspace.value?.temporal.time_slices || EMPTY_COUNTS)
const platformRows = computed(() => workspace.value?.temporal.platforms || EMPTY_COUNTS)
const traceableRecords = computed(() => workspace.value?.traceable.items || EMPTY_RECORDS)
const traceablePage = computed(() => workspace.value?.traceable.page || 1)
const traceablePageSize = computed(() => workspace.value?.traceable.page_size || 40)
const traceableTotal = computed(() => workspace.value?.traceable.total || 0)
const hasActiveFilters = computed(() => (
  filters.value.layer !== 'all'
  || filters.value.platforms.length > 0
  || Boolean(filters.value.date || filters.value.keyword || filters.value.topic)
  || Boolean(filters.value.sentiment || filters.value.stance || filters.value.entity)
))
const activeFilters = computed<Array<{ field: keyof SemanticWorkspaceFilters; label: string }>>(() => {
  const values: Array<{ field: keyof SemanticWorkspaceFilters; label: string }> = []
  if (filters.value.layer !== 'all') values.push({ field: 'layer', label: filters.value.layer === 'posts' ? '主帖' : '评论' })
  if (filters.value.platforms.length) values.push({ field: 'platforms', label: `平台：${filters.value.platforms.join('、')}` })
  if (filters.value.date) values.push({ field: 'date', label: `日期：${filters.value.date}` })
  if (filters.value.keyword) values.push({ field: 'keyword', label: `关键词：${filters.value.keyword}` })
  if (filters.value.topic) values.push({ field: 'topic', label: `主题：${filters.value.topic}` })
  if (filters.value.sentiment) values.push({ field: 'sentiment', label: `情感：${semanticLabel('sentiment', filters.value.sentiment)}` })
  if (filters.value.stance) values.push({ field: 'stance', label: `立场：${semanticLabel('stance', filters.value.stance)}` })
  if (filters.value.entity) values.push({ field: 'entity', label: `实体：${filters.value.entity.split(':').slice(1).join(':')}` })
  return values
})
const selectedRelation = computed<SemanticFacetRelation | null>(() => {
  const relations = workspace.value?.relations || {}
  const selection = [
    ['entities', filters.value.entity],
    ['topics', filters.value.topic],
    ['keywords', filters.value.keyword],
    ['time_slices', filters.value.date],
  ] as const
  for (const [dimension, key] of selection) {
    if (!key) continue
    const relation = relations[dimension]?.find((item) => item.key === key)
    if (relation) return relation
  }
  if (filters.value.platforms.length === 1) {
    return relations.platforms?.find((item) => item.key === filters.value.platforms[0]) || null
  }
  return null
})
const emptyTitle = computed(() => eventId.value.trim() ? '当前事件尚无可用语义证据' : '请选择事件范围')
const emptyDescription = computed(() => {
  if (!eventId.value.trim()) return '输入事件 ID 后加载已完成的语义分析。'
  if (projection.value?.blocking_reason) return '该语义制品当前未通过可用性或快照一致性检查。'
  return '需要先为当前事件生成并保存完整语义制品。'
})
const temporalAriaLabel = computed(() => `时间条带：${timeRows.value.map((item) => `${item.label} ${item.count} 条`).join('；')}`)
const reviewDestination = computed(() => ({ path: '/risk', query: reviewScopeQuery() }))
const layerOptions: Array<{ label: string; value: SemanticWorkspaceLayer }> = [
  { label: '全部', value: 'all' },
  { label: '主帖', value: 'posts' },
  { label: '评论', value: 'comments' },
]

function loadWorkspace(requestedPage = 1) {
  const requestedEventId = eventId.value.trim()
  const sequence = ++requestSequence
  loadError.value = ''
  if (!requestedEventId) {
    projection.value = null
    return
  }
  loading.value = true
  void getSemanticWorkspace(requestedEventId, { ...filters.value, page: requestedPage, pageSize: 40 })
    .then((response) => {
      if (sequence !== requestSequence || requestedEventId !== eventId.value.trim()) return
      projection.value = response.data
    })
    .catch(() => {
      if (sequence === requestSequence && requestedEventId === eventId.value.trim()) {
        loadError.value = '无法读取当前事件的语义制品，请确认服务和事件范围。'
      }
    })
    .finally(() => {
      if (sequence === requestSequence && requestedEventId === eventId.value.trim()) loading.value = false
    })
}

function refreshWorkspace() {
  loadWorkspace(1)
}

function setLayer(layer: string | number) {
  const next: SemanticWorkspaceLayer = layer === 'posts' || layer === 'comments' ? layer : 'all'
  if (filters.value.layer === next) return
  filters.value = { ...filters.value, layer: next }
  loadWorkspace(1)
}

function togglePlatform(platform: string) {
  const platforms = filters.value.platforms.includes(platform)
    ? filters.value.platforms.filter((value) => value !== platform)
    : [...filters.value.platforms, platform]
  filters.value = { ...filters.value, platforms }
  loadWorkspace(1)
}

function toggleSingle(field: SingleFilter, value: string | null) {
  const next = value && filters.value[field] === value ? null : value
  filters.value = { ...filters.value, [field]: next }
  loadWorkspace(1)
}

function clearFilters() {
  if (!hasActiveFilters.value) return
  filters.value = copyFilters(DEFAULT_FILTERS)
  loadWorkspace(1)
}

function clearFilter(field: keyof SemanticWorkspaceFilters) {
  if (field === 'layer') filters.value = { ...filters.value, layer: 'all' }
  else if (field === 'platforms') filters.value = { ...filters.value, platforms: [] }
  else filters.value = { ...filters.value, [field]: null }
  loadWorkspace(1)
}

function scheduleKeywordCloud() {
  if (keywordCloudFrame !== null) {
    cancelAnimationFrame(keywordCloudFrame)
    keywordCloudFrame = null
  }
  showKeywordCloud.value = false
  if (!keywordCloud.value.length) return
  keywordCloudFrame = requestAnimationFrame(() => {
    keywordCloudFrame = requestAnimationFrame(() => {
      if (keywordCloud.value.length) showKeywordCloud.value = true
      keywordCloudFrame = null
    })
  })
}

function readQueryEventId(): string {
  const value = route.query.event_id
  return typeof value === 'string' ? value.trim() : ''
}

function readQueryCaseId(): string {
  const value = route.query.case_id
  return typeof value === 'string' ? value.trim() : ''
}

function reviewScopeQuery(): { event_id: string; case_id?: string } {
  const query: { event_id: string; case_id?: string } = { event_id: eventId.value.trim() }
  if (caseId.value) query.case_id = caseId.value
  return query
}

function copyFilters(value: SemanticWorkspaceFilters): SemanticWorkspaceFilters {
  return { ...value, platforms: [...value.platforms] }
}

function ratio(count: number, values: SemanticCount[]): number {
  const maximum = Math.max(...values.map((item) => item.count), 0)
  return maximum > 0 ? Math.max(2, Math.round((count / maximum) * 100)) : 0
}

function semanticLabel(field: 'sentiment' | 'stance', value: string): string {
  return displaySemanticLabel(field, value)
}

function entityTypeLabel(type: string): string {
  return ({ PER: '人物', ORG: '组织', LOC: '地点', OTHER: '其他实体' } as Record<string, string>)[type] || type
}

function compactCounts(items: SemanticCount[], field?: 'sentiment' | 'stance'): string {
  return items.slice(0, 3).map((item) => (
    field ? `${semanticLabel(field, item.label)} ${item.count}` : `${item.label} ${item.count}`
  )).join('、')
}

function shortDate(value: string): string {
  return value === 'unknown' ? '未知' : value.slice(5) || value
}

function formatTimestamp(value: string): string {
  if (!value || value === 'unknown') return '时间未记录'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', { hour12: false })
}

function syncRouteScope() {
  const routeEventId = readQueryEventId()
  if (routeEventId && routeEventId !== eventId.value) {
    eventId.value = routeEventId
    filters.value = copyFilters(DEFAULT_FILTERS)
    refreshWorkspace()
  }
}

watch(() => route.query.event_id, syncRouteScope)
watch(keywordRows, scheduleKeywordCloud, { flush: 'post' })
onMounted(refreshWorkspace)
onActivated(syncRouteScope)
onBeforeUnmount(() => {
  if (keywordCloudFrame !== null) cancelAnimationFrame(keywordCloudFrame)
})
</script>

<style scoped lang="less">
.semantic-workspace { color: #1f2937; font-variant-numeric: tabular-nums; }

.scope-bar, .workspace-controls, .active-filters, .linked-context {
  display: flex; align-items: center; gap: 10px; border: 1px solid #d7e1eb; background: #ffffff;
}

.scope-bar { align-items: end; flex-wrap: wrap; margin-bottom: 16px; padding: 10px 12px; border-radius: 8px; }
.scope-field { display: grid; gap: 4px; min-width: min(100%, 320px); }
.scope-field > span, .scope-meta, .status-label, .section-kicker, .panel-heading > span, .control-label { color: #64748b; font-size: 12px; line-height: 1.45; }
.scope-meta { margin-left: auto; overflow-wrap: anywhere; }
.review-link { align-self: center; color: #1d67a0; font-size: 13px; line-height: 1.5; text-decoration: none; }
.review-link:hover { color: #0f4d78; text-decoration: underline; }
.state-alert, .traceability-alert { margin-bottom: 16px; }

.workspace-status { display: grid; grid-template-columns: minmax(0, .22fr) minmax(0, .22fr) minmax(0, .56fr); gap: 1px; margin-bottom: 16px; overflow: hidden; border: 1px solid #d7e1eb; background: #d7e1eb; }
.workspace-status > div { display: flex; align-items: baseline; gap: 7px; min-width: 0; padding: 11px 13px; background: #fbfcfe; color: #52667c; font-size: 13px; line-height: 1.5; }
.workspace-status strong { color: #162b40; font-size: 18px; }
.workspace-status .status-note { align-items: center; }

.workspace-controls { flex-wrap: wrap; margin-bottom: 8px; padding: 9px 11px; border-radius: 8px; }
.control-group, .control-platforms { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }
.control-layer { padding-right: 11px; border-right: 1px solid #e5edf4; }
.clear-filter-button { margin-left: auto; }

.platform-button, .active-filter, .facet-row, .distribution-row, .time-column, .value-list button, .plain-value { border: 0; font: inherit; }
.platform-button { padding: 4px 8px; border: 1px solid #ccd9e5; border-radius: 4px; background: #f8fbfd; color: #3d556d; cursor: pointer; font-size: 12px; }
.platform-button b { margin-left: 3px; color: #204f76; }
.platform-button:hover, .platform-button.is-selected { border-color: #4d88ae; background: #eaf4fa; color: #144f76; }

.active-filters { flex-wrap: wrap; margin-bottom: 12px; padding: 7px 10px; border-color: #e4ebf1; background: #f9fbfd; }
.active-filter { display: inline-flex; align-items: center; gap: 5px; padding: 3px 7px; border-radius: 4px; background: #e6f0f6; color: #245b80; cursor: pointer; font-size: 12px; }
.active-filter:hover { background: #d7eaf5; }

.linked-context { justify-content: space-between; flex-wrap: wrap; margin-bottom: 16px; padding: 10px 12px; border-left: 3px solid #d17b3f; background: #fffdf8; color: #4e5f6c; font-size: 13px; }
.linked-context > div:first-child, .context-signals { display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px; }
.linked-context strong { color: #293b4a; }
.context-signals { gap: 12px; color: #5f6872; font-size: 12px; }

.workspace-grid { display: grid; align-items: start; gap: 16px; margin-bottom: 16px; }
.overview-grid { grid-template-columns: minmax(0, 1.15fr) minmax(300px, .85fr); }
.ledger-grid, .timeline-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.overview-grid, .ledger-grid, .timeline-grid { align-items: stretch; }
.workspace-panel { min-width: 0; margin-bottom: 16px; padding: 14px; border: 1px solid #d7e1eb; border-top: 3px solid #4a7fa6; border-radius: 8px; background: #ffffff; }
.overview-grid .workspace-panel, .ledger-grid .workspace-panel, .timeline-grid .workspace-panel { margin-bottom: 0; }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.panel-heading h3 { margin: 2px 0 0; color: #162b40; font-size: 16px; font-weight: 650; line-height: 1.45; }
.panel-heading > span { max-width: 45%; text-align: right; }

.distribution-block { display: grid; gap: 7px; }
.distribution-block + .distribution-block { margin-top: 12px; padding-top: 12px; border-top: 1px solid #edf2f7; }
.distribution-block > strong { color: #334155; font-size: 13px; }
.distribution-row, .facet-row { display: grid; grid-template-columns: minmax(76px, .42fr) minmax(72px, 1fr) 34px; align-items: center; gap: 8px; width: 100%; padding: 4px 0; background: transparent; color: #475569; cursor: pointer; font-size: 13px; text-align: left; }
.distribution-row:hover, .distribution-row.is-selected, .facet-row:hover, .facet-row.is-selected { color: #14577f; }
.distribution-row > span:first-child, .facet-row > span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.distribution-row b, .facet-row b { color: #1e293b; font-size: 13px; text-align: right; }
.distribution-track, .facet-row > i { display: block; height: 7px; overflow: hidden; background: #e8eff5; }
.distribution-track i, .facet-row > i > em { display: block; height: 100%; background: #3c789f; }
.distribution-row.is-selected .distribution-track i, .facet-row.is-selected > i > em { background: #d17b3f; }
.facet-list, .entity-groups { display: grid; gap: 7px; }
.entity-groups { gap: 13px; }
.entity-group { display: grid; gap: 4px; }
.entity-type { color: #6c5a91; font-size: 12px; font-weight: 650; }
.entity-toggle { padding: 0; }

.time-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(48px, 1fr)); align-items: end; gap: 7px; min-height: 206px; }
.time-column { display: grid; grid-template-rows: auto 140px auto; align-items: end; gap: 7px; min-width: 0; padding: 0; background: transparent; color: #64748b; cursor: pointer; font-size: 12px; text-align: center; }
.time-column b { color: #324a60; }
.time-column > i { display: flex; align-items: end; height: 140px; overflow: hidden; border-bottom: 1px solid #cbd8e5; background: repeating-linear-gradient(to top, transparent 0 34px, #edf2f7 34px 35px); }
.time-column > i > em { display: block; width: 100%; min-height: 2px; background: #c48045; }
.time-column.is-selected > i > em { background: #2d7592; }
.time-column > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.traceable-table-wrap { overflow-x: auto; }
.traceable-table { width: 100%; min-width: 920px; border-collapse: collapse; table-layout: fixed; }
.traceable-table th, .traceable-table td { padding: 10px; border-bottom: 1px solid #e6edf3; color: #475569; font-size: 13px; text-align: left; vertical-align: top; }
.traceable-table th { color: #52667c; font-size: 12px; font-weight: 650; }
.traceable-table th:first-child, .traceable-table td:first-child { width: 36%; }
.record-meta, .record-reference, .value-list { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.record-meta, .record-reference { color: #64748b; font-size: 12px; }
.record-cell p { display: -webkit-box; margin: 7px 0; overflow: hidden; color: #334155; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.record-reference code { max-width: 270px; overflow: hidden; color: #48657b; font-family: Consolas, 'Courier New', monospace; text-overflow: ellipsis; white-space: nowrap; }
.record-reference a { color: #1d67a0; }
.value-list button, .plain-value { padding: 0; background: transparent; color: #285d82; cursor: pointer; font-size: 12px; line-height: 1.5; text-align: left; }
.value-list button:hover, .plain-value:hover { color: #b45d39; text-decoration: underline; }
.traceable-pagination { margin-top: 16px; }
.ledger-grid, .timeline-grid, .traceability-alert, .traceable-panel { content-visibility: auto; contain-intrinsic-size: auto 360px; }
button:focus-visible, a:focus-visible { outline: 3px solid #91caff; outline-offset: 2px; }

@media (max-width: 900px) {
  .overview-grid, .ledger-grid, .timeline-grid, .workspace-status { grid-template-columns: 1fr; }
  .workspace-status > div { min-height: 48px; }
  .control-layer { padding-right: 0; border-right: 0; }
}

@media (max-width: 720px) {
  .scope-bar { align-items: stretch; }
  .scope-field { flex: 1 1 100%; }
  .scope-meta { margin-left: 0; width: 100%; }
  .workspace-controls, .active-filters, .linked-context { align-items: flex-start; }
  .clear-filter-button { margin-left: 0; }
  .time-strip { grid-template-columns: repeat(auto-fit, minmax(38px, 1fr)); gap: 5px; }
  .time-column { font-size: 11px; }
  .traceable-table { min-width: 0; }
  .traceable-table thead { display: none; }
  .traceable-table, .traceable-table tbody, .traceable-table tr, .traceable-table td { display: block; width: 100%; }
  .traceable-table tr { padding: 8px 0; border-bottom: 1px solid #dce6ef; }
  .traceable-table td { display: grid; grid-template-columns: 66px minmax(0, 1fr); gap: 8px; padding: 5px 0; border: 0; }
  .traceable-table td::before { content: attr(data-label); color: #64748b; font-size: 12px; }
  .traceable-table td.record-cell { display: block; }
  .record-cell::before { display: block; margin-bottom: 6px; }
}
</style>
