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

test('propagation route watcher synchronizes event and platform scope before reloading analysis', () => {
  const watcherStart = propagationView.indexOf('() => [route.query.event_id')
  assert.notEqual(watcherStart, -1, 'Expected propagation route-query watcher to exist')
  const watcher = propagationView.slice(
    watcherStart,
    propagationView.indexOf('watch(displayLayerRows'),
  )

  assert.match(watcher, /route\.query\.event_id/)
  assert.match(watcher, /route\.query\.platform/)
  assert.match(watcher, /syncScopeFromRoute\(\)/)
  assert.match(watcher, /void loadAnalysis\(false\)/)
  assert.doesNotMatch(watcher, /route\.name/)
})

test('propagation analysis reload cancels stale prediction requests unless explicitly preserved', () => {
  const syncScope = bodyOf(propagationView, 'syncScopeFromRoute')
  const loadAnalysis = bodyOf(propagationView, 'loadAnalysis')
  const analyze = bodyOf(propagationView, 'handleAnalyze')

  assert.match(syncScope, /predictionRequestGeneration \+= 1/)
  assert.match(syncScope, /predicting\.value = false/)
  assert.match(loadAnalysis, /if \(!preservePrediction\) \{[\s\S]*predictionRequestGeneration \+= 1/)
  assert.match(loadAnalysis, /modelPrediction\.value = null/)
  assert.match(loadAnalysis, /disposeModelTrendChart\(\)/)
  assert.match(analyze, /await loadAnalysis\(true\)/)
})

test('propagation trend prediction retries the current event without platform when the selected platform has no data', () => {
  const handlePredict = bodyOf(propagationView, 'handlePredict')

  assert.match(propagationView, /function shouldRetryPredictionWithoutPlatform/)
  assert.match(handlePredict, /shouldRetryPredictionWithoutPlatform\(result,\s*requestedPlatform\)/)
  assert.match(handlePredict, /delete retryParams\.platform/)
  assert.match(handlePredict, /predictPropagationCurrentEvent\(retryParams\)/)
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
