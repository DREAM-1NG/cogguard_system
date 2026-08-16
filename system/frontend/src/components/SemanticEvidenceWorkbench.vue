<template>
  <div class="semantic-workbench" aria-label="语义研判工作台">
    <div class="workbench-toolbar">
      <div class="toolbar-scope">
        <span class="toolbar-label">内容范围</span>
        <a-segmented v-model:value="filters.layer" :options="layerOptions" size="small" />
      </div>
      <a-tooltip title="清除全部语义筛选">
        <a-button
          aria-label="清除全部语义筛选"
          size="small"
          type="text"
          :disabled="!hasActiveFilters"
          @click="resetFilters"
        >
          <ClearOutlined />
        </a-button>
      </a-tooltip>
    </div>

    <div class="platform-filter" aria-label="平台筛选">
      <span class="toolbar-label">平台</span>
      <button
        v-for="item in platformRows"
        :key="item.key"
        type="button"
        class="platform-filter-button"
        :class="{ 'is-selected': filters.platforms.includes(item.key) }"
        :aria-pressed="filters.platforms.includes(item.key)"
        @click="togglePlatform(item.key)"
      >
        {{ item.label }} <span>{{ item.count }}</span>
      </button>
    </div>

    <div v-if="activeFilterLabels.length" class="active-filters" aria-label="当前语义筛选">
      <span class="toolbar-label">当前筛选</span>
      <button
        v-for="item in activeFilterLabels"
        :key="item.field"
        class="active-filter"
        type="button"
        :aria-label="`移除筛选 ${item.label}`"
        @click="clearFilter(item.field)"
      >
        {{ item.label }} <CloseOutlined />
      </button>
    </div>

    <div class="semantic-overview-grid">
      <section class="workbench-section keyword-section" aria-labelledby="keyword-cloud-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">关键词概览</span>
            <h3 id="keyword-cloud-title">关键词词云</h3>
          </div>
          <span>{{ keywordCloud.length }} 个词</span>
        </div>
        <SemanticKeywordCloud
          v-if="keywordCloud.length"
          :items="keywordCloud"
          :selected-term="filters.keyword"
          @select="(term) => toggleSingle('keyword', term)"
        />
        <a-empty v-else description="当前筛选条件下暂无关键词" :image-style="{ height: '34px' }" />
      </section>

      <section class="workbench-section distribution-section" aria-labelledby="distribution-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">态度分布</span>
            <h3 id="distribution-title">情感与立场</h3>
          </div>
          <span>{{ filteredRecords.length }} 条内容</span>
        </div>
        <div class="distribution-group">
          <div class="distribution-title">情感</div>
          <div
            class="distribution-donut"
            role="img"
            :aria-label="distributionAriaLabel('情感', sentimentCounts)"
            :style="{ background: donutBackground('sentiment', sentimentCounts) }"
          >
            <div class="distribution-donut-hole">
              <strong>{{ distributionTotal(sentimentCounts) }}</strong>
              <span>条内容</span>
            </div>
          </div>
          <div class="distribution-legend">
            <button
              v-for="item in sentimentCounts"
              :key="item.key"
              type="button"
              class="distribution-legend-button"
              :class="{ 'is-selected': filters.sentiment === item.key }"
              :aria-pressed="filters.sentiment === item.key"
              @click="toggleSingle('sentiment', item.key)"
            >
              <span class="legend-dot" :class="sentimentClass(item.key)" />
              {{ displaySemanticLabel('sentiment', item.label) }} {{ formatDistributionPercent(item.count, distributionTotal(sentimentCounts)) }}% <span>{{ item.count }}</span>
            </button>
          </div>
        </div>
        <div class="distribution-group">
          <div class="distribution-title">立场（相对核心主张）</div>
          <div
            class="distribution-donut"
            role="img"
            :aria-label="distributionAriaLabel('立场', stanceCounts)"
            :style="{ background: donutBackground('stance', stanceCounts) }"
          >
            <div class="distribution-donut-hole">
              <strong>{{ distributionTotal(stanceCounts) }}</strong>
              <span>条内容</span>
            </div>
          </div>
          <div class="distribution-legend">
            <button
              v-for="item in stanceCounts"
              :key="item.key"
              type="button"
              class="distribution-legend-button"
              :class="{ 'is-selected': filters.stance === item.key }"
              :aria-pressed="filters.stance === item.key"
              @click="toggleSingle('stance', item.key)"
            >
              <span class="legend-dot" :class="stanceClass(item.key)" />
              {{ displaySemanticLabel('stance', item.label) }} {{ formatDistributionPercent(item.count, distributionTotal(stanceCounts)) }}% <span>{{ item.count }}</span>
            </button>
          </div>
        </div>
      </section>
    </div>

    <div class="semantic-analysis-grid semantic-ledger-grid">
      <section class="workbench-section" aria-labelledby="topic-rail-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">语义聚类</span>
            <h3 id="topic-rail-title">主题轨道</h3>
          </div>
          <span>按内容量排序</span>
        </div>
        <div v-if="topicCounts.length" class="facet-rail">
          <button
            v-for="item in topicCounts.slice(0, 8)"
            :key="item.key"
            class="facet-rail-row topic-row"
            :class="{ 'is-selected': filters.topic === item.key }"
            type="button"
            :aria-pressed="filters.topic === item.key"
            @click="toggleSingle('topic', item.key)"
          >
            <span class="facet-label">{{ item.label }}</span>
            <span class="facet-track"><span :style="{ width: `${percentage(item.count, topicCounts)}%` }" /></span>
            <strong>{{ item.count }}</strong>
          </button>
        </div>
        <a-empty v-else description="当前筛选条件下暂无主题" :image-style="{ height: '34px' }" />
      </section>

      <section class="workbench-section" aria-labelledby="entity-ledger-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">命名实体</span>
            <h3 id="entity-ledger-title">实体清单</h3>
          </div>
          <span>按类型分组</span>
        </div>
        <div v-if="entityGroups.length" class="entity-groups">
          <div v-for="group in entityGroups" :key="group.label" class="entity-group">
            <span class="entity-type">{{ entityTypeLabel(group.label) }}</span>
            <button
              v-for="item in group.items.slice(0, 5)"
              :key="item.key"
              class="entity-row"
              :class="{ 'is-selected': filters.entity === item.key }"
              type="button"
              :aria-pressed="filters.entity === item.key"
              @click="toggleSingle('entity', item.key)"
            >
              <span class="entity-row-label">{{ item.label }}</span>
              <span class="entity-row-metric">
                <span class="entity-frequency-track"><span :style="{ width: `${percentage(item.count, group.items)}%` }" /></span>
                <strong>{{ item.count }}</strong>
              </span>
            </button>
          </div>
        </div>
        <a-empty v-else description="当前筛选条件下暂无实体" :image-style="{ height: '34px' }" />
      </section>
    </div>

    <div class="semantic-analysis-grid timeline-platform-grid">
      <section class="workbench-section" aria-labelledby="time-strip-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">时间变化</span>
            <h3 id="time-strip-title">内容时间条带</h3>
          </div>
          <span>点击日期筛选</span>
        </div>
        <div v-if="timeCounts.length" class="time-strip">
          <button
            v-for="item in timeCounts"
            :key="item.key"
            type="button"
            class="time-column"
            :class="{ 'is-selected': filters.date === item.key }"
            :aria-pressed="filters.date === item.key"
            :aria-label="`${item.label}，${item.count} 条内容`"
            @click="toggleSingle('date', item.key)"
          >
            <span class="time-bar" :style="{ height: `${percentage(item.count, timeCounts)}%` }" />
            <span>{{ shortDate(item.label) }}</span>
          </button>
        </div>
        <a-empty v-else description="当前筛选条件下暂无时间切片" :image-style="{ height: '34px' }" />
      </section>

      <section class="workbench-section" aria-labelledby="platform-compare-title">
        <div class="section-heading">
          <div>
            <span class="section-kicker">跨平台比较</span>
            <h3 id="platform-compare-title">平台情感分布</h3>
          </div>
          <span>可多选</span>
        </div>
        <div v-if="platformRows.length" class="platform-comparison">
          <button
            v-for="item in platformRows"
            :key="item.key"
            type="button"
            class="platform-row"
            :class="{ 'is-selected': filters.platforms.includes(item.key) }"
            :aria-pressed="filters.platforms.includes(item.key)"
            @click="togglePlatform(item.key)"
          >
            <span class="platform-row-label">{{ item.label }} <strong>{{ item.count }}</strong></span>
            <span class="stacked-bar platform-stacked">
              <span
                v-for="segment in item.sentiment"
                :key="segment.key"
                class="stacked-segment"
                :class="sentimentClass(segment.key)"
                :style="{ width: `${percentage(segment.count, item.sentiment)}%` }"
              />
            </span>
          </button>
        </div>
        <a-empty v-else description="当前筛选条件下暂无平台内容" :image-style="{ height: '34px' }" />
      </section>
    </div>

    <section class="workbench-section community-section" aria-labelledby="community-summary-title">
      <div class="section-heading">
        <div>
          <span class="section-kicker">协调群体</span>
          <h3 id="community-summary-title">协同群体语义比较</h3>
        </div>
        <span>仅比较，不参与筛选</span>
      </div>
      <div v-if="communities.length" class="community-table">
        <div v-for="item in communities.slice(0, 6)" :key="item.communityId" class="community-row">
          <strong>{{ item.communityId }}</strong>
          <span>{{ item.memberCount }} 成员 · {{ item.itemCount }} 内容</span>
          <span>情感：{{ distributionText('sentiment', item.sentiment) }}</span>
          <span>立场：{{ distributionText('stance', item.stance) }}</span>
          <span>关键词：{{ namedCountsText(item.keywords) }}</span>
        </div>
      </div>
      <a-empty v-else description="当前语义结果未包含可比较的协同群体" :image-style="{ height: '34px' }" />
    </section>

    <section class="workbench-section semantic-matrix-section" aria-labelledby="semantic-matrix-title">
      <div class="section-heading matrix-heading">
        <div>
          <span class="section-kicker">可核验内容</span>
          <h3 id="semantic-matrix-title">帖子与评论语义矩阵</h3>
        </div>
        <span>{{ pageData.total }} 条匹配内容</span>
      </div>
      <div v-if="pageData.total" class="semantic-matrix-scroll">
        <table class="semantic-matrix-table">
          <thead>
            <tr>
              <th>类型</th>
              <th>平台</th>
              <th>时间</th>
              <th>关键词</th>
              <th>主题</th>
              <th>情感</th>
              <th>立场</th>
              <th>实体</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pageData.items" :key="`${item.layer}:${item.id}`">
              <td data-label="类型">{{ item.layer === 'posts' ? '主帖' : '评论' }}</td>
              <td data-label="平台">{{ item.platform }}</td>
              <td data-label="时间">{{ item.timestamp }}</td>
              <td data-label="关键词">
                <span v-for="keyword in item.keywords" :key="keyword" :class="{ 'is-evidence-match': filters.keyword === keyword }">
                  {{ keyword }}
                </span>
              </td>
              <td data-label="主题">
                <span v-for="topic in item.topics" :key="topic" :class="{ 'is-evidence-match': filters.topic === topic }">
                  {{ topic }}
                </span>
              </td>
              <td data-label="情感">{{ displaySemanticLabel('sentiment', item.sentiment) }}</td>
              <td data-label="立场">{{ displaySemanticLabel('stance', item.stance) }}</td>
              <td data-label="实体">
                <span
                  v-for="entity in item.entities"
                  :key="entity.key"
                  :class="{ 'is-evidence-match': filters.entity === entity.key }"
                >
                  {{ entity.text }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <a-empty v-else description="没有内容符合当前语义筛选" :image-style="{ height: '42px' }" />
      <a-pagination
        v-if="pageData.total > PAGE_SIZE"
        class="matrix-pagination"
        :current="pageData.page"
        :page-size="PAGE_SIZE"
        :total="pageData.total"
        :show-size-changer="false"
        size="small"
        @change="(page: number) => currentPage = page"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ClearOutlined, CloseOutlined } from '@ant-design/icons-vue'
