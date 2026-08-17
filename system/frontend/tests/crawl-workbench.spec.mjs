import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const __dirname = dirname(fileURLToPath(import.meta.url))
const modelPath = resolve(__dirname, '..', 'src/features/crawl/model.ts')

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
