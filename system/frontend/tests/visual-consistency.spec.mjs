import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const layout = readFileSync(resolve(frontendRoot, 'src/components/layout/BasicLayout.vue'), 'utf8')
const router = readFileSync(resolve(frontendRoot, 'src/router/index.ts'), 'utf8')
const risk = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')
const semantic = readFileSync(resolve(frontendRoot, 'src/components/SemanticEvidenceWorkbench.vue'), 'utf8')
const semanticPage = readFileSync(resolve(frontendRoot, 'src/views/semantic-analysis/index.vue'), 'utf8')
const propagation = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')
const coordination = readFileSync(resolve(frontendRoot, 'src/views/coordination/index.vue'), 'utf8')
const graph = readFileSync(resolve(frontendRoot, 'src/views/coordination/CoordinationGraph3D.vue'), 'utf8')
const dashboard = readFileSync(resolve(frontendRoot, 'src/views/dashboard/index.vue'), 'utf8')
const login = readFileSync(resolve(frontendRoot, 'src/views/login/index.vue'), 'utf8')

test('uses a shared neutral workbench shell instead of a nested white rounded container', () => {
  assert.match(layout, /--cg-page-bg:/)
  assert.match(layout, /--cg-surface:/)
  assert.match(layout, /font-variant-numeric: tabular-nums/)
  assert.match(layout, /background: transparent/)
  assert.match(layout, /border-radius: 0/)
})

test('keeps one visible page title when only one page tab is open', () => {
  assert.match(layout, /logo-mark/)
  assert.match(layout, /v-if="openTabs\.length > 1" class="tab-bar"/)
  assert.doesNotMatch(layout, /CogGuard 工作台/)
  assert.doesNotMatch(layout, /class="header-module"/)
})

test('collapses the desktop sidebar out of the mobile layout', () => {
  assert.match(layout, /@media \(max-width: 720px\)[\s\S]*ant-layout-sider[\s\S]*display: none !important/)
  assert.match(layout, /@media \(max-width: 720px\)[\s\S]*\.app-content[\s\S]*width: 100%/)
})

test('keeps the shell and header content shrinkable on narrow screens', () => {
  assert.match(layout, /\.app-layout\s*\{[^}]*min-width: 0/)
  assert.match(layout, /\.app-header\s*\{[^}]*min-width: 0/)
  assert.match(layout, /\.header-right\s*\{[^}]*min-width: 0/)
  assert.match(layout, /\.user-badge\s*\{[^}]*border-radius: 6px/)
})

test('keeps login surfaces scrollable, restrained, and keyboard-visible', () => {
  assert.doesNotMatch(login, /overflow:\s*hidden/)
  assert.match(login, /\.login-container\s*\{[^}]*box-sizing: border-box/)
  assert.match(login, /:deep\(\.ant-btn:focus-visible\)/)
  assert.match(login, /:deep\(\.ant-input:focus-visible\)/)
  assert.match(login, /@media \(max-width: 520px\)/)
})

test('keeps login form semantics while tightening the workbench shell', () => {
  assert.match(login, /name="username"/)
  assert.match(login, /autocomplete="username"/)
  assert.match(login, /name="password"/)
  assert.match(login, /autocomplete="current-password"/)
  assert.doesNotMatch(login, /transition:\s*all/)
})

test('presents the dashboard event scope as a labeled control with a real event name', () => {
  assert.match(dashboard, /event-scope-control/)
  assert.match(dashboard, /事件范围/)
  assert.doesNotMatch(dashboard, /label: '当前事件'/)
  assert.match(dashboard, /特朗普访华事件/)
})

