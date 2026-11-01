import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const router = readFileSync(resolve(frontendRoot, 'src/router/index.ts'), 'utf8')
const layout = readFileSync(resolve(frontendRoot, 'src/components/layout/BasicLayout.vue'), 'utf8')
const pagePath = resolve(frontendRoot, 'src/views/semantic-analysis/index.vue')
const riskPath = resolve(frontendRoot, 'src/views/risk/index.vue')
const riskTabsPath = resolve(frontendRoot, 'src/views/risk/RiskSectionTabs.vue')

test('provides one linked semantic evidence workspace and preserves legacy links', () => {
  assert.ok(existsSync(pagePath), 'semantic analysis page must exist')
  assert.ok(existsSync(riskTabsPath), 'risk section tabs must exist')
  const page = readFileSync(pagePath, 'utf8')
  const riskView = readFileSync(riskPath, 'utf8')
  const riskTabs = readFileSync(riskTabsPath, 'utf8')

  assert.match(router, /path: 'risk\/semantic-evidence'/)
  assert.match(router, /component: \(\) => import\('\@\/views\/semantic-analysis\/index\.vue'\)/)
  for (const legacyPath of [
    'risk/semantic-clusters',
    'risk/named-entities',
    'risk/temporal-change',
    'risk/verifiable-content',
  ]) {
    assert.match(router, new RegExp(`path: '${legacyPath}'`))
  }
  assert.match(router, /redirect: \(to\) => \(\{ path: '\/risk\/semantic-evidence', query: to\.query \}\)/)
  assert.doesNotMatch(layout, /path: '\/risk\/semantic-evidence'/)
  assert.match(page, /getSemanticWorkspace\(requestedEventId/)
  assert.doesNotMatch(page, /getEventSemantic\(requestedEventId\)/)
  assert.doesNotMatch(page, /getSemanticPageProjection/)
  assert.doesNotMatch(page, /defineProps<\{ kind/)
  assert.match(page, /<APagination/)
  assert.match(page, /name="semantic-event-id"/)
  assert.match(page, /autocomplete="off"/)
  assert.match(page, /RiskSectionTabs/)
  assert.match(page, /<router-link class="review-link" :to="reviewDestination">查看事件研判<\/router-link>/)
  assert.match(page, /class="time-strip" role="group" :aria-label="temporalAriaLabel"/)
  assert.doesNotMatch(page, /class="time-strip" role="img"/)
  for (const label of ['语义聚类', '命名实体', '时间变化', '可核验内容']) {
    assert.match(page, new RegExp(label))
  }
  assert.match(riskView, /RiskSectionTabs/)
  assert.match(riskTabs, /path: '\/risk\/semantic-evidence'/)
  assert.doesNotMatch(riskTabs, /semantic-clusters|named-entities|temporal-change|verifiable-content/)
  assert.match(riskTabs, /event_id/)
})

test('keeps verifiable content traceable without presenting it as a truth verdict', () => {
  const page = readFileSync(pagePath, 'utf8')

  assert.match(page, /可核验仅表示可定位回事件快照中的原始内容和引用，不等于事实已被证实。/)
  assert.match(page, /record\.evidence_ref/)
  assert.match(page, /record\.source_url/)
  assert.match(page, /record\.text/)
})

test('defers evidence word-cloud layout until the compact workspace content can paint', () => {
  const page = readFileSync(pagePath, 'utf8')

  assert.match(page, /const showKeywordCloud = ref\(false\)/)
  assert.match(page, /v-if="showKeywordCloud && keywordCloud\.length"/)
  assert.match(page, /function scheduleKeywordCloud\(\)/)
  assert.match(page, /requestAnimationFrame\(\(\) => \{[\s\S]*?requestAnimationFrame/)
  assert.match(page, /watch\(keywordRows, scheduleKeywordCloud/)
})

test('loads dense workspace controls with the route and keeps evidence panels compact', () => {
  const page = readFileSync(pagePath, 'utf8')

  assert.match(page, /from '@\/ui\/semanticWorkspaceControls'/)
  assert.match(page, /import SemanticKeywordCloud from '@\/components\/SemanticKeywordCloud\.vue'/)
  assert.doesNotMatch(page, /defineAsyncComponent/)
  assert.match(page, /\.workspace-grid \{ display: grid; align-items: start;/)
  assert.doesNotMatch(page, /border-top-color:/)
})

test('aligns paired evidence panels and removes the community slice', () => {
  const page = readFileSync(pagePath, 'utf8')

  assert.match(page, /\.overview-grid, \.ledger-grid, \.timeline-grid \{ align-items: stretch; \}/)
  assert.doesNotMatch(page, /communityRows|community-panel|协同群体|群体语义切片/)
})

test('shows the selected event audit and persisted governance references on the homepage', () => {
  const dashboard = readFileSync(resolve(frontendRoot, 'src/views/dashboard/index.vue'), 'utf8')

  assert.match(dashboard, /本案审计与治理参考/)
  assert.match(dashboard, /loadCurrentCaseAudit\(\)/)
  assert.match(dashboard, /getReviewAudit\(matched\.case_id\)/)
  assert.match(dashboard, /caseAudit\.governance\.references/)
  assert.match(dashboard, /当前事件未记录复核审计/)
})
