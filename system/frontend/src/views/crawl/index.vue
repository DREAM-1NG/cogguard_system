<template>
  <div>
    <PageHeader
      title="数据采集"
      description="创建跨平台采集任务，并查看已经写入 MongoDB 的历史帖子与评论结果。"
    />

    <a-alert
      v-if="isPreviewMode"
      type="info"
      show-icon
      style="margin-bottom: 16px"
      message="预览态已接入真实历史采集数据与本地任务执行"
      description="可以创建本地后台采集任务；取消和删除仍建议切换真实登录后操作。"
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
            <a-space v-if="!isPreviewMode">
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
            <a-tag v-else color="blue">预览只读</a-tag>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import PageHeader from '@/components/PageHeader.vue'
import TableSettings from '@/components/TableSettings.vue'
import { useAuthStore } from '@/stores/auth'
import {
  cancelCrawlJob,
  createCrawlJob,
  deleteCrawlJob,
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
  platform: string
  status: string
  progress: number
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
}

const authStore = useAuthStore()
const isPreviewMode = computed(() => authStore.isPreviewMode)

const tableSize = ref<TableSize>('middle')
const jobPageSize = ref(10)
const dataPageSize = ref(20)

const platforms = ref<PlatformOption[]>([])
const creating = ref(false)
const keywordsInput = ref('')
const postIdsInput = ref('')
const crawlForm = reactive({
  platform: 'mock_weibo',
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
let refreshTimer: number | undefined

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
  if (isPreviewMode.value) {
    message.info('预览态仅支持查看历史采集数据，请切换真实登录后管理任务')
    return
  }
  await cancelCrawlJob(jobId)
  message.success('任务已取消')
  await fetchJobs()
}

async function handleDelete(jobId: number) {
  if (isPreviewMode.value) {
    message.info('预览态仅支持查看历史采集数据，请切换真实登录后管理任务')
    return
  }
  await deleteCrawlJob(jobId)
  message.success('任务已删除')
  await fetchJobs()
  await fetchData()
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
    const response = (await queryCrawlData({ page, page_size: dataPageSize.value })) as {
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
</style>
