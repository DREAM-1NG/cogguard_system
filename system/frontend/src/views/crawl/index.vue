<template>
  <div>
    <PageHeader
      title="数据采集"
      description="创建跨平台采集任务，并查看已经写入 MongoDB 的历史帖子与评论结果。"
    />

    <a-card title="创建采集任务" size="small" style="margin-bottom: 16px">
      <a-form layout="vertical" :model="crawlForm" @finish="handleCreateJob">
        <div class="crawl-form-grid">
        <a-form-item label="平台">
          <a-select
            v-model:value="crawlForm.platform"
            placeholder="选择平台"
          >
            <a-select-option
              v-for="platform in platforms"
              :key="platform.id"
              :value="platform.id"
              :disabled="platform.status !== 'active'"
            >
              {{ platform.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="事件 ID">
          <a-input
            v-model:value="crawlForm.event_id"
            placeholder="例如 trump_visit_2026_05_21；留空则按任务生成"
          />
        </a-form-item>

        <a-form-item label="执行方式">
          <a-segmented
            v-model:value="crawlForm.execution_mode"
            :options="executionModeOptions"
          />
        </a-form-item>

        <a-form-item label="关键词">
          <a-input
            v-model:value="keywordsInput"
            placeholder="多个关键词用逗号分隔"
          />
        </a-form-item>

        <a-form-item label="主关键词">
          <a-input
            v-model:value="crawlForm.source_keyword"
            placeholder="留空则使用第一个关键词"
          />
        </a-form-item>

        <a-form-item label="链接">
          <a-textarea
            v-model:value="postIdsInput"
            placeholder="新闻平台可填写每行一条 http(s) 链接"
            :rows="2"
          />
        </a-form-item>

        <a-form-item label="最大帖子数">
          <a-input-number
            v-model:value="crawlForm.max_posts"
            :min="1"
            :max="1000"
            style="width: 100%"
          />
        </a-form-item>

        <a-form-item label="单帖评论上限">
          <a-input-number
            v-model:value="crawlForm.max_comments_per_post"
            :min="0"
            :max="5000"
            style="width: 100%"
          />
        </a-form-item>

        <a-form-item label="评论排序">
          <a-select v-model:value="crawlForm.comment_sort">
            <a-select-option value="none">默认顺序</a-select-option>
            <a-select-option value="like_count_desc">按点赞数降序</a-select-option>
            <a-select-option value="reply_count_desc">按回复数降序</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="抓取评论">
          <a-switch v-model:checked="crawlForm.crawl_comments" />
        </a-form-item>

        <a-form-item label="二级评论">
          <a-switch
            v-model:checked="crawlForm.recursive_comments"
            :disabled="!crawlForm.crawl_comments"
          />
        </a-form-item>

        <a-form-item label="作者画像">
          <a-switch v-model:checked="crawlForm.enrich_author_profiles" />
        </a-form-item>

        <a-form-item class="crawl-form-submit">
          <a-button
            type="primary"
            html-type="submit"
            :loading="creating"
          >
            开始采集
          </a-button>
        </a-form-item>
        </div>
      </a-form>
    </a-card>

    <a-card size="small" style="margin-bottom: 16px">
      <template #title>采集任务列表</template>
      <template #extra v-if="jobs.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="jobPageSize" />
      </template>

      <a-table
        v-if="jobs.length > 0"
        :columns="jobColumns"
        :data-source="jobs"
        :loading="loadingJobs"
        row-key="id"
        :size="tableSize"
        :pagination="{ pageSize: jobPageSize }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
          </template>

          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button
                v-if="record.job_type === 'media_download'"
                size="small"
                type="link"
                @click="openDownloadDetail(record.id)"
              >
                详情
              </a-button>
              <a-popconfirm
                v-if="record.status === 'pending' || record.status === 'running'"
                title="确定取消？"
                @confirm="handleCancel(record.id)"
              >
                <a-button size="small" type="link">取消</a-button>
              </a-popconfirm>

              <a-popconfirm
                title="确定删除该任务及其关联数据？"
                @confirm="handleDelete(record.id)"
              >
                <a-button size="small" type="link" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>

      <a-empty
        v-else
        description="暂无采集任务"
        :image-style="{ height: '40px' }"
      />
    </a-card>

    <a-card size="small">
      <template #title>采集数据</template>
      <template #extra v-if="postData.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="dataPageSize" />
      </template>

      <div class="data-filter-bar">
        <a-select
          v-model:value="dataFilters.platform"
          allow-clear
          placeholder="平台"
          style="width: 140px"
          @change="handleDataFilterChange"
        >
          <a-select-option value="xhs">小红书</a-select-option>
          <a-select-option value="douyin">抖音</a-select-option>
          <a-select-option value="weibo">微博</a-select-option>
        </a-select>
        <a-input
          v-model:value="dataFilters.keyword"
          allow-clear
          placeholder="关键词"
          style="width: 180px"
          @pressEnter="handleDataFilterChange"
        />
        <a-input
          v-model:value="dataFilters.event_id"
          allow-clear
          placeholder="事件 ID"
          style="width: 180px"
          @pressEnter="handleDataFilterChange"
        />
        <a-checkbox v-model:checked="dataFilters.has_media" @change="handleDataFilterChange">
          仅含媒体
        </a-checkbox>
        <a-button @click="handleDataFilterChange">筛选</a-button>
        <a-button type="primary" :loading="creatingDownload" @click="handleCreateDownload">
          下载媒体
        </a-button>
      </div>

      <a-table
        v-if="postData.length > 0"
        :columns="dataColumns"
        :data-source="postData"
        :loading="loadingData"
        row-key="post_id"
        :size="tableSize"
        :pagination="{ total: postTotal, pageSize: dataPageSize, onChange: handlePageChange }"
      />

      <a-empty
        v-else
        description="暂无采集数据"
        :image-style="{ height: '40px' }"
      />
    </a-card>

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
import { onMounted, onUnmounted, reactive, ref } from 'vue'
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
let refreshTimer: number | undefined

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
    window.setTimeout(() => {
      void fetchJobs()
      void fetchData()
    }, 1500)
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
  loadingJobs.value = true
  try {
    const response = (await listCrawlJobs({ page: 1, page_size: 50 })) as {
      data: { items: CrawlJobItem[] }
    }
    jobs.value = response.data.items
  } finally {
    loadingJobs.value = false
  }
}

async function fetchData(page = 1) {
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
    postData.value = response.data.items
    postTotal.value = response.data.total
  } finally {
    loadingData.value = false
  }
}

function handlePageChange(page: number) {
  void fetchData(page)
}

onMounted(async () => {
  const response = (await getPlatforms()) as { data: PlatformOption[] }
  platforms.value = response.data
  void fetchJobs()
  void fetchData()
  refreshTimer = window.setInterval(() => {
    if (jobs.value.some((job) => job.status === 'pending' || job.status === 'running')) {
      void fetchJobs()
      void fetchData()
    }
  }, 5000)
})

onUnmounted(() => {
  if (refreshTimer !== undefined) {
    window.clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.crawl-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px 16px;
  align-items: end;
}

.crawl-form-submit {
  align-self: end;
}

.data-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 12px;
  align-items: center;
  margin-bottom: 12px;
}

.path-text {
  word-break: break-all;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}
</style>
