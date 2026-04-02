<!--
  数据采集管理页面
-->
<template>
  <div>
    <PageHeader title="数据采集" description="创建跨平台数据采集任务，支持 Mock 模拟和真实爬虫。采集的帖子/评论存入 MongoDB，供协同检测、传播归因等模块分析。" />

    <!-- 创建采集任务 -->
    <a-card title="创建采集任务" size="small" style="margin-bottom: 16px">
      <a-form layout="inline" :model="crawlForm" @finish="handleCreateJob">
        <a-form-item label="平台">
          <a-select v-model:value="crawlForm.platform" style="width: 160px" placeholder="选择平台">
            <a-select-option v-for="p in platforms" :key="p.id" :value="p.id" :disabled="p.status !== 'active'">
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="关键词">
          <a-input v-model:value="keywordsInput" placeholder="多个关键词用逗号分隔" style="width: 240px" />
        </a-form-item>
        <a-form-item label="最大帖子数">
          <a-input-number v-model:value="crawlForm.max_posts" :min="1" :max="1000" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="creating">开始采集</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 任务列表 -->
    <a-card size="small" style="margin-bottom: 16px">
      <template #title>采集任务列表</template>
      <template #extra v-if="jobs.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="jobPageSize" />
      </template>
      <a-table v-if="jobs.length > 0"
        :columns="jobColumns" :dataSource="jobs" :loading="loadingJobs" rowKey="id"
        :size="tableSize" :pagination="{ pageSize: jobPageSize }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-popconfirm v-if="record.status === 'pending' || record.status === 'running'" title="确定取消？" @confirm="handleCancel(record.id)">
                <a-button size="small" type="link">取消</a-button>
              </a-popconfirm>
              <a-popconfirm title="确定删除该任务及其数据？" @confirm="handleDelete(record.id)">
                <a-button size="small" type="link" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
      <a-empty v-else description="暂无采集任务" :image-style="{ height: '40px' }" />
    </a-card>

    <!-- 采集数据 -->
    <a-card size="small">
      <template #title>采集数据</template>
      <template #extra v-if="postData.length > 0">
        <TableSettings v-model:size="tableSize" v-model:pageSize="dataPageSize" />
      </template>
      <a-table v-if="postData.length > 0"
        :columns="dataColumns" :dataSource="postData" :loading="loadingData" rowKey="post_id"
        :size="tableSize" :pagination="{ total: postTotal, pageSize: dataPageSize, onChange: handlePageChange }"
      />
      <a-empty v-else description="暂无采集数据" :image-style="{ height: '40px' }" />
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getPlatforms, createCrawlJob, listCrawlJobs, queryCrawlData, deleteCrawlJob, cancelCrawlJob } from '@/api/crawl'
import TableSettings from '@/components/TableSettings.vue'
import PageHeader from '@/components/PageHeader.vue'

const tableSize = ref<'small' | 'middle' | 'default'>('middle')
const jobPageSize = ref(10)
const dataPageSize = ref(20)

const platforms = ref<Array<{ id: string; name: string; status: string }>>([])
const creating = ref(false)
const keywordsInput = ref('')
const crawlForm = reactive({ platform: 'mock_weibo', max_posts: 50, crawl_comments: true })

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

function statusColor(s: string) {
  return ({ pending: 'default', running: 'processing', completed: 'success', failed: 'error' } as Record<string, string>)[s] || 'default'
}

async function handleCreateJob() {
  creating.value = true
  try {
    const keywords = keywordsInput.value.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    await createCrawlJob({ platform: crawlForm.platform, keywords, max_posts: crawlForm.max_posts, crawl_comments: crawlForm.crawl_comments })
    message.success('采集任务已创建')
    await fetchJobs()
  } catch { /* handled */ } finally { creating.value = false }
}

async function handleCancel(id: number) {
  try { await cancelCrawlJob(id); message.success('已取消'); await fetchJobs() } catch { /* handled */ }
}
async function handleDelete(id: number) {
  try { await deleteCrawlJob(id); message.success('已删除'); await fetchJobs(); await fetchData() } catch { /* handled */ }
}

async function fetchJobs() {
  loadingJobs.value = true
  try { const r = (await listCrawlJobs({ page: 1, page_size: 50 })) as any; jobs.value = r.data.items } catch { /* handled */ } finally { loadingJobs.value = false }
}
async function fetchData(page = 1) {
  loadingData.value = true
  try { const r = (await queryCrawlData({ page, page_size: 20 })) as any; postData.value = r.data.items; postTotal.value = r.data.total } catch { /* handled */ } finally { loadingData.value = false }
}
function handlePageChange(page: number) { fetchData(page) }

onMounted(async () => {
  try { const r = (await getPlatforms()) as any; platforms.value = r.data } catch { /* handled */ }
  fetchJobs()
  fetchData()
})
</script>
