import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')
const coordinationView = readFileSync(resolve(frontendRoot, 'src/views/coordination/index.vue'), 'utf8')

function functionBody(source, name) {
  const start = Math.max(
    source.indexOf(`async function ${name}`),
    source.indexOf(`function ${name}`),
  )
  assert.notEqual(start, -1, `Expected ${name} to exist`)
  const brace = source.indexOf('{', start)
  let depth = 0
  for (let index = brace; index < source.length; index += 1) {
    const char = source[index]
    if (char === '{') depth += 1
    if (char === '}') depth -= 1
    if (depth === 0) return source.slice(brace + 1, index)
  }
  throw new Error(`Could not extract ${name}`)
}

function compileAsyncFunction(source, name, parameters, dependencies) {
  const dependencyNames = Object.keys(dependencies)
  const dependencyValues = Object.values(dependencies)
  const body = functionBody(source, name).replace(/\s+as\s+\{\s*data:\s*AnalysisResult\s*\}/, '')
  return new Function(
    ...dependencyNames,
    `return async function ${name}(${parameters.join(', ')}) {${body}}`,
  )(...dependencyValues)
}

function deferred() {
  let resolvePromise
  let rejectPromise
  const promise = new Promise((resolveValue, rejectValue) => {
    resolvePromise = resolveValue
    rejectPromise = rejectValue
  })
  return { promise, resolve: resolvePromise, reject: rejectPromise }
}

function propagationHarness() {
  const eventId = { value: 'event-a' }
  const platform = { value: 'weibo' }
  const analyzing = { value: false }
  const analysisResult = { value: null }
  const modelPrediction = { value: null }
  const selectedObjectId = { value: '' }
  const timelineFocusPostId = { value: '' }
  const requestParams = {}
  Object.defineProperty(requestParams, 'value', {
    get() {
      return { event_id: eventId.value, platform: platform.value, node_limit: 80 }
    },
  })

  const pending = []
  const analyzeObservedPropagation = (params) => {
    const request = deferred()
    pending.push({ params, ...request })
    return request.promise
  }
  const loadAnalysis = compileAsyncFunction(propagationView, 'loadAnalysis', ['showToast = false', 'preservePrediction = false'], {
    analyzeObservedPropagation,
    requestParams,
    analysisResult,
    analyzing,
    modelPrediction,
    selectedObjectId,
    timelineFocusPostId,
    updateSyncTime() {},
    renderPathTabCharts: async () => {},
    disposeModelTrendChart() {},
    message: { warning() {} },
    predictionRequestGeneration: 0,
    analysisRequestGeneration: 0,
    eventId,
    platform,
  })

  return { eventId, platform, analyzing, analysisResult, pending, loadAnalysis }
}

test('ignores propagation analysis responses outside their captured event and platform scope', async () => {
  const harness = propagationHarness()
  const olderRequest = harness.loadAnalysis()

  harness.eventId.value = 'event-b'
  harness.platform.value = 'douyin'
  const activeRequest = harness.loadAnalysis()

  const activeData = { graph: { nodes: [{ id: 'event-b' }] } }
  harness.pending[1].resolve({ data: activeData })
  await activeRequest
  assert.deepEqual(harness.analysisResult.value, activeData)

  harness.pending[0].resolve({ data: { graph: { nodes: [{ id: 'event-a' }] } } })
  await olderRequest

  assert.deepEqual(harness.analysisResult.value, activeData)
})

test('ignores a propagation response when scope changes without starting another request', async () => {
  const harness = propagationHarness()
  const request = harness.loadAnalysis()
  harness.eventId.value = 'event-b'
  harness.platform.value = 'douyin'
  harness.pending[0].resolve({ data: { graph: { nodes: [{ id: 'event-a' }] } } })
  await request

  assert.equal(harness.analysisResult.value, null)
})

