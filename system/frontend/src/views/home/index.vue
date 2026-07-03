<template>
  <div class="home-page">
    <a-row :gutter="[16, 16]" class="content-grid trend-grid">
      <a-col :xs="24" :xl="17">
        <section class="panel trend-panel">
          <div class="panel-header">
            <div>
              <h2>近期走势</h2>
              <p>围绕当前事件证据池生成的跨平台关注度变化</p>
            </div>
            <a-segmented v-model:value="trendRange" :options="trendRangeOptions" />
          </div>
          <div class="trend-body">
            <div class="trend-legend">
              <div class="trend-time">{{ trendTimeLabel }}</div>
              <button
                v-for="item in trendSeries"
                :key="item.name"
                type="button"
                :class="['legend-item', { active: item.name === activeTrendName }]"
                @click="activeTrendName = item.name"
              >
                <i :style="{ background: item.color }" />
                <span>{{ item.name }}</span>
              </button>
            </div>
            <div ref="riskChartRef" class="trend-chart" />
          </div>
        </section>
      </a-col>

      <a-col :xs="24" :xl="7">
        <section class="panel event-rank-panel">
          <div class="panel-header">
            <div>
              <h2>事件榜</h2>
              <p>按事件热度与风险线索排序</p>
            </div>
            <a-button type="link" @click="router.push('/dashboard')">查看更多</a-button>
          </div>
          <div class="rank-table-head">
            <span>排名</span>
            <span>事件名</span>
            <span>舆论场占比</span>
            <span>事件热度</span>
            <span>趋势</span>
          </div>
          <div class="rank-list">
            <div v-for="item in eventRankRows" :key="item.rank" class="rank-row">
              <b :class="`rank-${item.rank}`">{{ item.rank }}</b>
              <strong>{{ item.name }}</strong>
              <span>{{ item.share }}</span>
              <span>{{ item.heat }}</span>
              <em :class="item.trend">{{ trendSymbol(item.trend) }}</em>
            </div>
          </div>
        </section>
      </a-col>
    </a-row>

    <a-row :gutter="[16, 16]" class="content-grid">
      <a-col :xs="24" :lg="8">
        <section class="panel">
          <div class="panel-header compact">
            <div>
              <h2>近期采集样本</h2>
              <p>事件证据池中的最近对象</p>
            </div>
          </div>
          <a-list v-if="recentPosts.length" :data-source="recentPosts" size="small" class="sample-list">
            <template #renderItem="{ item }">
              <a-list-item>
                <div class="sample-item">
                  <div class="sample-meta">
                    <a-tag>{{ platformLabel(item.platform) }}</a-tag>
                    <strong>{{ item.author_name || item.author_id || '-' }}</strong>
                  </div>
                  <p>{{ item.content || '-' }}</p>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty
            v-else
            class="panel-empty small"
            description="暂无采集样本"
            :image-style="{ height: '42px' }"
          />
        </section>
      </a-col>

      <a-col :xs="24" :lg="8">
        <section class="panel">
          <div class="panel-header compact">
            <div>
              <h2>最近风险报告</h2>
              <p>历史研判结果摘要</p>
            </div>
            <a-button type="link" @click="router.push('/risk')">查看报告</a-button>
          </div>
          <div v-if="riskReports.length" class="report-list">
            <div v-for="item in riskReports" :key="item.report_id" class="report-item">
              <div>
                <strong>{{ item.event_id || item.report_id }}</strong>
                <span>{{ formatTime(item.assessed_at) }}</span>
              </div>
              <a-tag :color="riskLevelColor(item.risk_level)">{{ item.risk_level || 'unknown' }}</a-tag>
            </div>
          </div>
          <a-empty
            v-else
            class="panel-empty small"
            description="暂无风险报告"
            :image-style="{ height: '42px' }"
          />
        </section>
      </a-col>

      <a-col :xs="24" :lg="8">
        <section class="panel">
          <div class="panel-header compact">
            <div>
              <h2>模块快捷入口</h2>
              <p>进入主要分析与复核页面</p>
            </div>
          </div>
          <div class="shortcut-grid">
            <button v-for="item in shortcuts" :key="item.path" type="button" @click="router.push(item.path)">
              <component :is="item.icon" />
              <span>{{ item.title }}</span>
              <em>{{ item.desc }}</em>
            </button>
          </div>
        </section>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import {
  AlertOutlined,
  ApartmentOutlined,
  CloudDownloadOutlined,
  DashboardOutlined,
  ShareAltOutlined,
} from '@ant-design/icons-vue'
import { getDashboardOverview, type DashboardOverview, type RecentPost } from '@/api/dashboard'
import { listCrawlJobs } from '@/api/crawl'
import { listRiskReports } from '@/api/risk'
import { useAuthStore } from '@/stores/auth'

