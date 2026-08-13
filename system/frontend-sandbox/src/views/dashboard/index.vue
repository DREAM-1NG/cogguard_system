<template>
  <div class="dashboard-page">
    <PageHeader title="数据大屏" description="跨平台事件态势、采集规模、风险与地理位置概览" />

    <div class="toolbar">
      <a-select
        v-model:value="eventId"
        class="event-input"
        show-search
        :filter-option="false"
        :options="eventOptions"
        :loading="eventSearchLoading"
        placeholder="搜索事件…"
        aria-label="搜索事件"
        @search="scheduleEventSearch"
        @change="loadOverview"
      />
      <a-button :loading="loading" aria-label="刷新数据大屏" @click="loadOverview">
        <ReloadOutlined aria-hidden="true" />
        刷新
      </a-button>
      <a-button type="primary" :disabled="!eventId" @click="enterReview">
        进入研判
        <ArrowRightOutlined aria-hidden="true" />
      </a-button>
      <span v-if="overview?.meta.generated_at" class="generated-at">
        {{ formatTime(overview.meta.generated_at) }}
      </span>
    </div>

    <a-alert
      v-if="loadError"
      class="status-alert"
      type="warning"
      show-icon
      :message="loadError"
    />

    <a-row :gutter="[16, 16]" class="main-grid">
      <a-col :xs="24" :xl="16">
        <a-card title="事件位置地图" size="small">
          <div class="map-shell">
            <div
              ref="mapRef"
              class="map-canvas"
              role="img"
              aria-describedby="dashboard-map-summary"
            />
            <p id="dashboard-map-summary" class="sr-only">{{ mapAccessibilitySummary }}</p>
            <div class="heatmap-panel">
              <div class="heatmap-title">事件热力</div>
              <div class="heatmap-bar" />
              <div class="heatmap-scale">
                <span>低</span>
                <span>{{ heatLegendMax }}</span>
              </div>
              <div class="heatmap-note">帖子 + 评论</div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :xs="24" :xl="8" class="side-column">
        <a-card title="平台数据分布" :loading="loading" size="small">
          <a-table
            :columns="platformColumns"
            :data-source="overview?.platforms || []"
            row-key="platform"
            size="small"
            :pagination="false"
          />
          <a-empty
            v-if="!loading && !overview?.platforms.length"
            description="暂无平台数据"
            :image-style="{ height: '36px' }"
          />
        </a-card>
        <a-card title="最早发帖样本" size="small">
          <a-list
            v-if="overview?.recent_posts.length"
            :data-source="overview.recent_posts"
            size="small"
            class="recent-list side-recent-list"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="recent-item">
                  <div class="recent-meta">
                    <a-tag>{{ platformLabel(item.platform) }}</a-tag>
                    <strong>{{ item.author_name || item.author_id || '-' }}</strong>
                    <span>{{ formatTime(item.timestamp) }}</span>
                  </div>
                  <div class="recent-content">{{ item.content || '-' }}</div>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty
            v-else
            description="暂无发帖样本"
            :image-style="{ height: '36px' }"
          />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]" class="detail-grid">
      <a-col :span="24">
        <a-card title="事件定位明细" size="small">
          <a-table
            :columns="eventColumns"
            :data-source="overview?.event_locations || []"
            row-key="event_id"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'event'">
                <div class="event-cell-title">{{ record.event_name }}</div>
              </template>
              <template v-else-if="column.key === 'origin'">
                <div>{{ record.origin_author || '-' }}</div>
                <div class="event-cell-meta">
                  {{ originLocationMeta(record) }}
                </div>
              </template>
              <template v-else-if="column.key === 'location'">
                <a-tag :color="record.resolved ? 'blue' : 'orange'">{{ record.location_region }}</a-tag>
                <div class="event-cell-meta">
                  {{ record.location_resolution_method === 'origin_post' ? '首帖定位' : record.location_resolution_method === 'first_geolocated_post' ? '回退到最早可解析帖子' : '无法解析' }}
                </div>
              </template>
              <template v-else-if="column.key === 'scale'">
                <span>{{ record.posts }} 帖 / {{ record.comments }} 评</span>
              </template>
            </template>
          </a-table>
          <a-empty
            v-if="!loading && !overview?.event_locations.length"
            description="暂无事件定位"
            :image-style="{ height: '36px' }"
          />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowRightOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import * as echarts from 'echarts/core'