import SemanticKeywordCloud from '@/components/SemanticKeywordCloud.vue'
import {
  buildDistribution,
  buildEntityCounts,
  buildKeywordCloud,
  buildPlatformCounts,
  buildTimeCounts,
  buildTopicCounts,
  createSemanticFilters,
  displaySemanticLabel,
  entityTypeFromKey,
  filterSemanticRecords,
  formatDistributionPercent,
  paginateSemanticRecords,
  toCommunitySummaries,
  toSemanticRecords,
  type SemanticCount,
  type SemanticFilters,
} from '@/features/semantic-evidence/model'

const PAGE_SIZE = 20

const props = defineProps<{
  evidence: Record<string, unknown> | null
}>()

type SingleFilter = Exclude<keyof SemanticFilters, 'layer' | 'platforms'>
type EntityGroup = { label: string; items: SemanticCount[] }

const filters = reactive(createSemanticFilters())
const currentPage = ref(1)
const layerOptions = [
  { label: '全部', value: 'all' },
  { label: '主帖', value: 'posts' },
  { label: '评论', value: 'comments' },
]

const evidencePayload = computed<Record<string, unknown>>(() => props.evidence || {})
const records = computed(() => toSemanticRecords(evidencePayload.value))
const filteredRecords = computed(() => filterSemanticRecords(records.value, filters))
const keywordCloud = computed(() => buildKeywordCloud(recordsWithout('keyword')))
const topicCounts = computed(() => buildTopicCounts(recordsWithout('topic')))
const sentimentCounts = computed(() => buildDistribution(recordsWithout('sentiment'), 'sentiment'))
const stanceCounts = computed(() => buildDistribution(recordsWithout('stance'), 'stance'))
const entityCounts = computed(() => buildEntityCounts(recordsWithout('entity')))
const timeCounts = computed(() => buildTimeCounts(recordsWithout('date')))
const platformRows = computed(() => {
  const base = recordsWithout('platforms')
  return buildPlatformCounts(base).map((item) => ({
    ...item,
    sentiment: buildDistribution(base.filter((record) => record.platform === item.key), 'sentiment'),
  }))
})
const communities = computed(() => toCommunitySummaries(evidencePayload.value))
const pageData = computed(() => paginateSemanticRecords(filteredRecords.value, currentPage.value, PAGE_SIZE))
const entityGroups = computed<EntityGroup[]>(() => {
  const groups = new Map<string, SemanticCount[]>()
  for (const entity of entityCounts.value) {
    const label = entityTypeFromKey(entity.key)
    groups.set(label, [...(groups.get(label) || []), entity])
  }
  return [...groups.entries()]
    .map(([label, items]) => ({ label, items }))
    .sort((left, right) => entityTypeLabel(left.label).localeCompare(entityTypeLabel(right.label), 'zh-CN'))
})
const hasActiveFilters = computed(() => {
  const initial = createSemanticFilters()
  return filters.layer !== initial.layer
    || filters.platforms.length > 0
    || filters.date !== null
    || filters.keyword !== null
    || filters.topic !== null
    || filters.sentiment !== null
    || filters.stance !== null
    || filters.entity !== null
})
const activeFilterLabels = computed(() => {
  const labels: Array<{ field: keyof SemanticFilters; label: string }> = []
  if (filters.layer !== 'all') labels.push({ field: 'layer', label: filters.layer === 'posts' ? '主帖' : '评论' })
  if (filters.platforms.length) labels.push({ field: 'platforms', label: `平台：${filters.platforms.join('、')}` })
  if (filters.date) labels.push({ field: 'date', label: `日期：${filters.date}` })
  if (filters.keyword) labels.push({ field: 'keyword', label: `关键词：${filters.keyword}` })
  if (filters.topic) labels.push({ field: 'topic', label: `主题：${filters.topic}` })
  if (filters.sentiment) labels.push({ field: 'sentiment', label: `情感：${displaySemanticLabel('sentiment', filters.sentiment)}` })
  if (filters.stance) labels.push({ field: 'stance', label: `立场：${displaySemanticLabel('stance', filters.stance)}` })
  if (filters.entity) labels.push({ field: 'entity', label: `实体：${filters.entity.split(':').slice(1).join(':')}` })
  return labels
})