test('uses the shared light workbench language on the login page', () => {
  assert.match(login, /background: #f5f7fa/)
  assert.match(login, /border-radius: 8px/)
  assert.doesNotMatch(login, /radial-gradient/)
  assert.doesNotMatch(login, /linear-gradient/)
})

test('uses the shared shield mark on the login brand', () => {
  assert.match(login, /SafetyCertificateOutlined/)
  assert.match(login, /class="brand-mark"/)
  assert.match(login, /aria-hidden="true"/)
})

test('removes the duplicate analysis route and navigation entry', () => {
  assert.doesNotMatch(router, /path: 'analysis'/)
  assert.doesNotMatch(layout, /path: '\/analysis'/)
  assert.doesNotMatch(layout, /label: '语义辅助'/)
})

test('risk links to one semantic workspace without embedding its artifact work', () => {
  assert.match(risk, /useRoute\(\)/)
  assert.match(risk, /router\.replace\(/)
  assert.match(risk, /RiskSectionTabs/)
  assert.doesNotMatch(risk, /SemanticEvidenceWorkbench/)
  assert.match(semanticPage, /getSemanticWorkspace/)
  assert.match(semanticPage, /<APagination/)
  assert.match(semanticPage, /RiskSectionTabs/)
  assert.doesNotMatch(semanticPage, /getSemanticPageProjection/)
})

test('keeps the event review overview compact instead of stretching empty panels', () => {
  assert.match(risk, /\.overview-strip\s*\{[\s\S]*?grid-template-columns/)
  assert.match(risk, /\.workbench-grid\s*\{[\s\S]*?align-items:start/)
  assert.doesNotMatch(risk, /\.summary-card\s*\{\s*min-height:/)
})

test('uses a readable hierarchy for the compact semantic evidence workspace', () => {
  assert.match(semanticPage, /\.scope-field > span,[^}]*font-size: 12px/)
  assert.match(semanticPage, /\.workspace-status strong \{[^}]*font-size: 18px/)
  assert.match(semanticPage, /\.traceable-table th, \.traceable-table td \{[^}]*font-size: 13px/)
  assert.match(semanticPage, /\.workspace-panel \{[^}]*padding: 14px/)
})

test('keeps a visible keyboard focus ring on semantic filters', () => {
  assert.doesNotMatch(semantic, /outline:\s*none/)
})

test('keeps the login shell visually quiet and usable on small screens', () => {
  assert.match(login, /box-shadow: 0 4px 16px rgba\(15, 23, 42, 0\.06\)/)
  assert.match(login, /min-height: 100dvh/)
})

test('propagation tabs expose tab semantics and keep path details user-facing', () => {
  assert.match(propagation, /role="tablist"/)
  assert.match(propagation, /<a-tab-pane key="path"/)
  assert.match(propagation, /aria-label="传播分析标签"/)
  assert.doesNotMatch(propagation, /权威来源.*authority_source_id/)
  assert.doesNotMatch(propagation, /路径 \{\{ pathRef\.path_id \}\}/)
  assert.doesNotMatch(propagation, /item\.evidence_refs\?\.join/)
})

test('groups propagation controls into compact scope, density, and action areas', () => {
  assert.match(propagation, /class="toolbar-section filter-group"/)
  assert.match(propagation, /class="toolbar-section density-group"/)
  assert.match(propagation, /class="toolbar-section action-group"/)
  assert.match(propagation, /aria-label="事件范围"/)
  assert.match(propagation, /aria-label="显示密度"/)
  assert.match(propagation, /aria-label="操作"/)
  assert.match(propagation, /\.action-bar\s*\{[\s\S]*padding: 10px 12px/)
})

test('coordination graph honors reduced motion and provides a text summary', () => {
  assert.match(graph, /prefers-reduced-motion/)
  assert.match(coordination, /网络摘要|图谱摘要/)
})

test('dashboard exposes an explicit map loading state', () => {
  assert.match(dashboard, /地图加载中|正在加载地图/)
  assert.match(dashboard, /地图加载失败|重试加载地图/)
})

test('aligns the desktop map with its diagnostic column and treats generated time as neutral metadata', () => {
  assert.match(dashboard, /class="map-card"/)
  assert.match(dashboard, /class="platform-card"/)
  assert.match(dashboard, /class="recent-card"/)
  assert.match(dashboard, /数据更新时间/)
  assert.match(dashboard, /<time :datetime="overview\.meta\.generated_at">/)
  assert.match(dashboard, /\.map-shell\s*\{[\s\S]*?min-height:\s*620px/)
  assert.match(dashboard, /\.map-card :deep\(\.ant-card-body\)\s*\{[^}]*flex-direction:\s*column/)
  assert.match(dashboard, /\.map-shell\s*\{[^}]*flex:\s*1 1 auto/)
  assert.match(dashboard, /@media \(min-width: 1200px\)[\s\S]*?\.side-column\s*\{[\s\S]*?min-height:\s*620px/)
  assert.match(dashboard, /\.side-recent-list\s*\{[\s\S]*?max-height:\s*none/)
})

test('uses the shared blue-gray workbench language for the dashboard audit strip', () => {
  assert.match(dashboard, /\.case-audit-strip\s*\{[^}]*border:\s*1px solid #d9e2f2/)
  assert.match(dashboard, /\.case-audit-strip\s*\{[^}]*border-left:\s*4px solid #1677ff/)
  assert.match(dashboard, /\.case-audit-strip\s*\{[^}]*background:\s*#fff/)
  assert.match(dashboard, /\.case-audit-kicker\s*\{[^}]*color:\s*#64748b/)
  assert.match(dashboard, /\.case-governance\s*\{[^}]*border-left:\s*1px solid #e5e7eb/)
  assert.doesNotMatch(dashboard, /\.case-audit-strip\s*\{[^}]*#dbe7d4/)
})
