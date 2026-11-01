import { readdir, readFile, stat } from 'node:fs/promises'
import { resolve } from 'node:path'

const mapBudget = 2_000_000
const chunkBudget = 1_000_000
const mapPath = resolve('src/assets/world-countries.geojson')
const assetsPath = resolve('dist/assets')

const mapBytes = (await stat(mapPath)).size
if (mapBytes > mapBudget) {
  throw new Error(`Map payload exceeds budget: ${mapBytes} > ${mapBudget} bytes`)
}

const oversizedChunks = []
for (const filename of await readdir(assetsPath)) {
  if (!filename.endsWith('.js')) continue
  const bytes = (await stat(resolve(assetsPath, filename))).size
  if (bytes > chunkBudget) oversizedChunks.push(`${filename} (${bytes} bytes)`)
}
if (oversizedChunks.length > 0) {
  throw new Error(`JavaScript chunks exceed budget:\n${oversizedChunks.join('\n')}`)
}

const productSource = await readFile(resolve('src/views/risk/index.vue'), 'utf8')
const forbiddenTerms = [
  'Student',
  'Teacher',
  'Agent',
  'checkpoint',
  'artifact',
  'run_id',
  'job_id',
  'task_id',
  'raw_confidence',
  'runtime_status',
]
const leakedTerms = forbiddenTerms.filter((term) => productSource.includes(term))
if (leakedTerms.length > 0) {
  throw new Error(`Forbidden product terms found in Event Review Case view: ${leakedTerms.join(', ')}`)
}

console.log(`Frontend budgets verified: map=${mapBytes} bytes, JS chunks <= ${chunkBudget} bytes`)