watch(filters, () => {
  currentPage.value = 1
}, { deep: true })

watch(() => props.evidence, () => {
  resetFilters()
})

watch(pageData, (value) => {
  if (value.page !== currentPage.value) currentPage.value = value.page
})

function recordsWithout(field: keyof SemanticFilters) {
  const context = {
    ...filters,
    [field]: field === 'platforms' ? [] : field === 'layer' ? 'all' : null,
  } as SemanticFilters
  return filterSemanticRecords(records.value, context)
}

function toggleSingle(field: SingleFilter, value: string | null) {
  filters[field] = filters[field] === value ? null : value
}

function togglePlatform(platform: string) {
  filters.platforms = filters.platforms.includes(platform)
    ? filters.platforms.filter((item) => item !== platform)
    : [...filters.platforms, platform]
}

function clearFilter(field: keyof SemanticFilters) {
  if (field === 'layer') {
    filters.layer = 'all'
    return
  }
  if (field === 'platforms') {
    filters.platforms = []
    return
  }
  filters[field] = null
}

function resetFilters() {
  Object.assign(filters, createSemanticFilters())
  currentPage.value = 1
}

function percentage(count: number, items: SemanticCount[]): number {
  const total = items.reduce((sum, item) => sum + item.count, 0)
  return total > 0 ? Math.max(1, Math.round((count / total) * 100)) : 0
}

