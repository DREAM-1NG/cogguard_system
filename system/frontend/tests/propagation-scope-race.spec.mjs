import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')

async function loadRequestScopeHelper() {
  const helperSource = readFileSync(resolve(frontendRoot, 'src/views/propagation/requestScope.ts'), 'utf8')
  const { outputText } = ts.transpileModule(helperSource, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2020,
    },
  })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}

function deferred() {
  let resolvePromise
  let rejectPromise
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })
  return {
    promise,
    resolve: resolvePromise,
    reject: rejectPromise,
  }
}

function styleBlock(source) {
  const start = source.indexOf('<style scoped lang="less">')
  assert.notEqual(start, -1, 'Expected scoped Less style block to exist')
  const bodyStart = source.indexOf('>', start) + 1
  const end = source.indexOf('</style>', bodyStart)
  assert.notEqual(end, -1, 'Expected scoped Less style block to close')
  return source.slice(bodyStart, end)
}

const {
  acceptPropagationScopedResponse,
  analysisRequestParamsFromScope,
  alertsRequestParamsFromScope,
  createPropagationAnalysisScope,
  createPropagationAlertsScope,
  samePropagationAnalysisScope,
  samePropagationAlertsScope,
} = await loadRequestScopeHelper()

test('slower analysis response for scope A cannot overwrite scope B analysis state', async () => {
  let generation = 0
  let currentScope = createPropagationAnalysisScope({
    eventId: 'evt-a',
    platform: 'weibo',
    diffusionNodeLimit: 160,
    diffusionFullViewRequested: false,
    defaultNodeLimit: 160,
  })
  let analysisResult = null
  const requests = []

  async function loadAnalysis(responsePromise) {
    const requestGeneration = ++generation
    const requestedScope = currentScope
    const requestedParams = analysisRequestParamsFromScope(requestedScope)
    requests.push(requestedParams)
    const response = await responsePromise
    if (!acceptPropagationScopedResponse({
      requestGeneration,
      currentGeneration: generation,
      requestedScope,
      currentScope,
      sameScope: samePropagationAnalysisScope,
    })) {
      return
    }
    analysisResult = response.data
  }

  const oldResponse = deferred()
  const currentResponse = deferred()
  const oldLoad = loadAnalysis(oldResponse.promise)

  currentScope = createPropagationAnalysisScope({
    eventId: 'evt-b',
    platform: 'xhs',
    diffusionNodeLimit: 320,
    diffusionFullViewRequested: true,
    defaultNodeLimit: 160,
  })
  const currentLoad = loadAnalysis(currentResponse.promise)

  currentResponse.resolve({ data: { scope: 'b' } })
  await currentLoad
  assert.deepEqual(analysisResult, { scope: 'b' })

  oldResponse.resolve({ data: { scope: 'a' } })
  await oldLoad
  assert.deepEqual(analysisResult, { scope: 'b' })
  assert.deepEqual(requests, [
    {
      event_id: 'evt-a',
      platform: 'weibo',
      node_limit: 160,
      first_layer_limit: 40,
      second_layer_limit: 80,
    },
    {
      event_id: 'evt-b',
      platform: 'xhs',
      node_limit: 0,
    },
  ])
})

test('stale alert success cannot overwrite current scope B alert rows', async () => {
  let generation = 0
  let currentScope = createPropagationAlertsScope({ eventId: 'evt-a', platform: 'news' })
  let alertRows = []
  const requests = []

  async function loadPropagationAlerts(responsePromise) {
    const requestGeneration = ++generation
    const requestedScope = currentScope
    requests.push(alertsRequestParamsFromScope(requestedScope))
    const response = await responsePromise
    if (!acceptPropagationScopedResponse({
      requestGeneration,
      currentGeneration: generation,
      requestedScope,
      currentScope,
      sameScope: samePropagationAlertsScope,
    })) {
      return
    }
    alertRows = Array.isArray(response.data) ? response.data : []
  }

  const oldResponse = deferred()
  const currentResponse = deferred()
  const oldLoad = loadPropagationAlerts(oldResponse.promise)

  currentScope = createPropagationAlertsScope({ eventId: 'evt-b', platform: 'weibo' })
  const currentLoad = loadPropagationAlerts(currentResponse.promise)

  currentResponse.resolve({ data: [{ id: 'b-alert' }] })
  await currentLoad
  assert.deepEqual(alertRows, [{ id: 'b-alert' }])

  oldResponse.resolve({ data: [{ id: 'a-alert' }] })
  await oldLoad
  assert.deepEqual(alertRows, [{ id: 'b-alert' }])
  assert.deepEqual(requests, [
    { event_id: 'evt-a', platform: 'news' },
    { event_id: 'evt-b', platform: 'weibo' },
  ])
})

test('stale alert failure cannot clear current scope B alert rows', async () => {
  let generation = 0
  let currentScope = createPropagationAlertsScope({ eventId: 'evt-a', platform: 'news' })
  let alertRows = []

  async function loadPropagationAlerts(responsePromise) {
    const requestGeneration = ++generation
    const requestedScope = currentScope
    try {
      const response = await responsePromise
      if (!acceptPropagationScopedResponse({
        requestGeneration,
        currentGeneration: generation,
        requestedScope,
        currentScope,
        sameScope: samePropagationAlertsScope,
      })) {
        return
      }
      alertRows = Array.isArray(response.data) ? response.data : []
    } catch {
      if (!acceptPropagationScopedResponse({
        requestGeneration,
        currentGeneration: generation,
        requestedScope,
        currentScope,
        sameScope: samePropagationAlertsScope,
      })) {
        return
      }
      alertRows = []
    }
  }

  const oldResponse = deferred()
  const currentResponse = deferred()
  const oldLoad = loadPropagationAlerts(oldResponse.promise)

  currentScope = createPropagationAlertsScope({ eventId: 'evt-b', platform: 'weibo' })
  const currentLoad = loadPropagationAlerts(currentResponse.promise)

  currentResponse.resolve({ data: [{ id: 'b-alert' }] })
  await currentLoad
  assert.deepEqual(alertRows, [{ id: 'b-alert' }])

  oldResponse.reject(new Error('old scope failed'))
  await oldLoad
  assert.deepEqual(alertRows, [{ id: 'b-alert' }])
})

test('propagation lifecycle functions use the shared request-scope policy helper', () => {
  assert.match(propagationView, /from '\.\/requestScope'/)
  assert.match(propagationView, /acceptPropagationScopedResponse\(\{[\s\S]*?sameScope: samePropagationAnalysisScope/)
  assert.match(propagationView, /acceptPropagationScopedResponse\(\{[\s\S]*?sameScope: samePropagationAlertsScope/)
})

test('path node controls stack inside the mobile propagation viewport', () => {
  const styles = styleBlock(propagationView)

  assert.match(styles, /\.path-node-control \{[\s\S]*?grid-template-columns: auto minmax\(160px, 1fr\) auto auto/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-control \{[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-control \{[\s\S]*?align-items: stretch/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-slider \{[\s\S]*?width: 100%/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-control-label,[\s\S]*?\.path-node-control-count \{[\s\S]*?white-space: normal/)
})
