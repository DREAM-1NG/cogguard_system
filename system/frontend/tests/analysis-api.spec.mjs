import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const analysisApi = readFileSync(resolve(frontendRoot, 'src/api/analysis.ts'), 'utf8')

test('analysis artifact client uses the product route and encodes both identifiers', () => {
  assert.match(analysisApi, /createApiClient\('\/api\/v2\/analysis', 120000\)/)
  assert.match(analysisApi, /runs\/\$\{encodeURIComponent\(runId\)\}\/artifacts\/\$\{encodeURIComponent\(artifactKey\)\}/)
  assert.doesNotMatch(analysisApi, /\/api\/v2\/governance/)
})

test('semantic projection client calls the event-scoped product path with an encoded event id', () => {
  assert.match(analysisApi, /export function getEventSemantic\(eventId: string\)/)
  assert.match(analysisApi, /events\/\$\{encodeURIComponent\(eventId\)\}\/semantic/)
})
