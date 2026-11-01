import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const modelPath = resolve(__dirname, '..', 'src/features/crawl/model.ts')
const pagePath = resolve(__dirname, '..', 'src/views/crawl/index.vue')

function loadModel() {
  assert.ok(existsSync(modelPath), 'Crawl workbench model must exist')
  const compiled = ts.transpileModule(readFileSync(modelPath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  new Function('module', 'exports', compiled)(module, module.exports)
  return module.exports
}

test('flattens keyword groups in stable order and removes duplicates', () => {
  const { flattenKeywordGroups } = loadModel()

  assert.deepEqual(
    flattenKeywordGroups([
      { id: 'g1', name: '官方', keywords: ['特朗普', '访华', ''] },
      { id: 'g2', name: '回应', keywords: ['访华', '关税', '特朗普'] },
    ]),
    ['特朗普', '访华', '关税'],
  )
})

test('chooses the primary keyword only from the flattened group terms', () => {
  const { choosePrimaryKeyword } = loadModel()
  const groups = [{ id: 'g1', name: '主张', keywords: ['访华', '关税'] }]

  assert.equal(choosePrimaryKeyword(groups, '关税'), '关税')
  assert.equal(choosePrimaryKeyword(groups, '不存在'), '访华')
})

test('parses task result counts without trusting malformed summaries', () => {
  const { parseJobSummary } = loadModel()

  assert.deepEqual(parseJobSummary('{"posts_count":12,"comments_count":34}'), {
    postsCount: 12,
    commentsCount: 34,
  })
  assert.deepEqual(parseJobSummary('not-json'), { postsCount: 0, commentsCount: 0 })
})

test('parses imported crawl counts from the nested data-run summary', () => {
  const { parseJobSummary } = loadModel()

  assert.deepEqual(parseJobSummary('{"mode":"mediacrawler_data_run_import","stats":{"unique_posts":31,"unique_comments":10137}}'), {
    postsCount: 31,
    commentsCount: 10137,
  })
})

test('clears stale post detail when the selected crawl job changes', () => {
  const { resetPreviewForJob } = loadModel()
  const previous = {
    selectedJobId: 7,
    selectedPostId: 'post-7',
    comments: [{ comment_id: 'comment-7' }],
    media: [{ filename: 'clip.mp4' }],
  }

  assert.deepEqual(resetPreviewForJob(previous, 8), {
    selectedJobId: 8,
    selectedPostId: null,
    comments: [],
    media: [],
  })
})

test('distinguishes ready, not downloaded and unsupported local media', () => {
  const { getMediaPreviewState } = loadModel()

  assert.equal(getMediaPreviewState({ status: 'ready', previewable: true }), 'ready')
  assert.equal(getMediaPreviewState({ status: 'missing', previewable: false }), 'not_downloaded')
  assert.equal(getMediaPreviewState({ status: 'ready', previewable: false }), 'unsupported')
})

test('round-trips crawl job, post and filter state through URL params', () => {
  const { readCrawlQuery, writeCrawlQuery } = loadModel()
  const query = writeCrawlQuery({
    jobId: 7,
    postId: 'post-7',
    platform: 'douyin',
    keyword: '访华',
    hasMedia: true,
  })

  assert.deepEqual(readCrawlQuery(query), {
    jobId: 7,
    postId: 'post-7',
    platform: 'douyin',
    keyword: '访华',
    hasMedia: true,
  })
})

test('crawl workbench uses equal-height scroll panes for controls and evidence preview', () => {
  const pageSource = readFileSync(pagePath, 'utf8')

  assert.match(pageSource, /class="control-column crawl-scroll-pane"/)
  assert.match(pageSource, /class="preview-column"/)
  assert.match(pageSource, /\.crawl-workbench\s*\{[^}]*height:\s*clamp\(720px,\s*calc\(100dvh - 160px\),\s*960px\)/s)
  assert.match(pageSource, /\.crawl-scroll-pane\s*\{[^}]*overflow-y:\s*auto/s)
  assert.match(pageSource, /\.crawl-scroll-pane:focus-visible\s*\{[^}]*outline:/s)
})

test('crawl evidence keeps the selected-content panel visible beside the scrollable post list', () => {
  const pageSource = readFileSync(pagePath, 'utf8')

  assert.match(pageSource, /<main class="preview-column"/)
  assert.match(pageSource, /class="tool-surface content-surface preview-pane"/)
  assert.match(pageSource, /class="tool-surface detail-surface preview-pane"/)
  assert.match(pageSource, /\.preview-column\s*\{[^}]*grid-template-rows:\s*minmax\(400px,\s*1\.35fr\)\s+minmax\(280px,\s*0\.85fr\)/s)
  assert.match(pageSource, /\.preview-pane\s*\{[^}]*min-height:\s*0[^}]*overflow:\s*hidden/s)
  assert.match(pageSource, /\.post-list\s*\{[^}]*overflow-y:\s*auto/s)
  assert.match(pageSource, /\.post-detail\s*\{[^}]*overflow-y:\s*auto/s)
})

test('crawl list distinguishes local media from source media links', () => {
  const pageSource = readFileSync(pagePath, 'utf8')

  assert.match(pageSource, /post\.local_media\?\.available_count/)
  assert.match(pageSource, /已下载/)
  assert.match(pageSource, /待下载/)
})

test('loads posts when a crawl job is restored from the URL', () => {
  const pageSource = readFileSync(pagePath, 'utf8')

  assert.doesNotMatch(pageSource, /selectedJobId\.value === jobId && selectedPost\.value === null\) return/)
  assert.match(pageSource, /const jobChanged = selectedJobId\.value !== jobId/)
  assert.match(pageSource, /await fetchData\(jobChanged \? 1 : dataPage\.value\)/)
  assert.match(pageSource, /if \(nextJob\) await selectJob\(nextJob\.id\)/)
})