import { EffectScatterChart, HeatmapChart, ScatterChart } from 'echarts/charts'
import { GeoComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import type { EChartsOption } from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import { getDashboardOverview, type DashboardOverview, type EventLocation } from '@/api/dashboard'
import { searchReviewCases } from '@/api/reviewCases'
import type { ReviewCaseSummary } from '@/types/reviewCase'

const DEFAULT_EVENT_ID = 'trump_visit_2026_05_21'
const WORLD_GEOJSON_URL = new URL('../../assets/world-countries.geojson', import.meta.url).href
const router = useRouter()

echarts.use([
  HeatmapChart,
  EffectScatterChart,
  ScatterChart,
  GeoComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

const eventId = ref(DEFAULT_EVENT_ID)
const caseItems = ref<ReviewCaseSummary[]>([])
const eventSearchLoading = ref(false)
const loading = ref(false)
const loadError = ref('')
const overview = ref<DashboardOverview | null>(null)
const mapRef = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null
let worldMapPromise: Promise<void> | null = null
let eventSearchTimer: number | undefined

const eventOptions = computed(() => {
  const options = caseItems.value.map((item) => ({
    label: item.title,
    value: item.event_id,
  }))
  if (eventId.value && !options.some((item) => item.value === eventId.value)) {
    options.unshift({ label: '当前事件', value: eventId.value })
  }
  return options
})

function ensureWorldMap() {
  if (!worldMapPromise) {
    worldMapPromise = fetch(WORLD_GEOJSON_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`世界底图加载失败 (${response.status})`)
        }
        return response.json()
      })
      .then((geoJson) => {
        echarts.registerMap('cogguard-world', geoJson as any)
      })
      .catch((error) => {
        worldMapPromise = null
        throw error
      })
  }
  return worldMapPromise
}

const resolvedLocations = computed(() => (overview.value?.event_locations || []).filter((item) => item.resolved && item.coordinates))
const mapAccessibilitySummary = computed(() => {
  if (resolvedLocations.value.length === 0) {
    return '当前事件没有可解析的地理位置；完整事件数据见下方定位明细。'
  }
  const total = resolvedLocations.value.reduce((sum, item) => sum + item.posts + item.comments, 0)
  const regions = resolvedLocations.value.map((item) => item.location_region).filter(Boolean).join('、')
  return `地图显示 ${resolvedLocations.value.length} 个事件位置，覆盖 ${regions}，共 ${total} 条帖子和评论；完整数据见下方定位明细。`
})
const mapPoints = computed(() => {
  return resolvedLocations.value.map((item) => ({
    name: item.event_name,
    value: [...(item.coordinates as [number, number]), item.posts + item.comments],
    raw: item,
  }))
})

const heatLegendMax = computed(() => {
  const maxValue = Math.max(...mapPoints.value.map((point) => Number(point.value[2]) || 0), 0)
  return maxValue.toLocaleString('zh-CN')
})

const geoRegions = computed(() => {
  const count = (name: string) => resolvedLocations.value.filter((item) => item.location_country === name).length
  return [
    {
      name: 'China',
      itemStyle: { areaColor: count('China') > 0 ? '#18181B' : '#F4F4F5' },
    },
    {
      name: 'United States of America',
      itemStyle: { areaColor: count('United States of America') > 0 ? '#2563EB' : '#F4F4F5' },
    },
    {
      name: 'Japan',
      itemStyle: { areaColor: count('Japan') > 0 ? '#2563EB' : '#F4F4F5' },
    },
    {
      name: 'South Korea',
      itemStyle: { areaColor: count('South Korea') > 0 ? '#2563EB' : '#F4F4F5' },
    },
  ]
})

const platformColumns = [
  { title: '平台', dataIndex: 'platform', key: 'platform', customRender: ({ text }: { text: string }) => platformLabel(text) },
  { title: '帖子', dataIndex: 'posts', key: 'posts', align: 'right' },
  { title: '评论', dataIndex: 'comments', key: 'comments', align: 'right' },
  { title: '合计', dataIndex: 'total', key: 'total', align: 'right' },
]

const eventColumns = [
  { title: '事件', key: 'event' },
  { title: '第一发帖者', key: 'origin' },
  { title: '地图位置', key: 'location' },
  { title: '规模', key: 'scale', align: 'right' },
]