function distributionAriaLabel(label: string, items: SemanticCount[]): string {
  const field = label === '情感' ? 'sentiment' : 'stance'
  return `${label}分布：${items.map((item) => `${displaySemanticLabel(field, item.label)} ${item.count} 条`).join('，') || '暂无'}`
}

function distributionTotal(items: SemanticCount[]): number {
  return items.reduce((sum, item) => sum + item.count, 0)
}

function donutBackground(field: 'sentiment' | 'stance', items: SemanticCount[]): string {
  const total = distributionTotal(items)
  if (!total) return '#e8edf1'
  let cursor = 0
  const stops = items.map((item) => {
    const start = cursor
    cursor += (item.count / total) * 100
    return `${donutColor(field, item.key)} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`
  })
  return `conic-gradient(${stops.join(', ')})`
}

function donutColor(field: 'sentiment' | 'stance', value: string): string {
  if (field === 'sentiment') {
    if (value.toLowerCase() === 'positive') return '#27825a'
    if (value.toLowerCase() === 'negative') return '#bd4b45'
    return '#86909c'
  }
  if (value.toLowerCase() === 'entailment') return '#326fba'
  if (value.toLowerCase() === 'contradiction') return '#c97521'
  return '#86909c'
}

function sentimentClass(value: string): string {
  const normalized = value.toLowerCase()
  if (normalized === 'positive') return 'is-positive'
  if (normalized === 'negative') return 'is-negative'
  return 'is-neutral'
}

