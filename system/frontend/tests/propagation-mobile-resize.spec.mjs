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

function styleBlock(source) {
  const start = source.indexOf('<style scoped lang="less">')
  assert.notEqual(start, -1, 'Expected scoped Less style block to exist')
  const bodyStart = source.indexOf('>', start) + 1
  const end = source.indexOf('</style>', bodyStart)
  assert.notEqual(end, -1, 'Expected scoped Less style block to close')
  return source.slice(bodyStart, end)
}

function executableFunction(source, name) {
  const definition = bodyOf(source, name)
    .replace(/: PropagationChartInstance \| null/g, '')
    .replace(/: HTMLDivElement \| null/g, '')
  return Function(`return (${definition})`)()
}

test('propagation resize skips hidden, detached, or disposed ECharts instances before resizing', () => {
  const safelyResizeChart = executableFunction(propagationView, 'safelyResizeChart')
  const attachedDom = { isConnected: true, offsetWidth: 390, offsetHeight: 260 }
  const hiddenDom = { isConnected: true, offsetWidth: 0, offsetHeight: 260 }
  const detachedDom = { isConnected: false, offsetWidth: 390, offsetHeight: 260 }
  let resizeCalls = 0

  safelyResizeChart(null)
  safelyResizeChart({ isDisposed: () => true, getDom: () => attachedDom, resize: () => { resizeCalls += 1 } })
  safelyResizeChart({ isDisposed: () => false, getDom: () => hiddenDom, resize: () => { resizeCalls += 1 } })
  safelyResizeChart({ isDisposed: () => false, getDom: () => detachedDom, resize: () => { resizeCalls += 1 } })
  safelyResizeChart({ isDisposed: () => false, getDom: () => attachedDom, resize: () => { resizeCalls += 1 } })

  assert.equal(resizeCalls, 1)
})

test('propagation resize uses the mounted-chart guard for every cached chart instance', () => {
  const resizeCharts = bodyOf(propagationView, 'resizeCharts')

  for (const chartName of [
    'layerChart',
    'pathGraphChart',
    'roleIgnitionGraph',
    'modelTrendChart',
    'modelBacktestChart',
    'evidenceTimelineChart',
  ]) {
    assert.match(resizeCharts, new RegExp(`safelyResizeChart\\(${chartName}\\)`))
  }
  assert.doesNotMatch(resizeCharts, /\?\.resize\(/)
})

test('claim-response mobile layout constrains long content instead of widening the viewport', () => {
  const styles = styleBlock(propagationView)

  assert.match(styles, /\.propagation-page \{[\s\S]*?min-width: 0/)
  assert.match(styles, /\.propagation-tabs \{[\s\S]*?min-width: 0/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.claim-response-anchor-card :deep\(\.ant-descriptions-view\) \{[\s\S]*?overflow-x: hidden/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.claim-response-anchor-card :deep\(table\) \{[\s\S]*?table-layout: fixed/)
  assert.match(styles, /@media \(max-width: 768px\) \{[\s\S]*?\.timeline-content \{[\s\S]*?overflow-wrap: anywhere/)
})
