<template>
  <div class="crawl-page">
    <PageHeader
      title="数据采集"
      description="创建跨平台采集任务，并查看已经写入 MongoDB 的历史帖子与评论结果。"
    />

    <div class="crawl-layout">
      <!-- Left Column: Form -->
      <div class="crawl-sidebar">
        <div class="panel-header">
          <span class="panel-title">新建采集任务</span>
        </div>
        <div class="panel-body">
          <a-form layout="vertical" :model="crawlForm" @finish="handleCreateJob" class="minimal-form">
            <div class="form-group">
              <div class="group-title">基础配置</div>
              <a-form-item label="平台">
                <a-select v-model:value="crawlForm.platform" placeholder="选择平台">
                  <a-select-option v-for="platform in platforms" :key="platform.id" :value="platform.id" :disabled="platform.status !== 'active'">
                    {{ platform.name }}
                  </a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item label="事件 ID">
                <a-input v-model:value="crawlForm.event_id" placeholder="例如 trump_visit_2026_05_21" />
              </a-form-item>
              <a-form-item label="执行方式">
                <a-segmented v-model:value="crawlForm.execution_mode" :options="executionModeOptions" block />
              </a-form-item>
            </div>

            <div class="form-group">
              <div class="group-title">目标与关键词</div>
              <a-form-item label="关键词">
                <a-input v-model:value="keywordsInput" placeholder="多个用逗号分隔" />
              </a-form-item>
              <a-form-item label="主关键词">
                <a-input v-model:value="crawlForm.source_keyword" placeholder="留空使用首个" />
              </a-form-item>
              <a-form-item label="直达链接">
                <a-textarea v-model:value="postIdsInput" placeholder="每行一条链接" :rows="2" />
              </a-form-item>
            </div>

            <div class="form-group">
              <div class="group-title">深度配置</div>
              <div class="grid-2-col">
                <a-form-item label="最大帖子数">
                  <a-input-number v-model:value="crawlForm.max_posts" :min="1" :max="1000" style="width: 100%" />
                </a-form-item>
                <a-form-item label="单帖评论上限">
                  <a-input-number v-model:value="crawlForm.max_comments_per_post" :min="0" :max="5000" style="width: 100%" />
                </a-form-item>
              </div>
              <a-form-item label="评论排序">
                <a-select v-model:value="crawlForm.comment_sort">
                  <a-select-option value="none">默认顺序</a-select-option>
                  <a-select-option value="like_count_desc">按点赞降序</a-select-option>
                  <a-select-option value="reply_count_desc">按回复降序</a-select-option>
                </a-select>
              </a-form-item>
              <div class="switches-grid">
                <a-form-item label="抓取评论">
                  <a-switch v-model:checked="crawlForm.crawl_comments" size="small" />
                </a-form-item>
                <a-form-item label="二级评论">
                  <a-switch v-model:checked="crawlForm.recursive_comments" size="small" :disabled="!crawlForm.crawl_comments" />
                </a-form-item>
                <a-form-item label="作者画像">
                  <a-switch v-model:checked="crawlForm.enrich_author_profiles" size="small" />
                </a-form-item>
              </div>
            </div>

            <div class="form-actions">
              <a-button type="primary" html-type="submit" :loading="creating" block size="large">开始采集</a-button>
            </div>
          </a-form>
        </div>
      </div>

      <!-- Right Column: Lists & Data -->
      <div class="crawl-main">
        <div class="main-paper">
          <a-tabs v-model:activeKey="activeTab" class="elegant-tabs" :animated="false">
            <a-tab-pane key="jobs" tab="采集任务列队">
              <div class="tab-toolbar">
                <span class="tab-desc">当前所有历史及运行中的数据采集任务。</span>
                <TableSettings v-if="jobs.length > 0" v-model:size="tableSize" v-model:pageSize="jobPageSize" />
              </div>
              
              <a-table
                v-if="jobs.length > 0"
                :columns="jobColumns"
                :data-source="jobs"
                :loading="loadingJobs"
                row-key="id"
                :size="tableSize"
                :pagination="{ pageSize: jobPageSize }"
                class="borderless-table"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'status'">
                    <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
                  </template>
                  <template v-else-if="column.key === 'action'">
                    <a-space>
                      <a-button v-if="record.job_type === 'media_download'" size="small" type="link" @click="openDownloadDetail(record.id)">详情</a-button>
                      <a-popconfirm v-if="record.status === 'pending' || record.status === 'running'" title="确定取消？" @confirm="handleCancel(record.id)">
                        <a-button size="small" type="link">取消</a-button>
                      </a-popconfirm>
                      <a-popconfirm title="确定删除？" @confirm="handleDelete(record.id)">
                        <a-button size="small" type="link" danger>删除</a-button>
                      </a-popconfirm>
                    </a-space>
                  </template>
                </template>
              </a-table>
              <a-empty v-else description="暂无采集任务" :image-style="{ height: '40px' }" />
            </a-tab-pane>

            <a-tab-pane key="data" tab="采集成果">
              <div class="tab-toolbar">
                <div class="data-filter-bar">
                  <a-select v-model:value="dataFilters.platform" allow-clear placeholder="平台" style="width: 120px" @change="handleDataFilterChange">
                    <a-select-option value="xhs">小红书</a-select-option>
                    <a-select-option value="douyin">抖音</a-select-option>
                    <a-select-option value="weibo">微博</a-select-option>
                  </a-select>
                  <a-input v-model:value="dataFilters.keyword" allow-clear placeholder="关键词" style="width: 160px" @pressEnter="handleDataFilterChange" />
                  <a-input v-model:value="dataFilters.event_id" allow-clear placeholder="事件 ID" style="width: 160px" @pressEnter="handleDataFilterChange" />
                  <a-checkbox v-model:checked="dataFilters.has_media" @change="handleDataFilterChange">仅含媒体</a-checkbox>
                  <a-button @click="handleDataFilterChange">筛选</a-button>
                  <a-button type="primary" :loading="creatingDownload" @click="handleCreateDownload">下载媒体</a-button>
                </div>
                <TableSettings v-if="postData.length > 0" v-model:size="tableSize" v-model:pageSize="dataPageSize" />
              </div>

              <a-table
                v-if="postData.length > 0"
                :columns="dataColumns"
                :data-source="postData"
                :loading="loadingData"
                row-key="post_id"
                :size="tableSize"
                :pagination="{ total: postTotal, pageSize: dataPageSize, onChange: handlePageChange }"
                class="borderless-table"
              />
              <a-empty v-else description="暂无采集数据" :image-style="{ height: '40px' }" />
            </a-tab-pane>
          </a-tabs>
        </div>
      </div>
    </div>

    <a-drawer
      v-model:open="downloadDrawerOpen"
      title="媒体下载详情"
      width="720"
    >
      <a-spin :spinning="loadingDownloadDetail">
        <a-descriptions
          v-if="downloadDetail"
          bordered
          size="small"
          :column="2"
          style="margin-bottom: 16px"
        >
          <a-descriptions-item label="任务 ID">{{ downloadDetail.id }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="statusColor(downloadDetail.status)">{{ downloadDetail.status }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="保存目录" :span="2">
            <span class="path-text">{{ downloadDetail.summary?.save_root || '-' }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="总数">{{ downloadDetail.summary?.total ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="已下载">{{ downloadDetail.summary?.downloaded ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="失败">{{ downloadDetail.summary?.failed ?? 0 }}</a-descriptions-item>
          <a-descriptions-item label="跳过">{{ downloadDetail.summary?.skipped ?? 0 }}</a-descriptions-item>
        </a-descriptions>

        <a-table
          :columns="downloadColumns"
          :data-source="downloadDetail?.items || []"
          row-key="url"
          size="small"
          :pagination="{ pageSize: 8 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="downloadStatusColor(record.status)">{{ record.status }}</a-tag>
            </template>
            <template v-else-if="column.key === 'local_path'">
              <span class="path-text">{{ record.local_path || '-' }}</span>
            </template>
            <template v-else-if="column.key === 'url'">
              <a :href="record.url" target="_blank" rel="noopener noreferrer">原始链接</a>
            </template>
          </template>
        </a-table>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import TableSettings from '@/components/TableSettings.vue'
import {
  cancelCrawlJob,
  createCrawlJob,
  createMediaDownloadJob,
  deleteCrawlJob,
  getMediaDownloadJob,
  getPlatforms,
  listCrawlJobs,
  queryCrawlData,
} from '@/api/crawl'

type TableSize = 'small' | 'middle' | 'default'

interface PlatformOption {
  id: string
  name: string
  status: string
  hint?: string
}

interface CrawlJobItem {
  id: number
  job_type: string
  platform: string
  status: string
  progress: number
  result_summary?: string | null
  created_at: string
}

interface PostItem {
  post_id: string
  platform: string
  author_name: string
  content: string
  likes: number
  reposts: number
  timestamp: string
  media_urls?: string[]
}

interface DownloadSummary {
  save_root?: string
  total?: number
  downloaded?: number
  failed?: number
  skipped?: number
}

interface DownloadItem {
  platform: string
  post_id: string
  media_type: string
  url: string
  local_path?: string
  status: string
  error?: string
}

interface DownloadDetail {
  id: number
  job_type: string
  platform: string
  status: string
  progress: number
  summary?: DownloadSummary
  items: DownloadItem[]
}

const tableSize = ref<TableSize>('middle')
const jobPageSize = ref(10)
const dataPageSize = ref(20)
const activeTab = ref('jobs')

const platforms = ref<PlatformOption[]>([])
const creating = ref(false)
const keywordsInput = ref('')
const postIdsInput = ref('')
const crawlForm = reactive({
  platform: 'weibo',
  event_id: '',
  source_keyword: '',
  max_posts: 50,
  max_comments_per_post: 200,
  crawl_comments: true,
  recursive_comments: true,
  enrich_author_profiles: false,
  comment_sort: 'none' as 'none' | 'like_count_desc' | 'reply_count_desc',
  execution_mode: 'local' as 'local' | 'queued',
})

const jobs = ref<CrawlJobItem[]>([])
const loadingJobs = ref(false)
const postData = ref<PostItem[]>([])
const postTotal = ref(0)
const loadingData = ref(false)
const creatingDownload = ref(false)
const downloadDrawerOpen = ref(false)
const loadingDownloadDetail = ref(false)
const downloadDetail = ref<DownloadDetail | null>(null)
const pageActive = ref(false)
let refreshTimer: number | undefined
let postCreateRefreshTimer: number | undefined
let initialCrawlLoad: Promise<void> | null = null
let jobsRequestGeneration = 0
let dataRequestGeneration = 0

const dataFilters = reactive({
  platform: undefined as string | undefined,
  keyword: '',
  event_id: '',
  has_media: true,
})

const executionModeOptions = [
  { label: '本地后台执行', value: 'local' },
  { label: 'Celery 队列', value: 'queued' },
]

const jobColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 72 },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '进度', dataIndex: 'progress', key: 'progress', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
  { title: '操作', key: 'action', width: 160 },
]

const dataColumns = [
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 100 },
  { title: '作者', dataIndex: 'author_name', key: 'author_name', width: 140 },
  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '点赞', dataIndex: 'likes', key: 'likes', width: 90 },
  { title: '转发', dataIndex: 'reposts', key: 'reposts', width: 90 },
  { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
]

const downloadColumns = [
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 90 },
  { title: '帖子', dataIndex: 'post_id', key: 'post_id', width: 130, ellipsis: true },
  { title: '类型', dataIndex: 'media_type', key: 'media_type', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '本地路径', dataIndex: 'local_path', key: 'local_path', ellipsis: true },
  { title: '链接', dataIndex: 'url', key: 'url', width: 90 },
]

function statusColor(status: string) {
  return (
    {
      pending: 'default',
      running: 'processing',
      completed: 'success',
      failed: 'error',
      cancelled: 'warning',
    } as Record<string, string>
  )[status] || 'default'
}

function downloadStatusColor(status: string) {
  return (
    {
      pending: 'default',
      downloaded: 'success',
      failed: 'error',
      skipped: 'warning',
    } as Record<string, string>
  )[status] || statusColor(status)
}

async function handleCreateJob() {
  creating.value = true
  try {
    const keywords = keywordsInput.value
      .split(/[,\uff0c]/)
      .map((item) => item.trim())
      .filter(Boolean)

    const post_ids = postIdsInput.value
      .split(/[\n,\uff0c]/)
      .map((item) => item.trim())
      .filter((item) => item.startsWith('http://') || item.startsWith('https://'))

    if (crawlForm.platform === 'news' && post_ids.length === 0) {
      message.warning('新闻采集需要填写至少一条 http(s) 链接')
      return
    }
    if (crawlForm.platform !== 'news' && keywords.length === 0) {
      message.warning('社交平台采集需要填写至少一个关键词')
      return
    }

    await createCrawlJob({
      platform: crawlForm.platform,
      keywords,
      event_id: crawlForm.event_id.trim() || undefined,
      source_keyword: crawlForm.source_keyword.trim() || keywords[0],
      post_ids,
      max_posts: crawlForm.max_posts,
      crawl_comments: crawlForm.crawl_comments,
      recursive_comments: crawlForm.crawl_comments && crawlForm.recursive_comments,
      enrich_author_profiles: crawlForm.enrich_author_profiles,
      comment_sort: crawlForm.comment_sort,
      max_comments_per_post: crawlForm.max_comments_per_post,
      execution_mode: crawlForm.execution_mode,
    })

    message.success(crawlForm.execution_mode === 'local' ? '采集任务已在本地后台启动' : '采集任务已投递队列')
    await fetchJobs()
    schedulePostCreateRefresh()
  } finally {
    creating.value = false
  }
}

async function handleCancel(jobId: number) {
  await cancelCrawlJob(jobId)
  message.success('任务已取消')
  await fetchJobs()
}

async function handleDelete(jobId: number) {
  await deleteCrawlJob(jobId)
  message.success('任务已删除')
  await fetchJobs()
  await fetchData()
}

async function handleCreateDownload() {
  const platform = dataFilters.platform
  if (platform && !['xhs', 'douyin'].includes(platform)) {
    message.warning('媒体下载当前支持小红书和抖音')
    return
  }

  creatingDownload.value = true
  try {
    const response = (await createMediaDownloadJob({
      platform,
      keyword: dataFilters.keyword.trim() || undefined,
      event_id: dataFilters.event_id.trim() || undefined,
      media_types: ['video', 'image'],
    })) as { data: CrawlJobItem }
    message.success('媒体下载任务已启动')
    await fetchJobs()
    if (response.data?.id) {
      void openDownloadDetail(response.data.id)
    }
  } finally {
    creatingDownload.value = false
  }
}

async function openDownloadDetail(jobId: number) {
  downloadDrawerOpen.value = true
  loadingDownloadDetail.value = true
  try {
    const response = (await getMediaDownloadJob(jobId)) as { data: DownloadDetail | null }
    downloadDetail.value = response.data
  } finally {
    loadingDownloadDetail.value = false
  }
}

function handleDataFilterChange() {
  void fetchData(1)
}

async function fetchJobs() {
  if (!pageActive.value) return
  const requestGeneration = ++jobsRequestGeneration
  loadingJobs.value = true
  try {
    const response = (await listCrawlJobs({ page: 1, page_size: 50 })) as {
      data: { items: CrawlJobItem[] }
    }
    if (!pageActive.value || requestGeneration !== jobsRequestGeneration) return
    jobs.value = response.data.items
  } finally {
    if (requestGeneration === jobsRequestGeneration) {
      loadingJobs.value = false
    }
  }
}

async function fetchData(page = 1) {
  if (!pageActive.value) return
  const requestGeneration = ++dataRequestGeneration
  loadingData.value = true
  try {
    const response = (await queryCrawlData({
      platform: dataFilters.platform,
      keyword: dataFilters.keyword.trim() || undefined,
      event_id: dataFilters.event_id.trim() || undefined,
      has_media: dataFilters.has_media || undefined,
      page,
      page_size: dataPageSize.value,
    })) as {
      data: { items: PostItem[]; total: number }
    }
    if (!pageActive.value || requestGeneration !== dataRequestGeneration) return
    postData.value = response.data.items
    postTotal.value = response.data.total
  } finally {
    if (requestGeneration === dataRequestGeneration) {
      loadingData.value = false
    }
  }
}

function handlePageChange(page: number) {
  void fetchData(page)
}

function hasActiveJobs() {
  return jobs.value.some((job) => job.status === 'pending' || job.status === 'running')
}

function startRefreshTimer() {
  if (!pageActive.value || refreshTimer !== undefined) return
  refreshTimer = window.setInterval(() => {
    if (pageActive.value && hasActiveJobs()) {
      void fetchJobs()
      void fetchData()
    }
  }, 5000)
}

function stopRefreshTimers() {
  if (refreshTimer !== undefined) {
    window.clearInterval(refreshTimer)
    refreshTimer = undefined
  }
  if (postCreateRefreshTimer !== undefined) {
    window.clearTimeout(postCreateRefreshTimer)
    postCreateRefreshTimer = undefined
  }
}

function schedulePostCreateRefresh() {
  if (postCreateRefreshTimer !== undefined) {
    window.clearTimeout(postCreateRefreshTimer)
  }
  postCreateRefreshTimer = window.setTimeout(() => {
    postCreateRefreshTimer = undefined
    if (!pageActive.value) return
    void fetchJobs()
    void fetchData()
  }, 1500)
}

async function initializeCrawlPage() {
  if (initialCrawlLoad) return initialCrawlLoad
  const load = (async () => {
    const response = (await getPlatforms()) as { data: PlatformOption[] }
    if (!pageActive.value) return
    platforms.value = response.data
    await Promise.all([fetchJobs(), fetchData()])
  })()
  initialCrawlLoad = load
  try {
    await load
  } finally {
    if (initialCrawlLoad === load) {
      initialCrawlLoad = null
    }
  }
}

function activateCrawlPage() {
  pageActive.value = true
  startRefreshTimer()
  if (!platforms.value.length) {
    void initializeCrawlPage()
    return
  }
  if (hasActiveJobs()) {
    void fetchJobs()
    void fetchData()
  }
}

function deactivateCrawlPage() {
  pageActive.value = false
  jobsRequestGeneration += 1
  dataRequestGeneration += 1
  loadingJobs.value = false
  loadingData.value = false
  stopRefreshTimers()
}

onMounted(() => {
  activateCrawlPage()
})

onActivated(() => {
  activateCrawlPage()
})

onDeactivated(() => {
  deactivateCrawlPage()
})

onBeforeUnmount(() => {
  deactivateCrawlPage()
})
</script>

<style scoped>
.crawl-layout {
  display: flex;
  gap: 24px;
  align-items: stretch;
}

@media (max-width: 1200px) {
  .crawl-layout {
    flex-direction: column;
  }
}

.crawl-sidebar {
  flex: 0 0 340px;
  width: 100%;
  background: #FFFFFF;
  border-radius: 8px;
  border: 1px solid #E4E4E7;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}

.crawl-main {
  flex: 1;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid #F4F4F5;
  background: #FFFFFF;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #18181B;
}

.panel-body {
  padding: 20px;
}

.minimal-form .form-group {
  margin-bottom: 24px;
}

.minimal-form .group-title {
  font-size: 13px;
  font-weight: 600;
  color: #71717A;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.grid-2-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.switches-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.form-actions {
  margin-top: 32px;
}

.main-paper {
  background: #FFFFFF;
  border-radius: 8px;
  border: 1px solid #E4E4E7;
  padding: 12px 24px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.elegant-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.elegant-tabs :deep(.ant-tabs-content-holder) {
  flex: 1;
}

.elegant-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 20px;
}
.elegant-tabs :deep(.ant-tabs-tab) {
  font-size: 15px;
  padding: 12px 0;
}

.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.tab-desc {
  color: #71717A;
  font-size: 13px;
}

.data-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.path-text {
  word-break: break-all;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}

/* Adjust ant-form-item margin to be tighter in the sidebar */
.minimal-form :deep(.ant-form-item) {
  margin-bottom: 16px;
}
</style>