function stanceClass(value: string): string {
  const normalized = value.toLowerCase()
  if (normalized === 'entailment') return 'is-entailment'
  if (normalized === 'contradiction') return 'is-contradiction'
  return 'is-neutral'
}

function entityTypeLabel(value: string): string {
  const labels: Record<string, string> = { PER: '人物', ORG: '组织', LOC: '地点', OTHER: '其他' }
  return labels[value] || value
}

function shortDate(value: string): string {
  return value.length >= 10 ? value.slice(5) : value
}

function distributionText(field: 'sentiment' | 'stance', value: Record<string, number>): string {
  return Object.entries(value)
    .map(([label, count]) => `${displaySemanticLabel(field, label)} ${count}`)
    .join('，') || '暂无'
}

function namedCountsText(items: SemanticCount[]): string {
  return items.slice(0, 3).map((item) => `${item.label} ${item.count}`).join('，') || '暂无'
}
</script>

<style scoped>
.semantic-workbench {
  color: #1f2329;
  font-variant-numeric: tabular-nums;
  min-width: 0;
}

.workbench-toolbar,
.toolbar-scope,
.platform-filter,
.active-filters,
.section-heading,
.distribution-legend,
.matrix-heading {
  align-items: center;
  display: flex;
}

.workbench-toolbar {
  justify-content: space-between;
  margin-bottom: 10px;
}