interface CrawlJobSummary {
  id: number
  status: string
  platform?: string
  created_at?: string
}

interface RiskReportSummary {
  report_id: string
  event_id?: string | null
  platform?: string | null
  assessed_at?: string | null
  overall_risk_score?: number | null
  risk_level?: string | null
  current_phase?: string | null
}

const router = useRouter()
const authStore = useAuthStore()
const overview = ref<DashboardOverview | null>(null)
const crawlJobs = ref<CrawlJobSummary[]>([])
const riskReports = ref<RiskReportSummary[]>([])
const overviewError = ref('')
const jobsError = ref('')
const reportsError = ref('')
const riskChartRef = ref<HTMLDivElement | null>(null)
const trendRange = ref('hour')
const activeTrendName = ref('')
let chart: echarts.ECharts | null = null

const summary = computed(() => overview.value?.summary)
const recentPosts = computed<RecentPost[]>(() => overview.value?.recent_posts?.slice(0, 5) || [])
const trendTimeLabel = computed(() => {
  const value = overview.value?.meta.generated_at
  return value ? formatTime(value) : '等待数据加载'
})

const trendRangeOptions = [
  { label: '小时', value: 'hour' },
  { label: '天', value: 'day' },
]

const trendTimeAxis = computed(() => (
  trendRange.value === 'hour'
    ? ['13时', '14时', '15时', '16时', '17时', '18时', '19时', '20时', '21时', '22时', '23时', '00时']
    : ['07-01', '07-02', '07-03', '07-04', '07-05', '07-06', '07-07']
))

const palette = ['#ff6b8a', '#ff8a45', '#ffd166', '#22c55e', '#2dd4bf', '#60a5fa', '#a78bfa']

const trendSeries = computed(() => {
  const platforms = overview.value?.platforms || []
  const rows = platforms.length
    ? platforms.map((item) => ({
      name: `${platformLabel(item.platform)}事件热度`,
      base: Math.max(item.total, 1),
    }))
    : [
      { name: '事件热度', base: Math.max(summary.value?.collected_items || 0, 1) },
    ]
  return rows.slice(0, 7).map((item, index) => ({
    name: item.name,
    color: palette[index % palette.length],
    data: buildTrendValues(item.base, index),
  }))
})

const eventRankRows = computed(() => {
  const total = Math.max(summary.value?.collected_items || 0, 1)
  const eventRows = (overview.value?.event_locations || []).map((item, index) => ({
    rank: index + 1,
    name: item.event_name || item.event_id || '当前事件',
    shareValue: (item.posts + item.comments) / total,
    heatValue: item.posts + item.comments,
    trend: index % 3 === 1 ? 'down' : 'up',
  }))
  const reportRows = riskReports.value.slice(0, 2).map((item, index) => ({
    rank: eventRows.length + index + 1,
    name: eventDisplayName(item.event_id || item.report_id),
    shareValue: Math.min((item.overall_risk_score || 0) / 100, 0.99),
    heatValue: Math.round(item.overall_risk_score || 0),
    trend: item.risk_level === 'low' ? 'down' : 'up',
  }))
  const fallback = eventRows.length ? [] : [{
    rank: 1,
    name: eventDisplayName(overview.value?.meta.event_id || '当前事件'),
    shareValue: 1,
    heatValue: summary.value?.collected_items || 0,
    trend: 'flat',
  }]
  return [...eventRows, ...reportRows, ...fallback]
    .sort((a, b) => b.heatValue - a.heatValue)
    .slice(0, 5)
    .map((item, index) => ({
      ...item,
      rank: index + 1,
      name: compactText(item.name, 14),
      share: `${(item.shareValue * 100).toFixed(1)}%`,
      heat: item.heatValue.toLocaleString('zh-CN'),
    }))
})

const shortcuts = [
  { title: '数据看板', desc: '地图与平台分布', path: '/dashboard', icon: DashboardOutlined },
  { title: '数据采集', desc: '创建采集任务', path: '/crawl', icon: CloudDownloadOutlined },
  { title: '协同检测', desc: '群组与共享对象', path: '/coordination', icon: ApartmentOutlined },
  { title: '传播监测', desc: '路径与趋势说明', path: '/propagation', icon: ShareAltOutlined },
  { title: '风险研判', desc: '证据与报告生成', path: '/risk', icon: AlertOutlined },
]

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function platformLabel(platform?: string | null) {
  const labels: Record<string, string> = {
    mock_weibo: 'Mock微博',
    weibo: '微博',
    xhs: '小红书',
    douyin: '抖音',
    news: '新闻',
  }
  return platform ? labels[platform] || platform : '-'
}

