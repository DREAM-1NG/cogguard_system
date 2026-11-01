<template>
  <div class="crawl-page">
    <PageHeader title="数据采集" description="配置检索范围，按任务查看采集证据与已下载媒体。" />

    <div class="crawl-workbench">
      <aside class="control-column crawl-scroll-pane" tabindex="0" aria-label="采集控制台">
        <section class="tool-surface request-surface">
          <div class="surface-heading">
            <div><p class="eyebrow">01 / acquisition</p><h2>采集配置</h2></div>
            <span class="surface-hint">用户提供检索词</span>
          </div>
          <form class="request-form" @submit.prevent="handleCreateJob">
            <label class="field-label" for="crawl-platform">平台</label>
            <a-select id="crawl-platform" v-model:value="crawlForm.platform" class="full-control">
              <a-select-option v-for="platform in platforms" :key="platform.id" :value="platform.id" :disabled="platform.status !== 'active'">{{ platform.name }}</a-select-option>
            </a-select>
            <label class="field-label" for="crawl-event">事件标识</label>
            <a-input id="crawl-event" v-model:value="crawlForm.event_id" placeholder="如 trump_visit_2026_05_21" />
            <div class="field-pair">
              <div><label class="field-label" for="crawl-mode">执行方式</label><a-segmented id="crawl-mode" v-model:value="crawlForm.execution_mode" :options="executionModeOptions" block /></div>
              <div><label class="field-label" for="crawl-limit">帖子数量</label><a-input-number id="crawl-limit" v-model:value="crawlForm.max_posts" :min="1" :max="1000" class="full-control" /></div>
            </div>
            <div class="section-label-row"><span class="field-label">检索词分组</span><a-button type="link" size="small" @click="addKeywordGroup">新增分组</a-button></div>
            <div class="keyword-groups">
              <div v-for="group in keywordGroups" :key="group.id" class="keyword-group">
                <div class="group-heading">
                  <button type="button" class="collapse-toggle" :aria-expanded="group.expanded" :aria-label="`${group.expanded ? '收起' : '展开'}${group.name || '检索词分组'}`" @click="group.expanded = !group.expanded"><span class="collapse-chevron" :class="{ expanded: group.expanded }">›</span></button>
                  <a-input v-model:value="group.name" size="small" class="group-name-input" placeholder="分组名称" />
                  <a-button v-if="keywordGroups.length > 1" type="text" danger size="small" aria-label="删除检索词分组" @click="removeKeywordGroup(group.id)">删除</a-button>
                </div>
                <div v-show="group.expanded" class="group-body">
                  <div class="keyword-chip-list"><a-tag v-for="keyword in group.keywords" :key="keyword" closable @close="removeKeyword(group, keyword)">{{ keyword }}</a-tag><span v-if="group.keywords.length === 0" class="muted-text">还没有检索词</span></div>
                  <a-input v-model:value="group.draft" size="small" placeholder="输入后按 Enter 添加" @pressEnter.prevent="addKeyword(group)" />
                </div>
              </div>
            </div>
            <label class="field-label" for="crawl-primary">主关键词</label>
            <a-select id="crawl-primary" v-model:value="crawlForm.source_keyword" class="full-control" allow-clear placeholder="从已输入检索词中选择"><a-select-option v-for="keyword in keywordOptions" :key="keyword" :value="keyword">{{ keyword }}</a-select-option></a-select>
            <details class="advanced-options">
              <summary>采集选项</summary>
              <div class="advanced-grid">
                <label class="option-row"><span>抓取评论</span><a-switch v-model:checked="crawlForm.crawl_comments" /></label>
                <label class="option-row"><span>递归评论</span><a-switch v-model:checked="crawlForm.recursive_comments" :disabled="!crawlForm.crawl_comments" /></label>
                <label class="option-row"><span>作者画像</span><a-switch v-model:checked="crawlForm.enrich_author_profiles" /></label>
                <label class="field-label" for="comment-limit">单帖评论上限</label><a-input-number id="comment-limit" v-model:value="crawlForm.max_comments_per_post" :min="0" :max="5000" class="full-control" />
                <label class="field-label" for="comment-sort">评论排序</label><a-select id="comment-sort" v-model:value="crawlForm.comment_sort" class="full-control"><a-select-option value="none">默认顺序</a-select-option><a-select-option value="like_count_desc">按点赞数降序</a-select-option><a-select-option value="reply_count_desc">按回复数降序</a-select-option></a-select>
                <label class="field-label" for="crawl-links">链接</label><a-textarea id="crawl-links" v-model:value="postIdsInput" :rows="2" placeholder="新闻平台每行一条 http(s) 链接" />
              </div>
            </details>
            <a-button type="primary" html-type="submit" block :loading="creating">开始采集</a-button>
          </form>
        </section>

        <section class="tool-surface task-summary-surface">
          <div class="surface-heading compact-heading"><div><p class="eyebrow">02 / selected job</p><h2>当前任务</h2></div><a-tag v-if="selectedJob" :color="statusColor(selectedJob.status)">{{ statusLabel(selectedJob.status) }}</a-tag></div>
          <div v-if="selectedJob" class="task-metrics"><div><strong>{{ selectedJobSummary.postsCount }}</strong><span>帖子</span></div><div><strong>{{ selectedJobSummary.commentsCount }}</strong><span>评论</span></div><div><strong>{{ selectedJob.progress }}%</strong><span>进度</span></div></div>
          <p v-if="selectedJob" class="selected-job-caption">{{ platformName(selectedJob.platform) }} · {{ formatDate(selectedJob.created_at) }}</p>
          <a-empty v-else description="请选择一个采集任务" :image-style="{ height: '36px' }" />
        </section>

        <section class="tool-surface history-surface">
          <div class="surface-heading compact-heading"><div><p class="eyebrow">03 / history</p><h2>任务历史</h2></div><a-spin v-if="loadingJobs" size="small" /></div>
          <div v-if="contentJobs.length" class="job-history" role="list">
            <div v-for="job in contentJobs" :key="job.id" class="job-history-row" :class="{ selected: selectedJobId === job.id }" role="button" tabindex="0" @click="selectJob(job.id)" @keydown.enter="selectJob(job.id)" @keydown.space.prevent="selectJob(job.id)">
              <div class="job-history-main"><span class="job-platform-mark">{{ platformName(job.platform).slice(0, 1) }}</span><div class="job-history-copy"><strong>{{ platformName(job.platform) }}</strong><span>{{ formatDate(job.created_at) }} · {{ statusLabel(job.status) }}</span></div></div>
              <div class="job-history-actions" @click.stop>
                <a-button v-if="['xhs', 'douyin'].includes(job.platform)" type="text" size="small" @click="handleBulkDownload(job)">下载媒体</a-button>
                <a-dropdown><a-button type="text" size="small" aria-label="更多任务操作">···</a-button><template #overlay><a-menu><a-menu-item v-if="['pending', 'running'].includes(job.status)" @click="handleCancel(job.id)">取消任务</a-menu-item><a-menu-item danger @click="handleDelete(job.id)">删除任务</a-menu-item></a-menu></template></a-dropdown>
              </div>
            </div>
          </div>
          <a-empty v-else description="暂无采集任务" :image-style="{ height: '36px' }" />
        </section>
      </aside>

      <main class="preview-column" aria-label="证据预览台">
        <section class="tool-surface content-surface preview-pane">
          <div class="surface-heading"><div><p class="eyebrow">selected crawl job</p><h2>帖子列表</h2></div><span class="result-count">{{ postTotal }} 条内容</span></div>
          <div class="filter-bar" aria-label="帖子筛选"><label class="filter-control-label" for="data-platform">平台</label><a-select id="data-platform" v-model:value="dataFilters.platform" allow-clear placeholder="全部平台" @change="handleDataFilterChange"><a-select-option v-for="platform in platforms" :key="platform.id" :value="platform.id">{{ platform.name }}</a-select-option></a-select><label class="filter-control-label" for="data-keyword">关键词</label><a-input id="data-keyword" v-model:value="dataFilters.keyword" allow-clear placeholder="筛选内容" @pressEnter="handleDataFilterChange" /><a-checkbox v-model:checked="dataFilters.has_media" @change="handleDataFilterChange">含媒体</a-checkbox><a-button @click="handleDataFilterChange">筛选</a-button></div>
          <div v-if="!selectedJob" class="empty-panel"><a-empty description="先从左侧选择一个采集任务" /></div>
          <div v-else-if="loadingData" class="empty-panel"><a-spin tip="正在读取任务内容" /></div>
          <div v-else-if="postData.length" class="post-list" role="listbox" aria-label="采集帖子">
            <button v-for="post in postData" :key="`${post.platform}:${post.post_id}`" type="button" class="post-row" :class="{ selected: selectedPost?.post_id === post.post_id && selectedPost?.platform === post.platform }" role="option" :aria-selected="selectedPost?.post_id === post.post_id && selectedPost?.platform === post.platform" @click="selectPost(post)"><span class="post-platform">{{ platformName(post.platform) }}</span><span class="post-row-body"><strong>{{ post.author_name || '未知作者' }}</strong><span class="post-snippet">{{ post.content || '无文本内容' }}</span><span class="post-meta">{{ formatDate(post.timestamp) }} · 赞 {{ post.likes ?? 0 }} · 转发 {{ post.reposts ?? 0 }}</span></span><span class="post-media-state" :class="{ active: post.media_urls?.length, ready: post.local_media?.available_count }">{{ post.local_media?.available_count ? `已下载 ${post.local_media.available_count}` : post.media_urls?.length ? '待下载' : '文本' }}</span></button>
          </div>
          <div v-else class="empty-panel"><a-empty description="当前任务没有符合条件的帖子" /></div>
          <div v-if="postTotal > dataPageSize" class="pagination-row"><a-pagination :current="dataPage" :page-size="dataPageSize" :total="postTotal" :show-size-changer="false" @change="handlePageChange" /></div>
        </section>

        <section class="tool-surface detail-surface preview-pane">
          <div class="surface-heading"><div><p class="eyebrow">evidence preview</p><h2>选中内容</h2></div><a-tag v-if="selectedPost" color="blue">{{ platformName(selectedPost.platform) }}</a-tag></div>
          <div v-if="!selectedPost" class="empty-panel detail-empty"><a-empty description="选择左侧帖子查看全文、评论和本地媒体" /></div>
          <div v-else class="post-detail">
            <div class="detail-meta-line"><strong>{{ selectedPost.author_name || '未知作者' }}</strong><span>{{ formatDate(selectedPost.timestamp) }}</span><a v-if="selectedPost.url" :href="selectedPost.url" target="_blank" rel="noopener noreferrer">打开原帖</a></div>
            <p class="post-full-text">{{ selectedPost.content || '无文本内容' }}</p>
            <div class="engagement-strip"><span><strong>{{ selectedPost.likes ?? 0 }}</strong> 点赞</span><span><strong>{{ selectedPost.reposts ?? 0 }}</strong> 转发</span><span><strong>{{ selectedPost.comments_count ?? 0 }}</strong> 评论</span></div>
            <div class="detail-section"><div class="detail-section-heading"><h3>媒体舞台</h3><span>仅显示本地已下载文件</span></div><div v-if="localMedia.length" class="media-stage-grid"><figure v-for="media in localMedia" :key="`${media.job_id}:${media.item_index}`" class="media-stage"><img v-if="media.media_type === 'image' && media.previewable && media.object_url" :src="media.object_url" :alt="`${selectedPost.author_name || '帖子'}的本地图片`" loading="lazy" /><video v-else-if="media.media_type === 'video' && media.previewable && media.object_url" :src="media.object_url" controls preload="metadata" /><div v-else class="media-unavailable">该文件格式暂不支持浏览器预览</div><figcaption>{{ media.filename }}<span v-if="!media.previewable"> · 不可预览</span></figcaption></figure></div><div v-else class="media-empty"><span>{{ selectedPost.media_urls?.length ? '已发现原帖媒体，但本地文件尚未下载。' : '这条帖子没有媒体附件。' }}</span><a-button v-if="selectedPost.media_urls?.length && canDownloadSelectedPost" type="primary" size="small" :loading="creatingDownload" @click="handleDownloadSelected">下载并预览</a-button><span v-else-if="selectedPost.media_urls?.length" class="muted-text">当前平台暂不支持本地媒体下载</span></div></div>
            <div class="detail-section"><div class="detail-section-heading"><h3>评论摘要</h3><span>最多显示 3 条</span></div><div v-if="loadingComments" class="inline-loading"><a-spin size="small" /> 正在读取评论</div><div v-else-if="comments.length" class="comment-list"><article v-for="comment in comments" :key="comment.comment_id" class="comment-row"><strong>{{ comment.author_name || '未知用户' }}</strong><p>{{ comment.content || '无文本内容' }}</p><time>{{ formatDate(comment.timestamp) }}</time></article></div><p v-else class="muted-text">当前任务没有可显示的评论摘要。</p></div>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import { cancelCrawlJob, createCrawlJob, createMediaDownloadJob, deleteCrawlJob, getMediaContentPath, getMediaDownloadJob, getPlatforms, getPostComments, getPostMedia, listCrawlJobs, queryCrawlData } from '@/api/crawl'