.toolbar-scope,
.platform-filter,
.active-filters {
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-label,
.section-kicker,
.section-heading > span {
  color: #6b7785;
  font-size: 14px;
}

.platform-filter {
  margin-bottom: 10px;
}

.platform-filter-button,
.active-filter {
  background: transparent;
  border: 1px solid #d7dde5;
  border-radius: 4px;
  color: #455564;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  min-height: 28px;
  padding: 3px 8px;
}

.platform-filter-button span {
  color: #7b8794;
  margin-left: 3px;
}

.platform-filter-button.is-selected,
.active-filter {
  border-color: #1769aa;
  color: #0f4f84;
}

.active-filters {
  border-bottom: 1px solid #e7ebef;
  margin-bottom: 18px;
  padding-bottom: 12px;
}

.active-filter {
  align-items: center;
  display: inline-flex;
  gap: 4px;
}

.semantic-overview-grid,
.semantic-analysis-grid {
  display: grid;
  gap: 22px;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
}

.semantic-analysis-grid {
  border-top: 1px solid #e7ebef;
  margin-top: 22px;
  padding-top: 22px;
}

.semantic-ledger-grid {
  grid-template-columns: minmax(0, 1fr);
}

.timeline-platform-grid {
  grid-template-columns: minmax(0, 1fr) minmax(320px, 1fr);
}

.workbench-section {
  min-width: 0;
}

.section-heading {
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-heading h3 {
  color: #1f2933;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  margin: 0;
}

.section-kicker {
  display: block;
  margin-bottom: 2px;
}

.distribution-group + .distribution-group {
  margin-top: 16px;
}

.distribution-group {
  align-items: center;
  column-gap: 16px;
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  row-gap: 8px;
}

.distribution-title {
  color: #4e5969;
  font-size: 13px;
  font-weight: 600;
  grid-column: 1 / -1;
}

.distribution-donut {
  align-items: center;
  border-radius: 50%;
  display: flex;
  height: 132px;
  justify-content: center;
  width: 132px;
}

.distribution-donut-hole {
  align-items: center;
  background: #fff;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  height: 78px;
  justify-content: center;
  width: 78px;
}

.distribution-donut-hole strong {
  color: #1f2933;
  font-size: 18px;
  line-height: 1.2;
}

.distribution-donut-hole span {
  color: #86909c;
  font-size: 12px;
  margin-top: 2px;
}

.stacked-bar {
  background: #edf1f4;
  display: flex;
  height: 10px;
  overflow: hidden;
  width: 100%;
}

.stacked-segment,
.legend-dot {
  background: #86909c;
}

.stacked-segment.is-positive,
.legend-dot.is-positive { background: #27825a; }
.stacked-segment.is-negative,
.legend-dot.is-negative { background: #bd4b45; }
.stacked-segment.is-entailment,
.legend-dot.is-entailment { background: #326fba; }
.stacked-segment.is-contradiction,
.legend-dot.is-contradiction { background: #c97521; }

.distribution-legend {
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 0;
}

.distribution-legend-button {
  align-items: center;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: #4e5969;
  cursor: pointer;
  display: inline-flex;
  font: inherit;
  font-size: 13px;
  gap: 4px;
  padding: 2px 0;
}

.distribution-legend-button.is-selected,
.distribution-legend-button:hover,
.distribution-legend-button:focus-visible {
  border-bottom-color: #1769aa;
  color: #0f4f84;
  outline: none;
}

.distribution-legend-button span:last-child {
  color: #86909c;
}

.legend-dot {
  border-radius: 50%;
  height: 8px;
  width: 8px;
}

.facet-rail {
  display: grid;
  gap: 7px;
}

.facet-rail-row,
.entity-row,
.platform-row {
  align-items: center;
  background: transparent;
  border: 0;
  color: #3d4a57;
  cursor: pointer;
  display: grid;
  font: inherit;
  min-width: 0;
  padding: 3px 0;
  text-align: left;
}

.facet-rail-row {
  gap: 8px;
  grid-template-columns: minmax(96px, 0.9fr) minmax(90px, 1.6fr) 32px;
}

.facet-rail-row.is-selected,
.entity-row.is-selected,
.platform-row.is-selected {
  color: #0f4f84;
}

.facet-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.facet-track {
  background: #e8eef5;
  height: 8px;
  overflow: hidden;
}

.facet-track span {
  background: #3e7fc0;
  display: block;
  height: 100%;
}

.entity-groups {
  display: grid;
  gap: 10px;
}

.entity-group {
  display: grid;
  gap: 4px;
}

.entity-type {
  color: #6b7785;
  font-size: 12px;
  font-weight: 600;
}

.entity-row {
  border-bottom: 1px solid #edf0f2;
  gap: 8px;
  grid-template-columns: minmax(72px, 0.85fr) minmax(82px, 1.15fr);
  width: 100%;
}

.entity-row-label {
  min-width: 0;
  overflow-wrap: anywhere;
}

.entity-row-metric {
  align-items: center;
  display: grid;
  gap: 7px;
  grid-template-columns: minmax(42px, 1fr) auto;
  min-width: 0;
  text-align: right;
}

.entity-frequency-track {
  background: #e8eef5;
  height: 7px;
  min-width: 0;
  overflow: hidden;
}

.entity-frequency-track span {
  background: #5b8fc4;
  display: block;
  height: 100%;
}

.time-strip {
  align-items: end;
  display: flex;
  gap: 5px;
  min-height: 128px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.time-column {
  align-items: center;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  color: #6b7785;
  cursor: pointer;
  display: flex;
  flex: 0 0 34px;
  flex-direction: column;
  font: inherit;
  font-size: 12px;
  gap: 5px;
  height: 124px;
  justify-content: end;
  padding: 0;
}

.time-column.is-selected,
.time-column:hover,
.time-column:focus-visible {
  border-bottom-color: #1769aa;
  color: #0f4f84;
  outline: none;
}

.time-bar {
  background: #4d92cb;
  min-height: 3px;
  width: 18px;
}

.platform-comparison {
  display: grid;
  gap: 9px;
}

.platform-row {
  gap: 9px;
  grid-template-columns: minmax(88px, 0.8fr) minmax(100px, 2fr);
}

.platform-row-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-row-label strong {
  color: #6b7785;
  font-weight: 500;
}

.platform-stacked {
  height: 9px;
}

.community-section,
.semantic-matrix-section {
  border-top: 1px solid #e7ebef;
  margin-top: 22px;
  padding-top: 22px;
}

.community-table {
  display: grid;
  gap: 0;
}

.community-row {
  align-items: baseline;
  border-bottom: 1px solid #edf0f2;
  display: grid;
  font-size: 12px;
  gap: 8px 16px;
  grid-template-columns: minmax(96px, 0.7fr) minmax(126px, 1fr) minmax(128px, 1fr) minmax(148px, 1.2fr) minmax(180px, 1.4fr);
  padding: 8px 0;
}

.community-row span {
  color: #657484;
}

.semantic-matrix-scroll {
  overflow-x: auto;
}

.semantic-matrix-table {
  border-collapse: collapse;
  font-size: 13px;
  min-width: 900px;
  width: 100%;
}

.semantic-matrix-table th,
.semantic-matrix-table td {
  border: 1px solid #edf0f2;
  line-height: 1.55;
  padding: 8px;
  text-align: left;
  vertical-align: top;
  word-break: break-word;
}

.semantic-matrix-table th {
  background: #f7f9fb;
  color: #4e5969;
  font-weight: 600;
  white-space: nowrap;
}

.semantic-matrix-table td span + span::before {
  color: #a1a8b0;
  content: '、';
}

.is-evidence-match {
  background: #fff3cd;
  color: #784b00;
  font-weight: 600;
}

.matrix-pagination {
  margin-top: 12px;
  text-align: right;
}

@media (max-width: 960px) {
  .semantic-overview-grid,
  .semantic-analysis-grid,
  .timeline-platform-grid {
    grid-template-columns: 1fr;
  }

  .community-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .workbench-toolbar,
  .section-heading,
  .matrix-heading {
    align-items: flex-start;
    gap: 8px;
  }

  .toolbar-scope {
    flex: 1 1 216px;
  }

  .section-heading > span {
    flex: 0 1 auto;
    text-align: right;
  }

  .platform-filter-button,
  .active-filter {
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  .distribution-group {
    column-gap: 12px;
    grid-template-columns: 104px minmax(0, 1fr);
  }

  .distribution-donut {
    height: 104px;
    width: 104px;
  }

  .distribution-donut-hole {
    height: 62px;
    width: 62px;
  }

  .distribution-donut-hole strong {
    font-size: 15px;
  }

  .community-row {
    grid-template-columns: 1fr;
  }

  .facet-rail-row {
    grid-template-columns: minmax(78px, 0.9fr) minmax(72px, 1.4fr) 28px;
  }

  .facet-label {
    overflow: visible;
    text-overflow: clip;
    white-space: normal;
  }

  .entity-row {
    grid-template-columns: minmax(0, 1fr) minmax(104px, 1.1fr);
  }

  .platform-row {
    grid-template-columns: minmax(92px, 0.9fr) minmax(96px, 1.4fr);
  }

  .matrix-pagination {
    overflow-x: auto;
    text-align: left;
  }

  .semantic-matrix-scroll {
    overflow-x: visible;
  }

  .semantic-matrix-table {
    display: block;
    min-width: 0;
  }

  .semantic-matrix-table thead {
    display: none;
  }

  .semantic-matrix-table tbody {
    display: grid;
    gap: 8px;
  }

  .semantic-matrix-table tr {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: hidden;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #fff;
  }

  .semantic-matrix-table td {
    display: grid;
    gap: 2px;
    min-width: 0;
    border: 0;
    padding: 7px 8px;
  }

.semantic-matrix-table td::before {
    color: #86909c;
    content: attr(data-label);
    font-size: 12px;
    font-weight: 600;
    line-height: 1.3;
  }

  .semantic-matrix-table td:nth-child(3),
  .semantic-matrix-table td:nth-child(4),
  .semantic-matrix-table td:nth-child(5),
  .semantic-matrix-table td:nth-child(8) {
    grid-column: 1 / -1;
  }
}
</style>