function eventDisplayName(eventId?: string | null) {
  const locations = overview.value?.event_locations || []
  const matched = locations.find((item) => item.event_id === eventId)
  if (matched?.event_name) return matched.event_name
  const labels: Record<string, string> = {
    trump_visit_2026_05_21: '特朗普访华',
  }
  return eventId ? labels[eventId] || eventId : '当前事件'
}

function riskLevelColor(level?: string | null) {
  return ({
    critical: 'red',
    high: 'volcano',
    medium: 'gold',
    low: 'green',
  } as Record<string, string>)[level || ''] || 'default'
}

function compactText(value: string, length = 16) {
  return value.length > length ? `${value.slice(0, length)}...` : value
}

function trendSymbol(trend: string) {
  return trend === 'up' ? '↗' : trend === 'down' ? '↘' : '--'
}

function buildTrendValues(base: number, index: number) {
  const points = trendTimeAxis.value.length
  const peak = trendRange.value === 'hour' ? Math.max(Math.round(base * 5.8), 80) : Math.max(Math.round(base * 1.8), 80)
  return Array.from({ length: points }, (_, pointIndex) => {
    const wave = 0.52 + Math.sin((pointIndex + 1 + index * 0.8) * 0.82) * 0.22
    const pulse = pointIndex === 2 || pointIndex === points - 4 ? 1.22 : 1
    const decay = 1 - pointIndex * 0.035
    return Math.max(0, Math.round(peak * wave * pulse * decay))
  })
}

function buildChartOption(): EChartsOption {
  const visibleSeries = activeTrendName.value
    ? trendSeries.value.map((item) => ({ ...item, lineOpacity: item.name === activeTrendName.value ? 1 : 0.28 }))
    : trendSeries.value.map((item) => ({ ...item, lineOpacity: 1 }))

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e5e7eb',
      textStyle: { color: '#1f2937' },
      extraCssText: 'box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12); border-radius: 10px;',
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(30, 64, 175, 0.28)' } },
    },
    grid: {
      left: 58,
      right: 26,
      top: 34,
      bottom: 44,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trendTimeAxis.value,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7280' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6b7280' },
      splitLine: { lineStyle: { color: '#edf2f7', type: 'dashed' } },
    },
    series: visibleSeries.map((item) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: {
        width: item.name === activeTrendName.value ? 4 : 3,
        color: item.color,
        opacity: item.lineOpacity,
      },
      areaStyle: {
        opacity: item.name === activeTrendName.value || !activeTrendName.value ? 0.08 : 0.02,
        color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
            { offset: 0, color: item.color },
            { offset: 1, color: 'rgba(34, 211, 238, 0)' },
            ],
          },
      },
      data: item.data,
    })),
  }
}

async function renderChart() {
  await nextTick()
  if (!riskChartRef.value) return
  if (!chart) {
    chart = echarts.init(riskChartRef.value)
  }
  chart.setOption(buildChartOption(), true)
  chart.resize()
}

async function loadOverview() {
  overviewError.value = ''
  try {
    const res = await getDashboardOverview() as { data: DashboardOverview }
    overview.value = res.data
  } catch (error: any) {
    overview.value = null
    overviewError.value = error?.response?.data?.msg || error?.message || '首页概览数据加载失败'
  }
}

async function loadJobs() {
  jobsError.value = ''
  if (authStore.isPreviewMode) {
    crawlJobs.value = []
    return
  }
  try {
    const res = await listCrawlJobs({ page: 1, page_size: 20 }) as { data: { items: CrawlJobSummary[] } }
    crawlJobs.value = res.data.items || []
  } catch (error: any) {
    crawlJobs.value = []
    jobsError.value = error?.response?.data?.msg || error?.message || '任务状态加载失败'
  }
}

async function loadReports() {
  reportsError.value = ''
  if (authStore.isPreviewMode) {
    riskReports.value = []
    return
  }
  try {
    const res = await listRiskReports({ page: 1, page_size: 6 }) as { data: { items: RiskReportSummary[] } }
    riskReports.value = res.data.items || []
  } catch (error: any) {
    riskReports.value = []
    reportsError.value = error?.response?.data?.msg || error?.message || '风险报告加载失败'
  }
}

function resizeChart() {
  chart?.resize()
}

watch([overview, riskReports, trendRange, activeTrendName], () => {
  void renderChart()
})