test('keeps propagation loading owned by the active generation when an older request finishes first', async () => {
  const harness = propagationHarness()
  const olderRequest = harness.loadAnalysis()

  harness.eventId.value = 'event-b'
  harness.platform.value = 'douyin'
  const activeRequest = harness.loadAnalysis()

  harness.pending[0].resolve({ data: { graph: { nodes: [{ id: 'event-a' }] } } })
  await olderRequest
  assert.equal(harness.analysisResult.value, null)
  assert.equal(harness.analyzing.value, true)

  const activeData = { graph: { nodes: [{ id: 'event-b' }] } }
  harness.pending[1].resolve({ data: activeData })
  await activeRequest
  assert.deepEqual(harness.analysisResult.value, activeData)
  assert.equal(harness.analyzing.value, false)
})

function coordinationHarness(source, name, parameters, apiName, stateName, loadingName, generationName) {
  const selectedDatasetId = { value: 1 }
  const state = { value: null }
  const loading = { value: false }
  const pending = []
  const api = (datasetId) => {
    const request = deferred()
    pending.push({ datasetId, ...request })
    return request.promise
  }
  const fn = compileAsyncFunction(source, name, parameters, {
    [apiName]: api,
    selectedDatasetId,
    [stateName]: state,
    [loadingName]: loading,
    [generationName]: 0,
    nodeLimit: { value: 200 },
    minNodeScore: { value: 0 },
  })
  return { selectedDatasetId, state, loading, pending, fn }
}

test('keeps coordination detail, result, and graph responses scoped to the active dataset and request', async () => {
  const cases = [
    {
      name: 'loadDatasetDetail',
      parameters: ['datasetId'],
      apiName: 'getCoordinationDatasetDetail',
      stateName: 'datasetDetail',
      loadingName: 'loadingDetail',
      generationName: 'datasetDetailRequestGeneration',
      response: { dataset_id: 2, name: 'dataset-b' },
    },
    {
      name: 'loadLatestResult',
      parameters: ['datasetId'],
      apiName: 'getCoordinationDatasetLatestResult',
      stateName: 'resultSnapshot',
      loadingName: 'loadingResult',
      generationName: 'latestResultRequestGeneration',
      response: { dataset_id: 2, result: 'dataset-b' },
    },
    {
      name: 'loadGraph',
      parameters: [],
      apiName: 'getCoordinationGraph',
      stateName: 'graphPayload',
      loadingName: 'loadingGraph',
      generationName: 'graphRequestGeneration',
      response: { dataset_id: 2, nodes: [{ id: 'b' }] },
    },
  ]

  for (const item of cases) {
    const harness = coordinationHarness(
      coordinationView,
      item.name,
      item.parameters,
      item.apiName,
      item.stateName,
      item.loadingName,
      item.generationName,
    )
    const firstRequest = item.name === 'loadGraph' ? harness.fn() : harness.fn(1)

    harness.selectedDatasetId.value = 2
    const activeRequest = item.name === 'loadGraph' ? harness.fn() : harness.fn(2)

    harness.pending[0].resolve({ data: { dataset_id: 1, name: 'dataset-a', result: 'dataset-a', nodes: [{ id: 'a' }] } })
    await firstRequest
    assert.equal(harness.state.value, null, `${item.name} applied stale dataset A response`)
    assert.equal(harness.loading.value, true, `${item.name} cleared active loading state`)

    harness.pending[1].resolve({ data: item.response })
    await activeRequest
    assert.deepEqual(harness.state.value, item.response)
    assert.equal(harness.loading.value, false)
  }
})

test('dataset selection clears prior projections and always starts latest-result loading for the active dataset', () => {
  const selectionBody = functionBody(coordinationView, 'selectDataset')

  assert.match(selectionBody, /datasetDetail\.value\s*=\s*null/)
  assert.match(selectionBody, /resultSnapshot\.value\s*=\s*null/)
  assert.match(selectionBody, /graphPayload\.value\s*=\s*null/)
  assert.match(selectionBody, /finally\s*\{[\s\S]*loadLatestResult\(datasetId\)/)
})

test('coordination polling ignores runs belonging to a superseded dataset', () => {
  const pollingBody = functionBody(coordinationView, 'startPolling')

  assert.match(pollingBody, /requestedDatasetId\s*=\s*selectedDatasetId\.value/)
  assert.match(pollingBody, /requestedDatasetId\s*!==\s*selectedDatasetId\.value/)
})
