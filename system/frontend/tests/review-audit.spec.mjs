import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const riskView = readFileSync(resolve(frontendRoot, 'src/views/risk/index.vue'), 'utf8')
const reviewCaseApi = readFileSync(resolve(frontendRoot, 'src/api/reviewCases.ts'), 'utf8')

test('loads the persisted review audit with the case, without auto-requesting review', () => {
  assert.match(reviewCaseApi, /export function getReviewAudit\(caseId: string\)/)
  assert.match(reviewCaseApi, /\/teacher-audit/)
  assert.match(riskView, /getReviewAudit\(caseId\)/)
  assert.match(riskView, /Promise\.all\(\[([\s\S]*?)getReviewAudit\(caseId\)/)
  assert.match(riskView, /message="尚未产生复核审计"/)
  assert.doesNotMatch(riskView, /requestReviewAdvisory\([^\n]+reviewAudit/)
})

test('renders audit stages, source provenance, and rationale capsules with explicit boundaries', () => {
  assert.match(riskView, /class="review-panel"/)
  assert.match(riskView, /reviewAudit\.stages/)
  assert.match(riskView, /reviewAudit\.sources/)
  assert.match(riskView, /reviewAudit\.rationale\.available/)
  assert.match(riskView, /来源数量为零不等于事实已被证实/)
  assert.match(riskView, /不是自动确认结论/)
})
