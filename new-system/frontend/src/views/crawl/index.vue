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
      message="预览态已接入真实历史采集数据"
      description="当前支持浏览历史采集任务和帖子数据；创建、取消、删除采集任务仍需要切换到真实登录。"
    />

    <a-card title="创建采集任务" size="small" style="margin-bottom: 16px">
      <a-form layout="inline" :model="crawlForm" @finish="handleCreateJob">
        <a-form-item label="平台">
          <a-select
            v-model:value="crawlForm.platform"
            style="width: 180px"
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

        <a-form-item label="关键词">
          <a-input
            v-model:value="keywordsInput"
            placeholder="社交平台按逗号分隔；新闻平台可留空"
            style="width: 260px"
          />
        </a-form-item>

        <a-form-item label="链接">
          <a-textarea
            v-model:value="postIdsInput"
            placeholder="新闻平台可填写每行一条 http(s) 链接"
            :rows="2"
            style="width: 320px"
          />
        </a-form-item>

        <a-form-item label="最大帖子数">
          <a-input-number v-model:value="crawlForm.max_posts" :min="1" :max="1000" />
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            :loading="creating"
            :disabled="isPreviewMode"
          >
            开始采集
          </a-button>
        </a-form-item>
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
import { computed, onMounted, reactive, ref } from 'vue'
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
  max_posts: 50,
  crawl_comments: true,
})

const jobs = ref<CrawlJobItem[]>([])
const loadingJobs = ref(false)
const postData = ref<PostItem[]>([])
const postTotal = ref(0)
const loadingData = ref(false)

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
  if (isPreviewMode.value) {
    message.info('预览态仅支持查看历史采集数据，请切换真实登录后创建任务')
    return
  }

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

    await createCrawlJob({
      platform: crawlForm.platform,
      keywords,
      post_ids,
      max_posts: crawlForm.max_posts,
      crawl_comments: crawlForm.crawl_comments,
    })

    message.success('采集任务已创建')
    await fetchJobs()
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
})
</script>
