<template>
  <a-card class="evidence-pane" size="small" :bordered="false">
    <template v-if="hasEvidence">
      <a-row :gutter="[16, 16]" class="evidence-layout">
        <a-col :xs="24" :lg="15">
          <section class="evidence-panel recent-panel">
            <header class="panel-header">
              <div>
                <div class="section-title">近期推文</div>
                <div class="section-subtitle">点击推文可筛选右侧关联内容</div>
              </div>
              <a-tag color="blue">{{ allPosts.length }} 条</a-tag>
            </header>

            <div class="tweet-list">
              <article
                v-for="post in visibleAllPosts"
                :key="post.post_id || post.excerpt"
                :class="['tweet-item', { active: isActivePost(post) }]"
                @click="selectForFiltering(post)"
              >
                <div class="tweet-meta">
                  <span>帖子 {{ post.post_id || '未知' }}</span>
                  <span v-if="post.authorName">作者 {{ post.authorName }}</span>
                  <span>匹配 {{ percentText(post.claimScore) }}</span>
                </div>
                <p class="tweet-text">{{ post.excerpt || '暂无文本' }}</p>
                <div class="tweet-footer">
                  <div class="evidence-tags">
                    <a-tag color="blue">{{ claimDisplayLabel(post.primaryClaimId) }}</a-tag>
                    <a-tag :color="post.stanceAbstain ? 'orange' : 'green'">
                      {{ stanceDisplayLabel(post.stanceLabel) }}
                    </a-tag>
                    <a-tag :color="post.harmLabel === 'harmful' ? 'red' : 'default'">
                      {{ harmDisplayLabel(post.harmLabel) }}
                    </a-tag>
                  </div>
                  <a-space size="small" @click.stop>
                    <a-button size="small" @click="openDetail(post)">详情</a-button>
                    <a-button size="small" type="link" class="select-button" @click="$emit('select-post', post)">
                      研判
                    </a-button>
                  </a-space>
                </div>
              </article>
            </div>

            <div v-if="hasMorePosts" class="more-actions">
              <a-button size="small" @click="visibleLimit += 30">查看更多</a-button>
            </div>
          </section>
        </a-col>

        <a-col :xs="24" :lg="9">
          <section class="evidence-panel side-panel danger-panel">
            <header class="panel-header compact">
              <div>
                <div class="section-title">可疑内容</div>
                <div class="section-subtitle">{{ rightPanelHint }}</div>
              </div>
              <a-tag color="red">{{ filteredSupportPosts.length }} 条</a-tag>
            </header>
            <div v-if="filteredSupportPosts.length" class="evidence-list">
              <article
                v-for="post in filteredSupportPosts"
                :key="post.post_id || post.excerpt"
                class="evidence-item evidence-item-danger"
                @click="$emit('select-post', post)"
              >
                <div class="evidence-card">
                  <div class="evidence-meta">
                    <span>帖子 {{ post.post_id || '未知' }}</span>
                    <span>态度 {{ stanceDisplayLabel(post.stanceLabel) }}</span>
                    <span>匹配 {{ percentText(post.claimScore) }}</span>
                  </div>
                  <p class="evidence-text">{{ post.excerpt || '暂无文本' }}</p>
                  <div class="evidence-tags">
                    <a-tag color="red">{{ harmDisplayLabel(post.harmLabel) }}</a-tag>
                    <a-tag color="volcano">{{ harmTypeDisplayLabel(post.primaryType) }}</a-tag>
                    <a-tag v-if="post.stanceAbstain" color="orange">需要核验</a-tag>
                  </div>
                </div>
              </article>
            </div>
            <a-empty v-else description="暂无可疑内容" />
          </section>

          <section class="evidence-panel side-panel safe-panel">
            <header class="panel-header compact">
              <div>
                <div class="section-title">反驳内容</div>
                <div class="section-subtitle">{{ rightPanelHint }}</div>
              </div>
              <a-tag color="green">{{ filteredDenyPosts.length }} 条</a-tag>
            </header>
            <div v-if="filteredDenyPosts.length" class="evidence-list">
              <article
                v-for="post in filteredDenyPosts"
                :key="post.post_id || post.excerpt"
                class="evidence-item evidence-item-safe"
                @click="$emit('select-post', post)"
              >
                <div class="evidence-card">
                  <div class="evidence-meta">
                    <span>帖子 {{ post.post_id || '未知' }}</span>
                    <span>态度 {{ stanceDisplayLabel(post.stanceLabel) }}</span>
                    <span>匹配 {{ percentText(post.claimScore) }}</span>
                  </div>
                  <p class="evidence-text">{{ post.excerpt || '暂无文本' }}</p>
                  <div class="evidence-tags">
                    <a-tag color="green">{{ harmDisplayLabel(post.harmLabel) }}</a-tag>
                    <a-tag color="blue">{{ claimDisplayLabel(post.primaryClaimId) }}</a-tag>
                    <a-tag v-if="post.stanceAbstain" color="orange">需要核验</a-tag>
                  </div>
                </div>
              </article>
            </div>
            <a-empty v-else description="暂无反驳内容" />
          </section>
        </a-col>
      </a-row>

      <a-drawer
        v-model:open="detailOpen"
        title="推文详情"
        placement="right"
        width="560"
        class="tweet-detail-drawer"
      >
        <template v-if="detailPost">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item label="帖子编号">{{ detailPost.post_id || '未知' }}</a-descriptions-item>
            <a-descriptions-item label="平台">{{ platformDisplayLabel(detailPost.platformName) }}</a-descriptions-item>
            <a-descriptions-item label="作者">{{ detailPost.authorName || '未知' }}</a-descriptions-item>
            <a-descriptions-item label="匹配度">{{ percentText(detailPost.claimScore) }}</a-descriptions-item>
            <a-descriptions-item label="态度">{{ stanceDisplayLabel(detailPost.stanceLabel) }}</a-descriptions-item>
            <a-descriptions-item label="危害判断">{{ harmDisplayLabel(detailPost.harmLabel) }}</a-descriptions-item>
            <a-descriptions-item label="危害类型">{{ harmTypeDisplayLabel(detailPost.primaryType) }}</a-descriptions-item>
            <a-descriptions-item label="置信度">{{ percentText(detailPost.harmScore) }}</a-descriptions-item>
          </a-descriptions>

          <section class="detail-block">
            <div class="detail-title">完整内容</div>
            <p class="detail-text">{{ detailPost.excerpt || '暂无文本' }}</p>
          </section>

          <section class="detail-block">
            <div class="detail-title">关联线索</div>
            <p class="detail-text">{{ detailPost.primaryClaimText || claimDisplayLabel(detailPost.primaryClaimId) }}</p>
          </section>

          <section class="detail-block">
            <div class="detail-title">可用信息摘要</div>
            <div class="detail-tags">
              <a-tag color="blue">{{ claimDisplayLabel(detailPost.primaryClaimId) }}</a-tag>
              <a-tag :color="detailPost.stanceAbstain ? 'orange' : 'green'">
                {{ stanceDisplayLabel(detailPost.stanceLabel) }}
              </a-tag>
              <a-tag :color="detailPost.harmLabel === 'harmful' ? 'red' : 'default'">
                {{ harmDisplayLabel(detailPost.harmLabel) }}
              </a-tag>
              <a-tag v-if="detailPost.stanceAbstain" color="orange">需要人工核验</a-tag>
            </div>
          </section>

          <a-button type="primary" block @click="$emit('select-post', detailPost)">进入研判</a-button>
        </template>
      </a-drawer>
    </template>
    <a-empty v-else description="暂无数据" />
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  allPosts: any[]
  supportPosts: any[]
  denyPosts: any[]
}>()

