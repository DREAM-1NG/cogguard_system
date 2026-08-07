import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')
const coordinationView = readFileSync(resolve(frontendRoot, 'src/views/coordination/index.vue'), 'utf8')
const coordinationGraph = readFileSync(resolve(frontendRoot, 'src/views/coordination/CoordinationGraph3D.vue'), 'utf8')
const crawlView = readFileSync(resolve(frontendRoot, 'src/views/crawl/index.vue'), 'utf8')
const riskView = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')

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

test('kept-alive propagation ignores route changes outside its own route', () => {
  const watcher = propagationView.slice(
    propagationView.indexOf('watch(\n  () => [route.name'),
    propagationView.indexOf('watch(displayLayerRows'),
  )
  const deactivate = bodyOf(propagationView, 'deactivatePropagationPage')
  const analyze = bodyOf(propagationView, 'handleAnalyze')

  assert.match(propagationView, /onActivated/)
  assert.match(propagationView, /onDeactivated/)
  assert.match(watcher, /!pageActive\.value \|\| route\.name !== 'Propagation'/)
  assert.match(deactivate, /analysisRequestGeneration \+= 1/)
  assert.match(deactivate, /unbindResizeListener\(\)/)
  assert.match(analyze, /await loadAnalysis\(true, true\)/)
})

test('kept-alive propagation restores a completed route scope without another analysis request', () => {
  const activate = bodyOf(propagationView, 'activatePropagationPage')
  const watcher = propagationView.slice(
    propagationView.indexOf('watch(\n  () => [route.name'),
    propagationView.indexOf('watch(displayLayerRows'),
  )

  assert.match(
    activate,
    /if \(hasCompletedAnalysisForCurrentScope\(\)\) \{[\s\S]*await renderActiveTabCharts\(\)[\s\S]*return/,
  )
  assert.match(watcher, /if \(!hasRouteScopeChanged\(\)\) return/)
})

test('coordination pauses work while its cached page is inactive', () => {
  const deactivate = bodyOf(coordinationView, 'deactivateCoordinationPage')
  const polling = bodyOf(coordinationView, 'startPolling')

  assert.match(coordinationView, /:active="pageActive"/)
  assert.match(deactivate, /stopPolling\(\)/)
  assert.match(deactivate, /graphRequestGeneration \+= 1/)
  assert.match(polling, /if \(!pageActive\.value\) return/)
  assert.match(coordinationGraph, /active: boolean/)
  assert.match(coordinationGraph, /graph\.pauseAnimation\?\.\(\)/)
  assert.match(coordinationGraph, /graph\.resumeAnimation\?\.\(\)/)
})

test('crawl refreshes only while its kept-alive page is active', () => {
  const deactivate = bodyOf(crawlView, 'deactivateCrawlPage')
  const refresh = bodyOf(crawlView, 'startRefreshTimer')

  assert.match(crawlView, /onActivated/)
  assert.match(crawlView, /onDeactivated/)
  assert.match(deactivate, /stopRefreshTimers\(\)/)
  assert.match(refresh, /pageActive\.value && hasActiveJobs\(\)/)
  assert.match(crawlView, /if \(!pageActive\.value\) return/)
})

test('review applies the latest case response directly without blocking on selector options', () => {
  const initialLoad = bodyOf(riskView, 'loadInitialCase')
  const latestFallback = initialLoad.slice(
    initialLoad.indexOf('loading.value = true'),
    initialLoad.indexOf('} catch'),
  )

  assert.match(latestFallback, /const latest = await getLatestReviewCase\(\)/)
  assert.match(latestFallback, /await applyCase\(latest\.data\)/)
  assert.doesNotMatch(latestFallback, /loadCase\(/)
  assert.match(latestFallback, /void loadCaseOptions\(''\)/)
  assert.doesNotMatch(latestFallback, /await loadCaseOptions\(''\)/)
})

test('review loads evidence and activity projections concurrently after applying a case', () => {
  const applyCase = bodyOf(riskView, 'applyCase')

  assert.match(applyCase, /const pendingLoads: Promise<void>\[\] = \[\]/)
  assert.match(applyCase, /pendingLoads\.push\(loadEvidenceGroup\(activeEvidenceGroup\.value\)\)/)
  assert.match(applyCase, /pendingLoads\.push\(loadActivities\(detail\.case_id\)\)/)
  assert.match(applyCase, /await Promise\.all\(pendingLoads\)/)
})

test('evidence pagination uses an ASCII-safe visible label', () => {
  assert.match(riskView, /\{\{ '\\u52a0\\u8f7d\\u66f4\\u591a' \}\}/)
  assert.doesNotMatch(riskView, /鍔犺浇鏇村/)
})
