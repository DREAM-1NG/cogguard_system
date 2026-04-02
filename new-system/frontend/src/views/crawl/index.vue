<!--
  数据采集管理页面

  功能：
  1. 创建采集任务（选择平台、输入关键词、设置参数）
  2. 查看采集任务列表与状态
  3. 查询已采集的帖子数据
-->
<template>
  <div>
    <h2 style="margin-bottom: 24px">数据采集</h2>

    <!-- 创建采集任务 -->
    <a-card title="创建采集任务" style="margin-bottom: 24px">
      <a-form layout="inline" :model="crawlForm" @finish="handleCreateJob">
        <a-form-item label="平台">
          <a-select
            v-model:value="crawlForm.platform"
            style="width: 160px"
            placeholder="选择平台"
          >
            <a-select-option
              v-for="p in platforms"
              :key="p.id"
              :value="p.id"
              :disabled="p.status !== 'active'"
            >
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="关键词">
          <a-input
            v-model:value="keywordsInput"
            placeholder="多个关键词用逗号分隔"
            style="width: 240px"
          />
        </a-form-item>

        <a-form-item label="最大帖子数">
          <a-input-number v-model:value="crawlForm.max_posts" :min="1" :max="1000" />
        </a-form-item>

        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="creating">
            开始采集
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 任务列表 -->
    <a-card title="采集任务列表" style="margin-bottom: 24px">
      <a-table
        :columns="jobColumns"
        :dataSource="jobs"
        :loading="loadingJobs"
        rowKey="id"
        :pagination="{ pageSize: 10 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-popconfirm
                v-if="record.status === 'pending' || record.status === 'running'"
                title="确定取消该任务？"
                @confirm="handleCancel(record.id)"
              >
                <a-button size="small" type="link">取消</a-button>
              </a-popconfirm>
              <a-popconfirm title="确定删除该任务及其数据？" @confirm="handleDelete(record.id)">
                <a-button size="small" type="link" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 采集数据查询 -->
    <a-card title="采集数据">
      <a-table
        :columns="dataColumns"
        :dataSource="postData"
        :loading="loadingData"
        rowKey="post_id"
        :pagination="{ total: postTotal, pageSize: 20, onChange: handlePageChange }"
      />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getPlatforms, createCrawlJob, listCrawlJobs, queryCrawlData, deleteCrawlJob, cancelCrawlJob } from '@/api/crawl'

// ---- 平台列表 ----
const platforms = ref<Array<{ id: string; name: string; status: string }>>([])

// ---- 创建任务 ----
const creating = ref(false)
const keywordsInput = ref('')
const crawlForm = reactive({
  platform: 'mock_weibo',
  max_posts: 50,
  crawl_comments: true,
})

// ---- 任务列表 ----
const jobs = ref<unknown[]>([])
const loadingJobs = ref(false)

const jobColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '平台', dataIndex: 'platform', key: 'platform' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '进度', dataIndex: 'progress', key: 'progress' },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
  { title: '操作', key: 'action', width: 160 },
]

// ---- 数据查询 ----
const postData = ref<unknown[]>([])
const postTotal = ref(0)
const loadingData = ref(false)

const dataColumns = [
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 100 },
  { title: '作者', dataIndex: 'author_name', key: 'author_name', width: 120 },
  { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
  { title: '点赞', dataIndex: 'likes', key: 'likes', width: 80 },
  { title: '转发', dataIndex: 'reposts', key: 'reposts', width: 80 },
  { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
]

/** 获取任务状态对应的标签颜色 */
function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
  }
  return map[status] || 'default'
}

/** 创建采集任务 */
async function handleCreateJob() {
  creating.value = true
  try {
    const keywords = keywordsInput.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    await createCrawlJob({
      platform: crawlForm.platform,
      keywords,
      max_posts: crawlForm.max_posts,
      crawl_comments: crawlForm.crawl_comments,
    })
    message.success('采集任务已创建')
    await fetchJobs()
  } catch {
    // 错误已由 request 拦截器处理
  } finally {
    creating.value = false
  }
}

/** 取消采集任务 */
async function handleCancel(jobId: number) {
  try {
    await cancelCrawlJob(jobId)
    message.success('任务已取消')
    await fetchJobs()
  } catch { /* handled */ }
}

/** 删除采集任务 */
async function handleDelete(jobId: number) {
  try {
    await deleteCrawlJob(jobId)
    message.success('任务已删除')
    await fetchJobs()
    await fetchData()
  } catch { /* handled */ }
}

/** 加载任务列表 */
async function fetchJobs() {
  loadingJobs.value = true
  try {
    const res = (await listCrawlJobs({ page: 1, page_size: 50 })) as { data: { items: unknown[] } }
    jobs.value = res.data.items
  } catch {
    // handled
  } finally {
    loadingJobs.value = false
  }
}

/** 加载采集数据 */
async function fetchData(page = 1) {
  loadingData.value = true
  try {
    const res = (await queryCrawlData({ page, page_size: 20 })) as {
      data: { items: unknown[]; total: number }
    }
    postData.value = res.data.items
    postTotal.value = res.data.total
  } catch {
    // handled
  } finally {
    loadingData.value = false
  }
}

/** 数据分页切换 */
function handlePageChange(page: number) {
  fetchData(page)
}

onMounted(async () => {
  try {
    const res = (await getPlatforms()) as { data: Array<{ id: string; name: string; status: string }> }
    platforms.value = res.data
  } catch {
    // handled
  }
  fetchJobs()
  fetchData()
})
</script>