function platformLabel(platform?: string | null) {
  const labels: Record<string, string> = {
    weibo: '微博',
    xhs: '小红书',
    douyin: '抖音',
  }
  return platform ? labels[platform] || platform : '-'
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function originLocationMeta(record: EventLocation) {
  const platform = platformLabel(record.origin_platform)
  if (record.origin_ip_location) {
    return `${platform} · ${record.origin_ip_location}`
  }
  if (record.location_source_ip_location) {
    return `${platform} · 首帖无属地，回退属地：${record.location_source_ip_location}`
  }
  return `${platform} · 未解析属地`
}

function buildMapOption(points: typeof mapPoints.value): EChartsOption {
  const markerLayers = points.map((point) => ({
    name: point.name,
    value: point.value,
    raw: point.raw,
  }))
  const maxValue = Math.max(...points.map((point) => Number(point.value[2]) || 0), 1)

  return {
    backgroundColor: 'transparent',
    visualMap: {
      show: false,
      min: 0,
      max: maxValue,
      seriesIndex: 0,
      inRange: {
        color: ['#F4F4F5', '#E4E4E7', '#A1A1AA', '#71717A', '#18181B'],
      },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: '#FFFFFF',
      borderColor: '#E4E4E7',
      textStyle: {
        color: '#18181B',
      },
      extraCssText: 'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);',
      formatter: (params: any) => {
        const raw = params.data?.raw as EventLocation | undefined
        if (!raw) return params.name
        return [
          `<strong>${raw.event_name}</strong>`,
          `第一发帖者：${raw.origin_author || '-'}`,
          `平台：${platformLabel(raw.origin_platform)}`,
          `IP 属地：${raw.ip_location || '-'}`,
          `规模：${raw.posts} 帖 / ${raw.comments} 评`,
        ].join('<br/>')
      },
    },
    geo: {
      map: 'cogguard-world',
      roam: true,
      zoom: 1.06,
      center: [12, 20],
      aspectScale: 0.88,
      scaleLimit: {
        min: 0.8,
        max: 4.5,
      },
      itemStyle: {
        areaColor: '#F4F4F5',
        borderColor: '#E4E4E7',
        borderWidth: 0.8,
      },
      emphasis: {
        itemStyle: {
          areaColor: '#E4E4E7',
        },
      },
      label: {
        show: false,
        color: '#18181B',
        fontSize: 11,
      },
      regions: geoRegions.value,
    },
    series: [
      {
        name: '事件热力',
        type: 'heatmap',
        coordinateSystem: 'geo',
        data: points.map((point) => [point.value[0], point.value[1], point.value[2]]),
        pointSize: 34,
        blurSize: 58,
        silent: true,
        zlevel: 1,
        z: 1,
        itemStyle: {
          opacity: 0.98,
        },
      },
      {
        name: '事件位置光晕',
        type: 'effectScatter',
        coordinateSystem: 'geo',
        data: markerLayers,
        zlevel: 2,
        z: 2,
        rippleEffect: {
          brushType: 'stroke',
          scale: 3.4,
        },
        symbolSize: (value: number[]) => Math.max(16, Math.min(38, Math.sqrt(value[2] || 1) * 2.2)),
        itemStyle: {
          color: '#18181B',
          shadowBlur: 4,
          shadowColor: 'rgba(24, 24, 27, 0.2)',
        },
        label: {
          show: false,
        },
      },
      {
        name: '事件位置',
        type: 'scatter',
        coordinateSystem: 'geo',
        data: markerLayers,
        zlevel: 3,
        z: 3,
        symbolSize: (value: number[]) => Math.max(12, Math.min(28, Math.sqrt(value[2] || 1) * 1.8)),
        itemStyle: {
          color: '#18181B',
          borderColor: '#FFFFFF',
          borderWidth: 2,
          shadowBlur: 4,
          shadowColor: 'rgba(0, 0, 0, 0.1)',
        },
        label: {
          show: true,
          formatter: '{b}',
          position: 'right',
          color: '#18181B',
          fontSize: 12,
          fontWeight: 600,
          backgroundColor: '#FFFFFF',
          borderColor: '#E4E4E7',
          borderWidth: 1,
          borderRadius: 4,
          padding: [4, 6],
        },
      },
    ],
  }
}

async function renderMap() {
  await nextTick()
  if (!mapRef.value || mapRef.value.offsetWidth === 0 || mapRef.value.offsetHeight === 0) return
  try {
    await ensureWorldMap()
  } catch (error) {
    const detail = error instanceof Error ? error.message : '世界底图加载失败'
    loadError.value = detail
    message.warning('世界底图加载失败')
    return
  }
  if (!chart) {
    chart = echarts.init(mapRef.value)
  }
  chart.setOption(buildMapOption(mapPoints.value), true)
  chart.resize()
}

async function loadOverview() {
  loading.value = true
  loadError.value = ''
  try {
    const params = eventId.value.trim() ? { event_id: eventId.value.trim() } : undefined
    const res = await getDashboardOverview(params) as { data: DashboardOverview }
    overview.value = res.data
  } catch (error) {
    const detail = error instanceof Error ? error.message : '看板数据加载失败'
    loadError.value = `无法加载真实看板数据：${detail}`
    overview.value = null
    message.warning('监测看板数据加载失败')
  } finally {
    loading.value = false
    await renderMap()
  }
}

async function loadEventOptions(query = '') {
  eventSearchLoading.value = true
  try {
    const response = await searchReviewCases({ query, limit: 30 })
    caseItems.value = response.data.items
  } finally {
    eventSearchLoading.value = false
  }
}

function scheduleEventSearch(query: string) {
  if (eventSearchTimer) window.clearTimeout(eventSearchTimer)
  eventSearchTimer = window.setTimeout(() => {
    void loadEventOptions(query)
  }, 250)
}

function enterReview() {
  const selected = caseItems.value.find((item) => item.event_id === eventId.value)
  void router.push({
    path: '/risk',
    query: {
      event_id: eventId.value,
      ...(selected ? { case_id: selected.case_id } : {}),
    },
  })
}

function resizeChart() {
  chart?.resize()
}

watch(mapPoints, () => {
  void renderMap()
})

watch(loading, (value) => {
  if (!value) {
    void renderMap()
  }
})

onMounted(() => {
  void renderMap()
  void loadOverview()
  void loadEventOptions()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
  chart = null
  if (eventSearchTimer) window.clearTimeout(eventSearchTimer)
})
</script>

<style scoped lang="less">
.dashboard-page {
  color: inherit;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.event-input {
  width: min(420px, 100%);
}

.generated-at {
  color: #71717A;
  font-size: 12px;
}

.status-alert {
  margin-bottom: 16px;
}

.main-grid,
.detail-grid {
  margin-bottom: 16px;
}

.side-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.map-shell {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 12px;
  min-height: 460px;
  overflow: hidden;
  border-radius: 6px;
  background: #FAF9F6;
  border: 1px solid #E4E4E7;
  box-shadow: inset 0 0 0 1px #F4F4F5;
}

.map-shell::before {
  position: absolute;
  inset: 0;
  content: '';
  pointer-events: none;
  background-image:
    linear-gradient(rgba(0, 0, 0, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.04) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(circle at center, black 0%, transparent 78%);
}

.map-canvas {
  flex: 1 1 auto;
  min-width: 0;
  height: 460px;
  width: 100%;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.heatmap-panel {
  position: relative;
  align-self: flex-end;
  flex: 0 0 180px;
  width: 180px;
  height: 132px;
  padding: 8px;
  border-radius: 6px;
  background: #FFFFFF;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #E4E4E7;
  z-index: 3;
}

.heatmap-title {
  color: #18181B;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}

.heatmap-bar {
  width: 100%;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, #E4E4E7 0%, #71717A 50%, #18181B 100%);
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.06);
}

.heatmap-scale {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  color: #71717A;
  font-size: 11px;
}

.heatmap-note {
  margin-top: 6px;
  color: #71717A;
  font-size: 11px;
}

@media (max-width: 1280px) {
  .map-shell {
    flex-direction: column;
  }

  .map-canvas {
    height: 420px;
  }

  .heatmap-panel {
    flex-basis: auto;
    width: 100%;
    height: 132px;
    align-self: stretch;
  }
}

.event-cell-title {
  font-weight: 600;
}

.event-cell-meta {
  margin-top: 2px;
  color: #71717A;
  font-size: 12px;
}

.recent-list {
  max-height: 360px;
  overflow-y: auto;
}

.side-recent-list {
  max-height: 318px;
}

.recent-item {
  width: 100%;
}

.recent-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #71717A;
  font-size: 12px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.recent-content {
  color: #18181B;
  line-height: 1.6;
  word-break: break-word;
}
</style>
