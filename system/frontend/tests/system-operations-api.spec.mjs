import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const apiSource = readFileSync(resolve(__dirname, '..', 'src', 'api', 'systemOperations.ts'), 'utf8')

test('system operations use the v2 API client and v2-relative routes', () => {
  assert.match(apiSource, /import \{ createApiClient \} from '@\/utils\/request'/)
  assert.match(apiSource, /const systemOperationsRequest = createApiClient\('\/api\/v2'\)/)
  assert.doesNotMatch(apiSource, /import request from '@\/utils\/request'/)
  assert.match(apiSource, /systemOperationsRequest\.get\('\/system\/operation-health'\)/)
  assert.match(apiSource, /systemOperationsRequest\.get\('\/system\/services'\)/)
  assert.match(apiSource, /systemOperationsRequest\.post\('\/system\/services', body\)/)
  assert.doesNotMatch(apiSource, /['"`]\/v2\/system\//)
})
