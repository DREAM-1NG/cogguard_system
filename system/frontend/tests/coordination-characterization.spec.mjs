import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const coordinationView = readFileSync(resolve(frontendRoot, 'src/views/coordination/index.vue'), 'utf8')

function bodyOf(source, name) {
  const start = source.indexOf(`function ${name}`)
  assert.notEqual(start, -1, `Expected ${name} to exist`)
  const paramsStart = source.indexOf('(', start)
  let paramsDepth = 0
  let paramsEnd = -1
  for (let index = paramsStart; index < source.length; index += 1) {
    const char = source[index]
    if (char === '(') paramsDepth += 1
    if (char === ')') paramsDepth -= 1
    if (paramsDepth === 0) {
      paramsEnd = index
      break
    }
  }
  const brace = source.indexOf('{', paramsEnd)
  let depth = 0
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index]
    if (char === '{') depth += 1
    if (char === '}') depth -= 1
    if (depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Could not extract ${name}`)
}

test('coordination page presents an evidence-first unavailable detection state without duplicate runtime cards', () => {
  assert.match(coordinationView, /跨平台证据/)
  assert.match(coordinationView, /协同发现/)
  assert.match(coordinationView, /协同攻击检测/)
  assert.match(coordinationView, /四维刻画/)
  assert.match(coordinationView, /真实性/)
  assert.match(coordinationView, /危害性/)
  assert.match(coordinationView, /组织性/)
  assert.match(coordinationView, /时间变化/)
  assert.match(coordinationView, /同名不自动合并/)
  assert.match(coordinationView, /检测结果暂不可用/)
  assert.match(coordinationView, /协同结构与四维证据仍可用于人工核查/)
  assert.match(coordinationView, /预计算成员概率/)
  assert.match(coordinationView, /协同证据阈值/)
  assert.match(coordinationView, /证据关键节点/)
  assert.match(coordinationView, /证据分数/)
  assert.match(coordinationView, /运行归档复现/)
  assert.match(coordinationView, /class="detection-status-strip"/)
  assert.doesNotMatch(coordinationView, /class="panel workbench-panel"/)
  assert.doesNotMatch(coordinationView, /class="panel verdict-panel"/)
  assert.doesNotMatch(coordinationView, /China checkpoint 离线预计算/)
  assert.doesNotMatch(coordinationView, /账号级概率到群组聚合代理提示/)
  assert.doesNotMatch(coordinationView, /不执行在线神经网络前向/)
  assert.doesNotMatch(coordinationView, /workflow-strip/)
  assert.doesNotMatch(coordinationView, /Coordination workflow/)
  assert.doesNotMatch(coordinationView, /resolve\s*->\s*discover\s*->\s*detect/)
  assert.doesNotMatch(coordinationView, /active artifact/)
  assert.doesNotMatch(coordinationView, /fail closed/)
  assert.doesNotMatch(coordinationView, /shadow classifier/)
  assert.doesNotMatch(coordinationView, /URL \/|共享 URL|共链 URL/)
  assert.doesNotMatch(coordinationView, /风险阈值/)
  assert.doesNotMatch(coordinationView, /全局关键节点/)
  assert.doesNotMatch(coordinationView, /节点分数/)
})

test('coordination page uses one restrained evidence treatment for all four dimensions', () => {
  const dimensionCardStyle = coordinationView.match(/\.dimension-card\s*\{([^}]*)\}/)?.[1] || ''

  assert.match(coordinationView, /class="dimension-card"/)
  assert.doesNotMatch(coordinationView, /dimension-card--authenticity/)
  assert.doesNotMatch(coordinationView, /dimension-card--harmfulness/)
  assert.doesNotMatch(coordinationView, /dimension-card--orchestration/)
  assert.doesNotMatch(coordinationView, /dimension-card--timeVariance/)
  assert.match(dimensionCardStyle, /border-left:\s*3px solid #63809e;/)
  assert.match(dimensionCardStyle, /background:\s*#fbfcfe;/)
  assert.doesNotMatch(dimensionCardStyle, /linear-gradient/)
})

test('coordination page adapts the four dimensions before the layout becomes crowded', () => {
  assert.match(coordinationView, /@media \(max-width: 1400px\)\s*\{[\s\S]*\.dimension-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(coordinationView, /@media \(max-width: 720px\)\s*\{[\s\S]*\.dimension-grid[\s\S]*grid-template-columns:\s*1fr/)
})

test('coordination page keeps visible breathing room between analysis sections inside the loading shell', () => {
  assert.match(coordinationView, /\.coordination-page :deep\(\.ant-spin-container\) > \* \+ \*\s*\{[\s\S]*margin-top:\s*20px;/)
})

test('coordination page joins cluster detection verdicts without assuming id format', () => {
  const detectionVerdictForCluster = bodyOf(coordinationView, 'detectionVerdictForCluster')

  assert.match(coordinationView, /const detectionVerdictMap = computed/)
  assert.match(coordinationView, /const primaryDetectionVerdicts = computed/)
  assert.match(coordinationView, /primary_socgfm_cross_attention/)
  assert.doesNotMatch(coordinationView, /if \(!role\) return true/)
  assert.doesNotMatch(coordinationView, /includes\('shadow'\)/)
  assert.match(coordinationView, /String\(verdict\?\.model_role \|\| ''\)\.trim\(\) === detectionPrimaryRole/)
  assert.match(detectionVerdictForCluster, /String\(clusterId\)/)
  assert.match(detectionVerdictForCluster, /`resolved-\$\{normalizedId\}`/)
  assert.match(coordinationView, /harmful_probability/)
  assert.match(coordinationView, /model_unavailable/)
  assert.doesNotMatch(coordinationView, /predicted_label/)
})

test('coordination page maps standard detection verdicts to Chinese labels', () => {
  const isHighRiskVerdict = bodyOf(coordinationView, 'isHighRiskVerdict')
  const detectionDecisionLabel = bodyOf(coordinationView, 'detectionDecisionLabel')

  assert.match(isHighRiskVerdict, /harmful_coordination/)
  assert.match(detectionDecisionLabel, /harmful_coordination/)
  assert.match(detectionDecisionLabel, /benign_coordination/)
  assert.match(detectionDecisionLabel, /高风险提示/)
  assert.match(detectionDecisionLabel, /暂未提示危害/)
})

test('coordination page counts every model verdict instead of only rendered community rows', () => {
  const highRiskClusterCount = coordinationView.match(/const highRiskClusterCount = computed\(\(\) => \(([\s\S]*?)\n\)\)/)?.[1] || ''

  assert.match(highRiskClusterCount, /primaryDetectionVerdicts\.value/)
  assert.doesNotMatch(highRiskClusterCount, /communityRows\.value/)
})

test('coordination page waits for the latest result after a run completes', () => {
  const startPolling = bodyOf(coordinationView, 'startPolling')

  assert.match(startPolling, /await Promise\.all\(\[loadDatasets\(\), loadDatasetDetail\(selectedDatasetId\.value\), loadGraph\(\)\]\)/)
  assert.match(startPolling, /await loadLatestResult\(selectedDatasetId\.value\)/)
  assert.doesNotMatch(startPolling, /void loadLatestResult\(selectedDatasetId\.value\)/)
})

test('coordination page keeps characterization evidence-bound instead of model-final', () => {
  assert.match(coordinationView, /characterizationDimensions/)
  assert.match(coordinationView, /authenticitySummary/)
  assert.match(coordinationView, /harmfulnessSummary/)
  assert.match(coordinationView, /orchestrationSummary/)
  assert.match(coordinationView, /timeVarianceSummary/)
  assert.doesNotMatch(coordinationView, /最终判定/)
  assert.doesNotMatch(coordinationView, /botnet/)
})
