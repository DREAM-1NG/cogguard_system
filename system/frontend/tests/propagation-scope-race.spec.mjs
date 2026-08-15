import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const propagationView = readFileSync(resolve(frontendRoot, 'src/views/propagation/index.vue'), 'utf8')

function bodyOf(source, name) {
  const start = source.indexOf(`function ${name}(`)
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

function executableFunction(source, name) {
  const definition = bodyOf(source, name)
    .replace(/: PropagationAnalysisRequestScope/g, '')
    .replace(/: PropagationAlertsRequestScope/g, '')
    .replace(/\): boolean \{/, ') {')
  return Function(`return (${definition})`)()
}

function styleBlock(source) {
  const start = source.indexOf('<style scoped lang="less">')
  assert.notEqual(start, -1, 'Expected scoped Less style block to exist')
  const bodyStart = source.indexOf('>', start) + 1
  const end = source.indexOf('</style>', bodyStart)
  assert.notEqual(end, -1, 'Expected scoped Less style block to close')
  return source.slice(bodyStart, end)
}

test('analysis responses update only the latest matching event, platform, and node-limit scope', () => {
  const sameScope = executableFunction(propagationView, 'samePropagationAnalysisScope')
  const current = {
    eventId: 'evt-current',
    platform: 'weibo',
    nodeLimit: 160,
    fullViewRequested: false,
  }

  assert.equal(sameScope(current, { ...current }), true)
  assert.equal(sameScope({ ...current, eventId: 'evt-old' }, current), false)
  assert.equal(sameScope({ ...current, platform: 'xhs' }, current), false)
  assert.equal(sameScope({ ...current, nodeLimit: 320 }, current), false)
  assert.equal(sameScope({ ...current, nodeLimit: 0, fullViewRequested: true }, current), false)

  const loadAnalysis = bodyOf(propagationView, 'loadAnalysis')
  const guardIndex = loadAnalysis.indexOf('samePropagationAnalysisScope(requestedScope, currentPropagationAnalysisScope())')
  const assignIndex = loadAnalysis.indexOf('analysisResult.value = res.data')

  assert.match(loadAnalysis, /const requestGeneration = \+\+analysisRequestGeneration/)
  assert.match(loadAnalysis, /const requestedScope = currentPropagationAnalysisScope\(\)/)
  assert.match(loadAnalysis, /const requestedParams = \{ \.\.\.requestParams\.value \}/)
  assert.match(loadAnalysis, /analyzeObservedPropagation\(requestedParams\)/)
  assert.match(loadAnalysis, /requestGeneration !== analysisRequestGeneration/)
  assert.ok(guardIndex !== -1, 'Expected loadAnalysis to compare response scope before applying it')
  assert.ok(guardIndex < assignIndex, 'Expected stale analysis responses to be rejected before assignment')
})

test('alert responses update only the latest matching event and platform scope', () => {
  const sameScope = executableFunction(propagationView, 'samePropagationAlertsScope')
  const current = { eventId: 'evt-current', platform: 'news' }

  assert.equal(sameScope(current, { ...current }), true)
  assert.equal(sameScope({ ...current, eventId: 'evt-old' }, current), false)
  assert.equal(sameScope({ ...current, platform: 'weibo' }, current), false)

  const loadAlerts = bodyOf(propagationView, 'loadPropagationAlerts')
  const guardIndex = loadAlerts.indexOf('samePropagationAlertsScope(requestedScope, currentPropagationAlertsScope())')
  const assignIndex = loadAlerts.indexOf('propagationAlerts.value = Array.isArray(response.data) ? response.data : []')
  const catchIndex = loadAlerts.indexOf('} catch')

  assert.match(loadAlerts, /const requestGeneration = \+\+alertsRequestGeneration/)
  assert.match(loadAlerts, /const requestedScope = currentPropagationAlertsScope\(\)/)
  assert.match(loadAlerts, /const requestedParams = \{[\s\S]*event_id: requestedScope\.eventId/)
  assert.match(loadAlerts, /getPropagationAlerts\(requestedParams\)/)
  assert.match(loadAlerts, /requestGeneration !== alertsRequestGeneration/)
  assert.ok(guardIndex !== -1, 'Expected loadPropagationAlerts to compare response scope before applying it')
  assert.ok(guardIndex < assignIndex, 'Expected stale alert responses to be rejected before assignment')
  assert.ok(catchIndex !== -1 && catchIndex < loadAlerts.indexOf('propagationAlerts.value = []', catchIndex))
  assert.match(loadAlerts, /if \(requestGeneration === alertsRequestGeneration\) \{[\s\S]*alertsLoading\.value = false/)
})

test('path node controls stack inside the mobile propagation viewport', () => {
  const styles = styleBlock(propagationView)

  assert.match(styles, /\.path-node-control \{[\s\S]*?grid-template-columns: auto minmax\(160px, 1fr\) auto auto/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-control \{[\s\S]*?grid-template-columns: minmax\(0, 1fr\)/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-control \{[\s\S]*?align-items: stretch/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-slider \{[\s\S]*?width: 100%/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.path-node-control-label,[\s\S]*?\.path-node-control-count \{[\s\S]*?white-space: normal/)
})