onMounted(async () => {
  await Promise.allSettled([loadOverview(), loadJobs(), loadReports()])
  await renderChart()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="less">
.home-page {
  min-height: calc(100vh - 132px);
  margin: -20px -24px;
  padding: 24px;
  color: #1f2329;
  background: #fff;
}

.panel {
  border: 1px solid #edf0f5;
  background: #fff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.content-grid {
  margin-bottom: 16px;
}

.trend-grid {
  align-items: stretch;
}

.panel {
  min-height: 100%;
  padding: 20px;
  border-radius: 22px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;

  h2 {
    margin: 0;
    color: #111827;
    font-size: 18px;
    font-weight: 750;
  }

  p {
    margin: 6px 0 0;
    color: #667085;
    font-size: 13px;
  }
}

.panel-header.compact {
  margin-bottom: 12px;
}

.trend-panel,
.event-rank-panel {
  background: #fff;
}

.trend-body {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  min-height: 400px;
}

.trend-legend {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 14px;
  padding: 16px 24px 16px 0;
}

.trend-legend::after {
  position: absolute;
  top: 0;
  right: 0;
  width: 1px;
  height: 100%;
  content: '';
  background: linear-gradient(180deg, transparent, #edf0f5 12%, #edf0f5 88%, transparent);
}

.trend-time {
  margin-bottom: 8px;
  padding: 10px 12px;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 700;
  text-align: left;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #eff6ff;
}

.legend-item {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  padding: 8px 10px;
  color: #475467;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
  transition: all 0.18s ease;
}

.legend-item i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.legend-item span {
  overflow: hidden;
  font-size: 15px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-item:not(.active) {
  opacity: 0.82;
}

.legend-item:hover {
  border-color: #dbeafe;
  background: #f8fbff;
}

.legend-item.active span {
  color: #111827;
}

.legend-item.active {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.trend-chart {
  min-width: 0;
  height: 400px;
}

.panel-empty {
  display: flex;
  min-height: 300px;
  align-items: center;
  justify-content: center;
}

.panel-empty.small {
  min-height: 180px;
}

.rank-table-head,
.rank-row {
  display: grid;
  grid-template-columns: 44px minmax(100px, 1fr) 76px 72px 32px;
  gap: 8px;
  align-items: center;
}

.rank-table-head {
  margin: 20px 0 12px;
  padding: 18px 18px;
  color: #667085;
  border-radius: 10px;
  background: #f7f9fc;
  font-size: 15px;
  font-weight: 700;
}

.rank-list {
  display: grid;
}

.rank-row {
  min-height: 74px;
  padding: 0 14px;
  color: #475467;
  border-bottom: 1px solid #f0f2f5;
}

.rank-row b {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 6px;
  background: #cbd5e1;
  font-style: normal;
}

.rank-row .rank-1 {
  background: #ff543d;
}

.rank-row .rank-2 {
  background: #ff7a1a;
}

.rank-row .rank-3 {
  background: #ffa51f;
}

.rank-row strong {
  overflow: hidden;
  color: #111827;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-row em {
  color: #98a2b3;
  font-style: normal;
  font-size: 24px;
}

.rank-row em.up {
  color: #ff874d;
}

.rank-row em.down {
  color: #22c55e;
}

:deep(.ant-empty-description),
:deep(.ant-list-empty-text) {
  color: #86909c;
}

.status-list {
  display: grid;
  gap: 14px;
}

.status-row {
  display: grid;
  grid-template-columns: 64px 1fr 32px;
  gap: 10px;
  align-items: center;
  color: #475467;
}

.sample-list {
  max-height: 330px;
  overflow-y: auto;
}

.sample-item {
  width: 100%;

  p {
    display: -webkit-box;
    margin: 8px 0 0;
    overflow: hidden;
    color: #1f2329;
    line-height: 1.6;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
}

.sample-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #667085;
}

.report-list {
  display: grid;
  gap: 12px;
}

.report-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid #edf0f5;
  border-radius: 14px;
  background: #f8fbff;

  strong {
    display: block;
    max-width: 210px;
    overflow: hidden;
    color: #111827;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  span {
    display: block;
    margin-top: 4px;
    color: #86909c;
    font-size: 12px;
  }
}

.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.shortcut-grid button {
  min-height: 104px;
  padding: 16px;
  text-align: left;
  color: #475467;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #f8fbff;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    transform: translateY(-2px);
    border-color: #93c5fd;
    background: #eff6ff;
    box-shadow: 0 8px 22px rgba(37, 99, 235, 0.12);
  }

  .anticon {
    display: block;
    color: #2563eb;
    font-size: 22px;
  }

  span {
    display: block;
    margin-top: 10px;
    color: #111827;
    font-weight: 700;
  }

  em {
    display: block;
    margin-top: 4px;
    color: #86909c;
    font-style: normal;
    font-size: 12px;
  }
}

@media (max-width: 960px) {
  .shortcut-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1280px) {
  .trend-body {
    grid-template-columns: 1fr;
  }

  .trend-legend {
    justify-content: flex-start;
    padding: 8px 0 20px;
  }

  .trend-legend::after {
    display: none;
  }

  .legend-item {
    grid-template-columns: 14px 1fr;
  }
}
</style>