defineEmits<{
  (event: 'select-post', post: any): void
}>()

const visibleLimit = ref(30)
const activePost = ref<any | null>(null)
const detailPost = ref<any | null>(null)
const detailOpen = ref(false)

const visibleAllPosts = computed(() => props.allPosts.slice(0, visibleLimit.value))
const hasMorePosts = computed(() => props.allPosts.length > visibleLimit.value)
const hasEvidence = computed(() => props.allPosts.length > 0 || props.supportPosts.length > 0 || props.denyPosts.length > 0)
const activeClaimId = computed(() => String(activePost.value?.primaryClaimId || '').trim())
const filteredSupportPosts = computed(() => filterRelatedPosts(props.supportPosts))
const filteredDenyPosts = computed(() => filterRelatedPosts(props.denyPosts))
const rightPanelHint = computed(() => activeClaimId.value ? '已按选中推文筛选' : '显示当前候选内容')

watch(() => props.allPosts, () => {
  visibleLimit.value = 30
  if (!activePost.value) return
  const stillExists = props.allPosts.some((post) => samePost(post, activePost.value))
  if (!stillExists) activePost.value = null
})

const stanceLabels: Record<string, string> = {
  support: '支持传播',
  deny: '反驳',
  query: '求证',
  neutral: '中性',
  uncertain: '需要核验',
  unlinked: '待关联',
}

const harmLabels: Record<string, string> = {
  harmful: '有害',
  non_harmful: '正常',
  uncertain: '需要核验',
}

const harmTypeLabels: Record<string, string> = {
  misinformation: '虚假信息',
  hate: '仇恨攻击',
  harassment: '骚扰',
  incitement: '煽动',
  amplification: '放大传播',
  spam: '垃圾传播',
  none: '暂无类型',
}

