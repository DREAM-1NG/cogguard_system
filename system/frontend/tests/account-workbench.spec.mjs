import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const workbenchSource = readFileSync(resolve(frontendRoot, 'src/views/accounts/accountWorkbench.ts'), 'utf8')
const accountView = readFileSync(resolve(frontendRoot, 'src/views/accounts/index.vue'), 'utf8')

async function loadWorkbenchHelper() {
  const { outputText } = ts.transpileModule(workbenchSource, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2020,
    },
  })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}

const {
  acceptAccountDetailResponse,
  accountSelectionKey,
  resolveAccountSelection,
} = await loadWorkbenchHelper()

const profiles = [
  { platform: 'weibo', account_id: 'a-1' },
  { platform: 'weibo', account_id: 'a-2' },
  { platform: 'xhs', account_id: 'a-1' },
]

test('account selection keeps the requested platform-scoped account or falls back to the first profile', () => {
  assert.equal(accountSelectionKey({ platform: 'weibo', accountId: 'a-1' }), 'weibo::a-1')
  assert.deepEqual(resolveAccountSelection(profiles, { platform: 'xhs', accountId: 'a-1' }), {
    platform: 'xhs',
    accountId: 'a-1',
  })
  assert.deepEqual(resolveAccountSelection(profiles, { platform: 'douyin', accountId: 'missing' }), {
    platform: 'weibo',
    accountId: 'a-1',
  })
  assert.equal(resolveAccountSelection([], { platform: 'weibo', accountId: 'a-1' }), null)
})

test('a stale account detail response cannot replace the most recently selected account', () => {
  const current = { platform: 'xhs', accountId: 'a-1' }
  assert.equal(acceptAccountDetailResponse({
    requestGeneration: 1,
    currentGeneration: 2,
    requested: { platform: 'weibo', accountId: 'a-1' },
    current,
  }), false)
  assert.equal(acceptAccountDetailResponse({
    requestGeneration: 2,
    currentGeneration: 2,
    requested: current,
    current,
  }), true)
})

test('account page renders an accessible master-detail investigation layout', () => {
  assert.match(accountView, /class="account-master-detail"/)
  assert.match(accountView, /class="account-list-pane"/)
  assert.match(accountView, /class="account-detail-pane"/)
  assert.match(accountView, /class="account-list-row"/)
  assert.match(accountView, /:aria-pressed="isSelectedAccount\(record\)"/)
  assert.match(accountView, /aria-label="事件 ID"/)
  assert.match(accountView, /aria-live="polite"/)
})

test('account master-detail workbench uses equal-height scroll panes instead of pagination', () => {
  assert.match(accountView, /class="account-list-scroll"/)
  assert.match(accountView, /v-for="record in profiles"/)
  assert.match(accountView, /\.account-master-detail \{[\s\S]*?height: clamp\(620px, calc\(100dvh - 250px\), 780px\)/)
  assert.match(accountView, /\.account-list-scroll \{[\s\S]*?overflow-y: auto/)
  assert.match(accountView, /\.account-detail-pane \{[\s\S]*?overflow-y: auto/)
  assert.doesNotMatch(accountView, /<a-pagination/)
  assert.doesNotMatch(accountView, /const pageSize = 20/)
})

test('similar account list preserves backend order and switches accounts within the anchor platform', () => {
  assert.match(accountView, /v-for="\(neighbor, index\) in similarAccounts"/)
  assert.match(accountView, /class="similar-account-row"/)
  assert.match(accountView, /@click="selectSimilarAccount\(neighbor\)"/)
  assert.match(accountView, /function selectSimilarAccount\(neighbor: SimilarAccount\)/)
  assert.match(accountView, /platform: String\(detail\.value\?\.platform \|\| ''\)/)
  assert.match(accountView, /final_prediction: neighbor\.final_prediction \|\| profile\?\.assessment\?\.prediction/)
  assert.match(accountView, /bot_probability: neighbor\.bot_probability \?\? profile\?\.assessment\?\.bot_probability/)
  assert.doesNotMatch(accountView, /sort\(\(left, right\).*similarity/)
})

test('similar account drill-down centers the selected account in the left list', () => {
  assert.match(accountView, /:ref="\(element\) => captureAccountListRow\(record, element\)"/)
  assert.match(accountView, /async function selectAccount\(record: AccountProfile, scrollListRow = false\)/)
  assert.match(accountView, /await nextTick\(\)\s*scrollSelectedAccountIntoView\(target\)/)
  assert.match(accountView, /void selectAccount\(profile, true\)/)
  assert.match(accountView, /accountListRowElements\s*\.get\(\s*accountSelectionKey\(target\)\s*\)/)
  assert.match(accountView, /scrollIntoView\(\{ block: 'center', behavior: 'smooth' \}\)/)
})

test('similar account empty state is explicit and does not substitute a different relationship', () => {
  assert.match(accountView, /当前检测未产出相似账号/)
  assert.match(accountView, /不代表关注、好友或转发关系/)
  assert.doesNotMatch(accountView, /超图支持邻居/)
})
