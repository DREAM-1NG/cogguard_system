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

test('coordination page isolates stale dataset responses and exposes retryable resource errors', () => {
  assert.match(coordinationView, /getCoordinationDatasetDetail\(datasetId\)/)
  assert.match(coordinationView, /getCoordinationDatasetLatestResult\(datasetId\)/)
  assert.match(coordinationView, /getCoordinationGraph\(/)
  assert.doesNotMatch(coordinationView, /runCoordinationDetection\(/)

  assert.match(coordinationView, /const datasetDetailError = ref<string \| null>\(null\)/)
  assert.match(coordinationView, /const latestResultError = ref<string \| null>\(null\)/)
  assert.match(coordinationView, /const graphError = ref<string \| null>\(null\)/)
  assert.match(coordinationView, /let datasetDetailRequestGeneration = 0/)
  assert.match(coordinationView, /let latestResultRequestGeneration = 0/)

  const selectDataset = bodyOf(coordinationView, 'selectDataset')
  assert.match(selectDataset, /datasetDetail\.value = null/)
  assert.match(selectDataset, /resultSnapshot\.value = null/)
  assert.match(selectDataset, /graphPayload\.value = null/)
  assert.match(selectDataset, /datasetDetailError\.value = null/)
  assert.match(selectDataset, /latestResultError\.value = null/)
  assert.match(selectDataset, /graphError\.value = null/)
  assert.match(selectDataset, /loadDatasetDetail\(datasetId\)/)
  assert.match(selectDataset, /loadLatestResult\(datasetId\)/)
  assert.match(selectDataset, /loadGraph\(\)/)

  const detailLoader = bodyOf(coordinationView, 'loadDatasetDetail')
  assert.match(detailLoader, /const requestGeneration = \+\+datasetDetailRequestGeneration/)
  assert.match(detailLoader, /requestGeneration !== datasetDetailRequestGeneration/)
  assert.match(detailLoader, /datasetId !== selectedDatasetId\.value/)
  assert.match(detailLoader, /catch \(error\)/)
  assert.match(detailLoader, /datasetDetailError\.value =/)

  const latestLoader = bodyOf(coordinationView, 'loadLatestResult')
  assert.match(latestLoader, /const requestGeneration = \+\+latestResultRequestGeneration/)
  assert.match(latestLoader, /requestGeneration !== latestResultRequestGeneration/)
  assert.match(latestLoader, /datasetId !== selectedDatasetId\.value/)
  assert.match(latestLoader, /catch \(error\)/)
  assert.match(latestLoader, /latestResultError\.value =/)

  const graphLoader = bodyOf(coordinationView, 'loadGraph')
  assert.match(graphLoader, /catch \(error\)/)
  assert.match(graphLoader, /graphError\.value =/)

  assert.match(coordinationView, /v-if="datasetDetailError"/)
  assert.match(coordinationView, /数据集详情加载失败/)
  assert.match(coordinationView, /重试数据集详情/)
  assert.match(coordinationView, /v-if="latestResultError"/)
  assert.match(coordinationView, /历史结果加载失败/)
  assert.match(coordinationView, /重试历史结果/)
  assert.match(coordinationView, /v-if="graphError"/)
  assert.match(coordinationView, /协同网络加载失败/)
  assert.match(coordinationView, /重试协同网络/)
  assert.match(coordinationView, /暂无历史协同检测结果/)
  assert.match(coordinationView, /暂无可展示的协同网络数据/)
})