import { choosePrimaryKeyword, flattenKeywordGroups, parseJobSummary, readCrawlQuery, resetPreviewForJob, writeCrawlQuery } from '@/features/crawl/model'

interface PlatformOption { id: string; name: string; status: string; hint?: string }
interface KeywordGroup { id: string; name: string; keywords: string[]; draft: string; expanded: boolean }
interface CrawlJobItem { id: number; job_type: string; platform: string; status: string; progress: number; result_summary?: string | null; created_at: string }
interface PostItem { post_id: string; platform: string; author_name: string; author_id?: string; content: string; timestamp: string; url?: string; likes: number; reposts: number; comments_count?: number; media_urls?: string[]; local_media?: { available_count: number; types: Array<'image' | 'video'> } }
interface CommentItem { comment_id: string; author_name: string; content: string; timestamp: string }
interface LocalMediaItem { job_id: number; item_index: number; media_type: 'image' | 'video'; filename: string; content_type?: string | null; previewable: boolean; preview_url: string; status?: string; object_url?: string }

const route = useRoute(); const router = useRouter(); const pageActive = ref(false); const platforms = ref<PlatformOption[]>([]); const jobs = ref<CrawlJobItem[]>([]); const selectedJobId = ref<number | null>(null); const selectedPost = ref<PostItem | null>(null); const postData = ref<PostItem[]>([]); const postTotal = ref(0); const dataPage = ref(1); const dataPageSize = 20; const comments = ref<CommentItem[]>([]); const localMedia = ref<LocalMediaItem[]>([]); const loadingJobs = ref(false); const loadingData = ref(false); const loadingComments = ref(false); const creating = ref(false); const creatingDownload = ref(false); const postIdsInput = ref(''); const refreshTimer = ref<number | undefined>(); const postRequestGeneration = ref(0); const initialCrawlLoad = ref<Promise<void> | null>(null); const routeStateReady = ref(false); const objectUrls = new Set<string>()
const keywordGroups = ref<KeywordGroup[]>([{ id: 'group-1', name: '默认检索', keywords: [], draft: '', expanded: true }])
const crawlForm = reactive({ platform: 'weibo', event_id: '', source_keyword: '', max_posts: 50, max_comments_per_post: 200, crawl_comments: true, recursive_comments: true, enrich_author_profiles: false, comment_sort: 'none' as 'none' | 'like_count_desc' | 'reply_count_desc', execution_mode: 'local' as 'local' | 'queued' })
const dataFilters = reactive({ platform: undefined as string | undefined, keyword: '', has_media: false }); const executionModeOptions = [{ label: '本地后台', value: 'local' }, { label: '队列', value: 'queued' }]
const keywordOptions = computed(() => flattenKeywordGroups(keywordGroups.value)); const contentJobs = computed(() => jobs.value.filter((job) => job.job_type !== 'media_download')); const selectedJob = computed(() => contentJobs.value.find((job) => job.id === selectedJobId.value) || null); const selectedJobSummary = computed(() => parseJobSummary(selectedJob.value?.result_summary)); const canDownloadSelectedPost = computed(() => Boolean(selectedPost.value?.media_urls?.length && ['xhs', 'douyin'].includes(selectedPost.value.platform)))
function platformName(platform: string) { return platforms.value.find((item) => item.id === platform)?.name || platform }
function statusLabel(status: string) { return ({ pending: '等待中', running: '采集中', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[status] || status }
function statusColor(status: string) { return ({ pending: 'default', running: 'processing', completed: 'success', failed: 'error', cancelled: 'warning' } as Record<string, string>)[status] || 'default' }
function formatDate(value?: string) { if (!value) return '-'; return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function routeQueryParams() { const params = new URLSearchParams(); Object.entries(route.query).forEach(([key, value]) => { if (typeof value === 'string') params.set(key, value) }); return params }
function clearObjectUrls() { objectUrls.forEach((url) => URL.revokeObjectURL(url)); objectUrls.clear() }
function addKeywordGroup() { keywordGroups.value.push({ id: `group-${Date.now()}`, name: `分组 ${keywordGroups.value.length + 1}`, keywords: [], draft: '', expanded: true }) }
function removeKeywordGroup(id: string) { if (keywordGroups.value.length > 1) keywordGroups.value = keywordGroups.value.filter((group) => group.id !== id) }
function addKeyword(group: KeywordGroup) { const value = group.draft.trim(); if (value && !group.keywords.includes(value)) group.keywords.push(value); group.draft = '' }
function removeKeyword(group: KeywordGroup, keyword: string) { group.keywords = group.keywords.filter((item) => item !== keyword) }

async function handleCreateJob() { const keywords = flattenKeywordGroups(keywordGroups.value); const postIds = postIdsInput.value.split(/[\n,，]/).map((item) => item.trim()).filter((item) => /^https?:\/\//.test(item)); if (crawlForm.platform === 'news' && !postIds.length) { message.warning('新闻采集需要填写至少一条 http(s) 链接'); return }; if (crawlForm.platform !== 'news' && !keywords.length) { message.warning('社交平台采集需要填写至少一个关键词'); return }; creating.value = true; try { await createCrawlJob({ platform: crawlForm.platform, keywords, event_id: crawlForm.event_id.trim() || undefined, source_keyword: choosePrimaryKeyword(keywordGroups.value, crawlForm.source_keyword), post_ids: postIds, max_posts: crawlForm.max_posts, crawl_comments: crawlForm.crawl_comments, recursive_comments: crawlForm.crawl_comments && crawlForm.recursive_comments, enrich_author_profiles: crawlForm.enrich_author_profiles, comment_sort: crawlForm.comment_sort, max_comments_per_post: crawlForm.max_comments_per_post, execution_mode: crawlForm.execution_mode }); message.success('采集任务已启动'); await fetchJobs() } finally { creating.value = false } }
async function handleCancel(jobId: number) { await cancelCrawlJob(jobId); message.success('任务已取消'); await fetchJobs() }
async function handleDelete(jobId: number) { await deleteCrawlJob(jobId); if (selectedJobId.value === jobId) { selectedJobId.value = null; selectedPost.value = null; postData.value = []; comments.value = []; localMedia.value = [] }; message.success('任务已删除'); await fetchJobs() }
async function handleBulkDownload(job: CrawlJobItem) { if (!['xhs', 'douyin'].includes(job.platform)) { message.warning('当前平台暂不支持本地媒体下载'); return }; creatingDownload.value = true; try { const response = await createMediaDownloadJob({ platform: job.platform, media_types: ['video', 'image'] }) as { data?: CrawlJobItem }; message.success('媒体下载任务已启动'); await fetchJobs(); if (response.data?.id) await waitForMediaDownload(response.data.id) } finally { creatingDownload.value = false } }
async function handleDownloadSelected() { if (!selectedPost.value || !canDownloadSelectedPost.value) return; creatingDownload.value = true; try { const response = await createMediaDownloadJob({ platform: selectedPost.value.platform, post_ids: [selectedPost.value.post_id], media_types: ['video', 'image'] }) as { data?: CrawlJobItem }; message.success('当前帖子的媒体下载已启动'); if (response.data?.id) await waitForMediaDownload(response.data.id) } finally { creatingDownload.value = false } }
async function waitForMediaDownload(jobId: number) { for (let attempt = 0; attempt < 8; attempt += 1) { const response = await getMediaDownloadJob(jobId) as { data?: CrawlJobItem }; const status = response.data?.status; if (status === 'completed' || status === 'failed') break; await new Promise((resolve) => window.setTimeout(resolve, 1000)) }; if (selectedPost.value) await fetchPostMedia(selectedPost.value); await fetchJobs() }
async function selectJob(jobId: number) { const jobChanged = selectedJobId.value !== jobId; if (jobChanged) { const reset = resetPreviewForJob({ selectedJobId: selectedJobId.value, selectedPostId: selectedPost.value?.post_id || null, comments: comments.value, media: localMedia.value }, jobId); selectedJobId.value = reset.selectedJobId; selectedPost.value = null; comments.value = []; localMedia.value = []; clearObjectUrls(); dataPage.value = 1 }; await fetchData(jobChanged ? 1 : dataPage.value); syncUrl() }
async function selectPost(post: PostItem) { selectedPost.value = post; comments.value = []; localMedia.value = []; clearObjectUrls(); const generation = ++postRequestGeneration.value; loadingComments.value = true; try { const [commentResponse, mediaResponse] = await Promise.all([selectedJobId.value ? getPostComments(post.platform, post.post_id, { crawl_job_id: selectedJobId.value, limit: 3 }) : Promise.resolve({ data: { items: [] } }), getPostMedia(post.platform, post.post_id)]) as [{ data: { items: CommentItem[] } }, { data: { items: LocalMediaItem[] } }]; if (generation !== postRequestGeneration.value || selectedPost.value?.post_id !== post.post_id) return; comments.value = commentResponse.data.items || []; localMedia.value = (mediaResponse.data.items || []).map((media) => ({ ...media, status: 'ready' })); await loadMediaObjects(generation) } finally { if (generation === postRequestGeneration.value) loadingComments.value = false }; syncUrl() }
async function loadMediaObjects(generation: number) { const token = localStorage.getItem('access_token'); if (!token) return; for (const media of localMedia.value) { if (generation !== postRequestGeneration.value || !media.previewable) continue; const response = await fetch(getMediaContentPath(media.job_id, media.item_index), { headers: { Authorization: `Bearer ${token}` } }); if (!response.ok) { media.previewable = false; continue }; const objectUrl = URL.createObjectURL(await response.blob()); objectUrls.add(objectUrl); media.object_url = objectUrl } }
async function fetchPostMedia(post: PostItem) { const response = await getPostMedia(post.platform, post.post_id) as { data: { items: LocalMediaItem[] } }; localMedia.value = (response.data.items || []).map((media) => ({ ...media, status: 'ready' })); await loadMediaObjects(postRequestGeneration.value) }
async function fetchJobs() { if (!pageActive.value) return; loadingJobs.value = true; try { const response = await listCrawlJobs({ page: 1, page_size: 50 }) as { data: { items: CrawlJobItem[] } }; jobs.value = response.data.items || []; const queryJobId = readCrawlQuery(routeQueryParams()).jobId; const nextJob = contentJobs.value.find((job) => job.id === (selectedJobId.value || queryJobId)) || contentJobs.value[0]; if (nextJob) await selectJob(nextJob.id) } finally { loadingJobs.value = false } }
async function fetchData(page = 1) { if (!pageActive.value || !selectedJobId.value) { postData.value = []; postTotal.value = 0; return }; loadingData.value = true; dataPage.value = page; try { const response = await queryCrawlData({ crawl_job_id: selectedJobId.value, platform: dataFilters.platform, keyword: dataFilters.keyword.trim() || undefined, has_media: dataFilters.has_media || undefined, page, page_size: dataPageSize }) as { data: { items: PostItem[]; total: number } }; postData.value = response.data.items || []; postTotal.value = response.data.total || 0; if (selectedPost.value && !postData.value.some((post) => post.post_id === selectedPost.value?.post_id)) { selectedPost.value = null; comments.value = []; localMedia.value = [] } } finally { loadingData.value = false } }
function handleDataFilterChange() { void fetchData(1); syncUrl() }
function handlePageChange(page: number) { void fetchData(page) }
function syncUrl() { if (!pageActive.value || !routeStateReady.value) return; const query = writeCrawlQuery({ jobId: selectedJobId.value, postId: selectedPost.value?.post_id || null, platform: dataFilters.platform, keyword: dataFilters.keyword, hasMedia: dataFilters.has_media }); void router.replace({ query: Object.fromEntries(query.entries()) }) }
function hasActiveJobs() { return contentJobs.value.some((job) => job.status === 'pending' || job.status === 'running') }
function startRefreshTimer() { if (!pageActive.value || refreshTimer.value !== undefined) return; refreshTimer.value = window.setInterval(() => { if (pageActive.value && hasActiveJobs()) { void fetchJobs(); void fetchData(dataPage.value) } }, 5000) }
function stopRefreshTimers() { if (refreshTimer.value !== undefined) { window.clearInterval(refreshTimer.value); refreshTimer.value = undefined } }
function activateCrawlPage() { pageActive.value = true; startRefreshTimer(); if (!platforms.value.length) void initializeCrawlPage(); else void fetchJobs() }
function deactivateCrawlPage() { pageActive.value = false; stopRefreshTimers(); clearObjectUrls() }
async function initializeCrawlPage() { if (initialCrawlLoad.value) return initialCrawlLoad.value; const state = readCrawlQuery(routeQueryParams()); selectedJobId.value = state.jobId; dataFilters.platform = state.platform; dataFilters.keyword = state.keyword; dataFilters.has_media = state.hasMedia; const load = (async () => { const response = await getPlatforms() as { data: PlatformOption[] }; platforms.value = response.data || []; await fetchJobs(); routeStateReady.value = true; if (state.postId) { const post = postData.value.find((item) => item.post_id === state.postId); if (post) await selectPost(post) } })(); initialCrawlLoad.value = load; try { await load } finally { if (initialCrawlLoad.value === load) initialCrawlLoad.value = null } }
watch(keywordOptions, (keywords) => { if (!keywords.includes(crawlForm.source_keyword)) crawlForm.source_keyword = keywords[0] || '' }); watch(() => [selectedJobId.value, selectedPost.value?.post_id, dataFilters.platform, dataFilters.keyword, dataFilters.has_media], syncUrl)
onMounted(activateCrawlPage); onActivated(activateCrawlPage); onDeactivated(deactivateCrawlPage); onBeforeUnmount(deactivateCrawlPage)
</script>

<style scoped>
.crawl-page { --crawl-border: #e5e7eb; --crawl-muted: #64748b; --crawl-text: #1f2937; color: var(--crawl-text); }
.crawl-workbench { display: grid; grid-template-columns: minmax(300px, 5fr) minmax(0, 7fr); height: clamp(720px, calc(100dvh - 160px), 960px); min-height: 0; gap: 16px; align-items: stretch; }
.control-column { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.preview-column { display: grid; grid-template-rows: minmax(400px, 1.35fr) minmax(280px, 0.85fr); gap: 16px; min-width: 0; min-height: 0; overflow: hidden; }
.crawl-scroll-pane { min-height: 0; padding-right: 6px; overflow-y: auto; overscroll-behavior: contain; scrollbar-color: #aebdca transparent; scrollbar-gutter: stable; scrollbar-width: thin; }
.crawl-scroll-pane:focus-visible { outline: 3px solid #91caff; outline-offset: 2px; }
.crawl-scroll-pane::-webkit-scrollbar { width: 8px; }
.crawl-scroll-pane::-webkit-scrollbar-thumb { border: 2px solid #f5f7fa; border-radius: 999px; background: #aebdca; }
.crawl-scroll-pane::-webkit-scrollbar-thumb:hover { background: #7f94a8; }
.tool-surface { background: #fff; border: 1px solid var(--crawl-border); border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.preview-pane { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.surface-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
.compact-heading { margin-bottom: 12px; align-items: center; }
.surface-heading h2 { margin: 3px 0 0; font-size: 18px; line-height: 1.3; font-weight: 650; letter-spacing: 0; }
.eyebrow { margin: 0; color: #94a3b8; font-size: 11px; line-height: 1.2; letter-spacing: .08em; text-transform: uppercase; }
.surface-hint, .detail-section-heading span, .selected-job-caption, .muted-text { color: var(--crawl-muted); font-size: 13px; }
.request-form { display: grid; gap: 8px; }
.field-label, .filter-control-label { display: block; margin-top: 4px; color: #475569; font-size: 13px; font-weight: 600; }
.full-control { width: 100%; }
.field-pair { display: grid; grid-template-columns: 1.2fr .8fr; gap: 10px; }
.section-label-row, .detail-section-heading, .detail-meta-line, .filter-bar, .pagination-row, .media-empty { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.keyword-groups { display: grid; gap: 8px; }
.keyword-group { border: 1px solid var(--crawl-border); border-radius: 6px; overflow: hidden; }
.group-heading { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; }
.collapse-toggle { width: 24px; height: 24px; border: 0; background: transparent; color: #64748b; cursor: pointer; }
.collapse-chevron { display: inline-block; font-size: 19px; transform: rotate(0deg); transition: transform .16s ease; }
.collapse-chevron.expanded { transform: rotate(90deg); }
.group-name-input { flex: 1; }
.group-body { display: grid; gap: 8px; padding: 9px; }
.keyword-chip-list { display: flex; flex-wrap: wrap; gap: 5px; min-height: 24px; align-items: center; }
.advanced-options { border-top: 1px solid var(--crawl-border); margin-top: 4px; padding-top: 10px; }
.advanced-options summary { color: #475569; font-size: 13px; font-weight: 600; cursor: pointer; }
.advanced-grid { display: grid; gap: 8px; margin-top: 10px; }
.option-row { display: flex; align-items: center; justify-content: space-between; color: #475569; font-size: 13px; }
.task-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.task-metrics div { border-left: 2px solid #dbeafe; padding-left: 10px; }
.task-metrics strong { display: block; font-size: 22px; font-variant-numeric: tabular-nums; line-height: 1.1; }
.task-metrics span, .result-count { color: var(--crawl-muted); font-size: 12px; }
.selected-job-caption { margin: 10px 0 0; }
.job-history { display: grid; gap: 4px; }
.job-history-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; border: 1px solid transparent; border-radius: 6px; padding: 8px; cursor: pointer; }
.job-history-row:hover, .job-history-row.selected { border-color: #bfdbfe; background: #eff6ff; }
.job-history-main { display: flex; min-width: 0; align-items: center; gap: 9px; }
.job-platform-mark { display: grid; width: 28px; height: 28px; place-items: center; flex: 0 0 auto; border-radius: 6px; background: #e0f2fe; color: #0369a1; font-weight: 700; }
.job-history-copy { display: grid; min-width: 0; gap: 2px; }
.job-history-copy strong { font-size: 13px; }
.job-history-copy span { color: var(--crawl-muted); font-size: 11px; }
.job-history-actions { display: flex; align-items: center; gap: 2px; }
.filter-bar { justify-content: flex-start; flex-wrap: wrap; margin-bottom: 12px; }
.filter-bar :deep(.ant-select), .filter-bar :deep(.ant-input) { width: 150px; }
.post-list { display: grid; min-height: 0; gap: 4px; overflow-y: auto; overscroll-behavior: contain; scrollbar-color: #aebdca transparent; scrollbar-width: thin; }
.post-row { display: grid; grid-template-columns: 64px minmax(0, 1fr) auto; gap: 10px; width: 100%; border: 1px solid transparent; border-radius: 6px; padding: 10px; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.post-row:hover, .post-row.selected { border-color: #bfdbfe; background: #f8fbff; }
.post-row:focus-visible, .job-history-row:focus-visible, .collapse-toggle:focus-visible { outline: 2px solid #1677ff; outline-offset: 2px; }
.post-platform { color: #0369a1; font-size: 12px; font-weight: 650; }
.post-row-body { display: grid; min-width: 0; gap: 3px; }
.post-row-body strong { font-size: 13px; }
.post-snippet { overflow: hidden; color: #334155; font-size: 14px; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.post-meta { color: var(--crawl-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.post-media-state { align-self: start; color: #94a3b8; font-size: 12px; }
.post-media-state.active { color: #64748b; }
.post-media-state.ready { color: #15803d; font-weight: 650; }
.empty-panel { display: grid; min-height: 170px; place-items: center; }
.pagination-row { justify-content: flex-end; margin-top: 12px; }
.detail-empty { min-height: 240px; }
.detail-meta-line { justify-content: flex-start; flex-wrap: wrap; color: var(--crawl-muted); font-size: 13px; }
.detail-meta-line strong { color: var(--crawl-text); }
.detail-meta-line a { color: #1677ff; }
.post-full-text { margin: 16px 0; white-space: pre-wrap; overflow-wrap: anywhere; color: #1e293b; font-size: 15px; line-height: 1.75; }
.engagement-strip { display: flex; flex-wrap: wrap; gap: 22px; border-top: 1px solid var(--crawl-border); border-bottom: 1px solid var(--crawl-border); padding: 10px 0; color: var(--crawl-muted); font-size: 13px; }
.engagement-strip strong { color: var(--crawl-text); font-variant-numeric: tabular-nums; }
.detail-section { margin-top: 20px; }
.detail-section-heading { justify-content: flex-start; margin-bottom: 10px; }
.detail-section-heading h3 { margin: 0; font-size: 15px; }
.media-stage-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.media-stage { margin: 0; overflow: hidden; border: 1px solid var(--crawl-border); border-radius: 6px; background: #f8fafc; }
.media-stage img, .media-stage video { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: #0f172a; }
.media-stage figcaption { overflow: hidden; padding: 7px 9px; color: #475569; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.media-unavailable { display: grid; aspect-ratio: 16 / 9; place-items: center; padding: 16px; color: #64748b; font-size: 13px; text-align: center; }
.media-empty { justify-content: flex-start; flex-wrap: wrap; border: 1px dashed #cbd5e1; border-radius: 6px; padding: 12px; color: #64748b; font-size: 13px; }
.post-detail { min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding-right: 4px; }
.comment-list { display: grid; gap: 8px; }
.comment-row { border-left: 2px solid #e2e8f0; padding-left: 10px; }
.comment-row strong { font-size: 13px; }
.comment-row p { margin: 3px 0; color: #334155; font-size: 13px; line-height: 1.55; }
.comment-row time { color: #94a3b8; font-size: 11px; }
.inline-loading { display: flex; align-items: center; gap: 8px; color: var(--crawl-muted); font-size: 13px; }
@media (max-width: 1100px) { .crawl-workbench { grid-template-columns: 1fr; height: auto; } .crawl-scroll-pane { overflow-y: visible; padding-right: 0; } .control-column { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; } .request-surface, .history-surface { grid-column: 1 / -1; } .preview-column { min-height: 680px; } }
@media (max-width: 720px) { .control-column, .preview-column { display: flex; min-height: 0; overflow: visible; } .preview-pane, .post-list, .post-detail { min-height: auto; overflow: visible; } .tool-surface { padding: 13px; } .field-pair { grid-template-columns: 1fr; } .surface-heading { margin-bottom: 12px; } .post-row { grid-template-columns: 52px minmax(0, 1fr); } .post-media-state { display: none; } .filter-bar { align-items: stretch; } .filter-bar :deep(.ant-select), .filter-bar :deep(.ant-input), .filter-bar :deep(.ant-btn) { width: 100%; } .filter-control-label { width: 100%; margin: 0; } .media-stage-grid { grid-template-columns: 1fr; } .detail-meta-line { align-items: flex-start; flex-direction: column; gap: 4px; } }
</style>