function selectForFiltering(post: any) {
  activePost.value = samePost(activePost.value, post) ? null : post
}

function openDetail(post: any) {
  detailPost.value = post
  detailOpen.value = true
}

function filterRelatedPosts(rows: any[]) {
  if (!activeClaimId.value) return rows
  const related = rows.filter((post) => String(post?.primaryClaimId || '').trim() === activeClaimId.value)
  return related.length ? related : rows
}

function isActivePost(post: any) {
  return samePost(activePost.value, post)
}

function samePost(left: any, right: any) {
  if (!left || !right) return false
  const leftId = String(left?.post_id || '').trim()
  const rightId = String(right?.post_id || '').trim()
  if (leftId && rightId) return leftId === rightId
  return String(left?.excerpt || '') === String(right?.excerpt || '')
}

function stanceDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (stanceLabels[key] || '需要核验') : '待关联'
}

function harmDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (harmLabels[key] || '需要核验') : '需要核验'
}

function harmTypeDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim()
  return key ? (harmTypeLabels[key] || '其他类型') : '暂无类型'
}

function platformDisplayLabel(value: string | undefined) {
  const key = String(value || '').trim().toLowerCase()
  if (!key) return '未知'
  if (key.includes('weibo')) return '微博'
  if (key.includes('twitter') || key === 'x') return 'X'
  if (key.includes('douyin')) return '抖音'
  if (key.includes('xiaohongshu') || key.includes('xhs')) return '小红书'
  return String(value)
}

function claimDisplayLabel(value: string | undefined) {
  const text = String(value || '').trim()
  if (!text) return '待关联'
  return text.replace(/^claim[-_]/i, '线索-')
}

function percentText(value: number | undefined) {
  if (typeof value !== 'number') return '待核验'
  return `${(value * 100).toFixed(1)}%`
}
</script>

<style scoped>
.evidence-pane {
  border-radius: 18px;
}

.evidence-layout {
  align-items: stretch;
}

.evidence-panel {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 18px;
  box-shadow: 0 14px 36px rgb(31 45 61 / 7%);
  padding: 16px;
}

.recent-panel {
  height: 100%;
}

.side-panel + .side-panel {
  margin-top: 16px;
}

.side-panel :deep(.ant-empty) {
  margin: 18px 0 10px;
}

.side-panel :deep(.ant-empty-image) {
  height: 72px;
}

.panel-header {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  margin-bottom: 14px;
}

.panel-header.compact {
  margin-bottom: 12px;
}

.section-title {
  color: #262626;
  font-size: 16px;
  font-weight: 700;
}

.section-subtitle {
  color: #8c8c8c;
  font-size: 12px;
  margin-top: 4px;
}

.tweet-list,
.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tweet-item {
  background: linear-gradient(180deg, #fff, #f8fbff);
  border: 1px solid #edf4ff;
  border-radius: 16px;
  cursor: pointer;
  padding: 14px 16px;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
}

.tweet-item:hover,
.tweet-item.active {
  border-color: #4096ff;
  box-shadow: 0 10px 28px rgb(24 144 255 / 12%);
  transform: translateY(-1px);
}

.tweet-item.active {
  background: linear-gradient(180deg, #f0f7ff, #fff);
}

.tweet-meta,
.evidence-meta {
  color: #8c8c8c;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 10px;
  margin-bottom: 8px;
}

.tweet-text,
.evidence-text {
  color: #262626;
  line-height: 1.7;
  margin: 0 0 10px;
}

.tweet-text {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  overflow: hidden;
}

.tweet-footer {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
}

.evidence-tags,
.detail-tags {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
  row-gap: 8px;
}

.select-button {
  padding: 0;
}

.evidence-item {
  cursor: pointer;
}

.evidence-card {
  border: 1px solid #f5f5f5;
  border-radius: 14px;
  padding: 12px 14px;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
}

.danger-panel .evidence-card {
  background: linear-gradient(180deg, #fff, #fff8f7);
}

.safe-panel .evidence-card {
  background: linear-gradient(180deg, #fff, #f8fff9);
}

.evidence-item:hover .evidence-card {
  border-color: #91caff;
  box-shadow: 0 10px 28px rgb(24 144 255 / 12%);
  transform: translateY(-1px);
}

.more-actions {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

.detail-block {
  margin-top: 18px;
}

.detail-title {
  color: #262626;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
}

.detail-text {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  color: #262626;
  line-height: 1.8;
  margin: 0;
  padding: 12px;
  white-space: pre-wrap;
}

@media (max-width: 991px) {
  .recent-panel {
    height: auto;
  }
}
</style>
