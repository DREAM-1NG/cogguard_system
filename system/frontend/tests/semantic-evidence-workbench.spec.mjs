import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const modelPath = resolve(frontendRoot, 'src/features/semantic-evidence/model.ts')
const layoutPath = resolve(frontendRoot, 'src/components/layout/BasicLayout.vue')
const workbenchPath = resolve(frontendRoot, 'src/components/SemanticEvidenceWorkbench.vue')
const keywordCloudPath = resolve(frontendRoot, 'src/components/SemanticKeywordCloud.vue')

function loadModel() {
  assert.ok(existsSync(modelPath), 'Semantic evidence model must exist')
  const compiled = ts.transpileModule(readFileSync(modelPath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  const module = { exports: {} }
  new Function('module', 'exports', compiled)(module, module.exports)
  return module.exports
}

function semanticRecord(overrides = {}) {
  return {
    id: 'post-1',
    layer: 'posts',
    platform: 'weibo',
    date: '2026-08-14',
    keywords: ['特朗普', '访问'],
    topics: ['访问议程'],
    sentiment: 'negative',
    stance: 'contradiction',
    entities: [{ key: 'PER:特朗普', text: '特朗普', label: 'PER' }],
    ...overrides,
  }
}

test('intersects semantic dimensions without manufacturing a match', () => {
  const { createSemanticFilters, filterSemanticRecords } = loadModel()
  const records = [
    semanticRecord(),
    semanticRecord({
      id: 'comment-1',
      layer: 'comments',
      platform: 'xhs',
      keywords: ['特朗普'],
      topics: ['出访反应'],
      sentiment: 'positive',
      stance: 'entailment',
    }),
  ]
  const filters = createSemanticFilters()
  filters.keyword = '特朗普'
  filters.sentiment = 'negative'
  filters.platforms = ['weibo']

  assert.deepEqual(filterSemanticRecords(records, filters).map((record) => record.id), ['post-1'])
})

test('formats non-zero semantic distribution segments without rounding them to zero', () => {
  const { formatDistributionPercent } = loadModel()

  assert.equal(formatDistributionPercent(0, 14_491), '0')
  assert.equal(formatDistributionPercent(1, 20_000), '<0.01')
  assert.equal(formatDistributionPercent(4, 14_491), '0.03')
  assert.equal(formatDistributionPercent(52, 14_773), '0.35')
  assert.equal(formatDistributionPercent(28, 52), '54')
})

test('builds a stable top-fifty keyword cloud with bounded logarithmic sizes', () => {
  const { buildKeywordCloud } = loadModel()
  const records = Array.from({ length: 90 }, (_, index) => semanticRecord({
    id: `post-${index}`,
    keywords: index < 20 ? ['高频词'] : [`词${index.toString().padStart(2, '0')}`],
  }))

  const cloud = buildKeywordCloud(records)

  assert.equal(cloud.length, 50)
  assert.deepEqual(cloud[0], { term: '高频词', count: 20, fontSize: 40 })
  assert.equal(cloud.at(-1)?.fontSize, 12)
  assert.ok(cloud.every((item) => item.fontSize >= 12 && item.fontSize <= 40))
})

test('places keyword cloud terms deterministically with mixed angles and no overlapping bounds', () => {
  const { layoutKeywordCloud } = loadModel()
  const items = [
    { term: '核心主张', count: 90, fontSize: 34 },
    { term: '传播路径', count: 72, fontSize: 31 },
    { term: '协同群体', count: 56, fontSize: 28 },
    { term: '权威来源', count: 43, fontSize: 25 },
    { term: '特朗普', count: 37, fontSize: 23 },
    { term: '情感态度', count: 29, fontSize: 21 },
    { term: '证据矩阵', count: 18, fontSize: 18 },
    { term: '跨平台', count: 12, fontSize: 16 },
  ]

  const placements = layoutKeywordCloud(items, 620, 320)

  assert.deepEqual(layoutKeywordCloud(items, 620, 320), placements)
  assert.equal(placements.length, items.length)
  assert.ok(placements.some((item) => item.rotation !== 0))
  assert.ok(placements.every((item) => item.left >= 0 && item.top >= 0 && item.right <= 620 && item.bottom <= 320))
  assert.ok(placements.every((item, index) => placements.slice(index + 1).every((other) => (
    item.right <= other.left || other.right <= item.left || item.bottom <= other.top || other.bottom <= item.top
  ))))
  assert.ok(Math.max(...placements.map((item) => item.right)) - Math.min(...placements.map((item) => item.left)) >= 220)
  assert.ok(Math.max(...placements.map((item) => item.bottom)) - Math.min(...placements.map((item) => item.top)) >= 130)
})

test('keeps fifty realistic Chinese keywords inside the cloud without overlap', () => {
  const { layoutKeywordCloud } = loadModel()
  const terms = [
    '繁荣昌盛', '中国特色社会主义', '特朗普访华', '国际关系', '中美关系',
    '核心主张', '权威来源', '外交政策', '传播路径', '协同群体',
    '经济合作', '和平发展', '国家安全', '时事热点', '媒体报道',
    '全球治理', '文化交流', '访问计划', '多边主义', '公共舆论',
    '国际社会', '贸易关税', '社会稳定', '区域合作', '战略伙伴',
    '新闻发布', '官方回应', '历史进程', '经济发展', '中国人民',
    '世界和平', '外交部长', '国际秩序', '舆情分析', '证据矩阵',
    '风险研判', '情感态度', '官方媒体', '关键证据', '事实核查',
    '议题设置', '影响范围', '评论观点', '主帖内容', '传播节点',
    '网络关系', '数据来源', '分析结果', '政策建议', '平台动态',
  ]
  const items = terms.map((term, index) => ({
    term,
    count: 50 - index,
    fontSize: 12 + Math.round(((50 - index) / 50) * 28),
  }))

  const placements = layoutKeywordCloud(items, 680, 520)

  assert.equal(placements.length, items.length)
  assert.ok(placements.every((item, index) => placements.slice(index + 1).every((other) => (
    item.right <= other.left || other.right <= item.left || item.bottom <= other.top || other.bottom <= item.top
  ))))
})

test('paginates filtered semantic rows and resets invalid pages to the first page', () => {
  const { paginateSemanticRecords } = loadModel()
  const records = Array.from({ length: 21 }, (_, index) => semanticRecord({ id: `post-${index}` }))

  assert.deepEqual(paginateSemanticRecords(records, 2, 20).items.map((record) => record.id), ['post-20'])
  assert.equal(paginateSemanticRecords(records, 9, 20).page, 1)
})

test('keeps the risk workbench readable on a phone without removing navigation', () => {
  const layout = readFileSync(layoutPath, 'utf8')
  const workbench = readFileSync(workbenchPath, 'utf8')

  assert.match(layout, /<a-drawer\s+v-model:open="mobileNavigationOpen"/)
  assert.match(layout, /class="mobile-menu-button"/)
  assert.match(layout, /@media \(max-width: 720px\) \{[\s\S]*?:deep\(\.ant-layout-sider\)[\s\S]*?display: none/)
  assert.match(layout, /@media \(max-width: 720px\) \{[\s\S]*?\.app-content \{[\s\S]*?margin: 0[\s\S]*?padding: 16px 12px 24px/)
  assert.match(workbench, /@media \(max-width: 720px\) \{[\s\S]*?\.workbench-toolbar,[\s\S]*?align-items: flex-start/)
  assert.match(workbench, /\.semantic-matrix-scroll \{[\s\S]*?overflow-x: auto/)
  assert.match(workbench, /\.semantic-matrix-table \{[\s\S]*?min-width: 0/)
  assert.match(workbench, /\.semantic-matrix-table td::before \{[\s\S]*?content: attr\(data-label\)/)
})

test('keeps multi-value semantic evidence compact inside mobile record fields', () => {
  const workbench = readFileSync(workbenchPath, 'utf8')

  assert.match(workbench, /class="matrix-value-list"/)
  assert.match(workbench, /\.matrix-value-list \{[\s\S]*?display: flex/)
  assert.match(workbench, /\.matrix-value-list \{[\s\S]*?flex-wrap: wrap/)
})

test('keeps the entity ledger focused until an analyst expands all entity types', () => {
  const workbench = readFileSync(workbenchPath, 'utf8')

  assert.match(workbench, /const DEFAULT_ENTITY_GROUP_LIMIT = 3/)
  assert.match(workbench, /const visibleEntityGroups = computed\(\(\) =>/)
  assert.match(workbench, /entityGroups\.value\.slice\(0, DEFAULT_ENTITY_GROUP_LIMIT\)/)
  assert.match(workbench, /v-for="group in visibleEntityGroups"/)
  assert.match(workbench, /class="entity-expand-button"/)
  assert.match(workbench, /:aria-expanded="entityGroupsExpanded"/)
  assert.match(workbench, /entityGroupsExpanded \? '收起' : '展开'/)
  assert.doesNotMatch(workbench, /展开全部|收起为前三类/)
})

test('keeps semantic evidence numbers stable and supporting text readable', () => {
  const workbench = readFileSync(workbenchPath, 'utf8')
  assert.match(workbench, /\.semantic-workbench \{[\s\S]*?font-variant-numeric: tabular-nums/)
  assert.match(workbench, /\.toolbar-label,[^}]*font-size: 14px/)
  assert.match(workbench, /\.entity-type \{[^}]*font-size: 13px/)
  assert.match(workbench, /\.time-column \{[^}]*font-size: 13px/)
})

test('uses Chinese semantic labels and aligned visual sections for the evidence workbench', () => {
  const layout = readFileSync(workbenchPath, 'utf8')
  const keywordCloud = readFileSync(keywordCloudPath, 'utf8')
  const model = loadModel()

  assert.equal(model.displaySemanticLabel('sentiment', 'positive'), '正向')
  assert.equal(model.displaySemanticLabel('sentiment', 'negative'), '负向')
  assert.equal(model.displaySemanticLabel('stance', 'entailment'), '支持')
  assert.equal(model.displaySemanticLabel('stance', 'contradiction'), '反对')
  assert.equal(model.displaySemanticLabel('stance', 'neutral'), '中立')
  assert.match(layout, /conic-gradient/)
  assert.match(layout, /class="semantic-analysis-grid semantic-ledger-grid"/)
  assert.match(layout, /class="distribution-donut"/)
  assert.match(keywordCloud, /<svg/)
  assert.match(keywordCloud, /word-cloud-canvas/)
  assert.match(keywordCloud, /ResizeObserver/)
  assert.doesNotMatch(keywordCloud, /grid-template-columns/)
})
