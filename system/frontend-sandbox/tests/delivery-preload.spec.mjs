import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const generator = resolve(frontendRoot, 'scripts/generate-delivery-preload.mjs')

function writeFixtureManifest(root) {
  const manifestPath = resolve(root, 'dist/.vite/manifest.json')
  mkdirSync(dirname(manifestPath), { recursive: true })
  mkdirSync(resolve(root, 'dist/assets'), { recursive: true })
  writeFileSync(resolve(root, 'dist/index.html'), '<html><head></head><body></body></html>')
  writeFileSync(manifestPath, JSON.stringify({
    'src/components/layout/BasicLayout.vue': { file: 'assets/layout.js' },
    'src/views/dashboard/index.vue': {
      file: 'assets/dashboard.js',
      css: ['assets/dashboard.css'],
      assets: ['assets/world.geojson'],
      imports: ['assets/dashboard-vendor.js', 'assets/installCanvasRenderer.js'],
    },
    'src/views/crawl/index.vue': { file: 'assets/crawl.js' },
    'src/views/accounts/index.vue': { file: 'assets/accounts.js' },
    'src/views/system/index.vue': { file: 'assets/system.js' },
    'src/views/coordination/index.vue': { file: 'assets/coordination.js', imports: ['assets/graph3d-view.js'] },
    'src/views/propagation/index.vue': { file: 'assets/propagation.js' },
    'src/views/risk/index.vue': { file: 'assets/risk.js' },
    'assets/dashboard-vendor.js': { file: 'assets/dashboard-vendor.js' },
    'assets/installCanvasRenderer.js': { file: 'assets/installCanvasRenderer.js' },
    'assets/graph3d-view.js': { file: 'assets/graph3d-view.js' },
  }))
}

function runPreloadScript(source) {
  const documentListeners = new Map()
  const windowListeners = new Map()
  const preparedAssets = []
  const localStorage = {
    getItem: (key) => key === 'access_token' ? 'test-token' : null,
  }
  const document = {
    readyState: 'complete',
    addEventListener: (event, handler) => documentListeners.set(event, handler),
    createElement: () => ({}),
    querySelector: () => null,
    head: {
      append: (asset) => preparedAssets.push(asset),
    },
  }
  const window = {
    addEventListener: (event, handler) => windowListeners.set(event, handler),
    clearInterval: () => {},
    requestIdleCallback: (callback) => callback(),
    setInterval: () => 1,
    setTimeout: (callback) => callback(),
  }

  vm.runInNewContext(source, { URL, document, localStorage, window })
  return { documentListeners, preparedAssets, windowListeners }
}

function menuTarget(menuId) {
  return {
    closest(selector) {
      if (selector === '[data-menu-id]') {
        return { getAttribute: () => menuId }
      }
      return null
    },
  }
}

test('generates an eager-only delivery preload plan and defers heavy routes to interaction', () => {
  const fixtureRoot = mkdtempSync(resolve(tmpdir(), 'cogguard-delivery-preload-'))
  try {
    writeFixtureManifest(fixtureRoot)
    execFileSync(process.execPath, [generator], { cwd: fixtureRoot, stdio: 'pipe' })

    const manifest = JSON.parse(readFileSync(resolve(fixtureRoot, 'dist/delivery-preload-manifest.json'), 'utf8'))
    const indexHtml = readFileSync(resolve(fixtureRoot, 'dist/index.html'), 'utf8')
    const preloadScript = readFileSync(resolve(fixtureRoot, 'dist', manifest.script.slice(1)), 'utf8')

    assert.deepEqual(manifest.eager_routes, ['layout', 'dashboard'])
    assert.deepEqual(manifest.interaction_routes, ['crawl', 'accounts', 'system', 'coordination', 'propagation', 'risk'])
    assert.match(indexHtml, /data-cogguard-delivery-preload/)
    assert.ok(!manifest.routes.dashboard.assets.some((asset) => asset.href.endsWith('/world.geojson')))
    assert.ok(!manifest.routes.dashboard.assets.some((asset) => asset.href.endsWith('.css')))
    assert.ok(!manifest.routes.dashboard.assets.some((asset) => asset.href.includes('graph3d-view')))
    assert.ok(manifest.routes.dashboard.assets.some((asset) => asset.href.includes('installCanvasRenderer')))
    assert.match(preloadScript, /pointerover/)
    assert.match(preloadScript, /data-menu-id/)
    assert.match(preloadScript, /key\.startsWith\('\/'\)/)
    assert.match(preloadScript, /requestIdleCallback/)
    assert.match(preloadScript, /setInterval/)

    const { documentListeners, preparedAssets } = runPreloadScript(preloadScript)
    const eagerAssets = preparedAssets.map((asset) => asset.href)
    assert.ok(eagerAssets.includes('/assets/layout.js'))
    assert.ok(eagerAssets.includes('/assets/dashboard.js'))
    assert.ok(!eagerAssets.some((href) => href.includes('graph3d-view')))

    documentListeners.get('pointerover')({ target: menuTarget('menu_item_1_$$_/crawl') })
    documentListeners.get('focusin')({ target: menuTarget('/risk') })
    const interactionAssets = preparedAssets.map((asset) => asset.href)
    assert.ok(interactionAssets.includes('/assets/crawl.js'))
    assert.ok(interactionAssets.includes('/assets/risk.js'))
  } finally {
    rmSync(fixtureRoot, { recursive: true, force: true })
  }
})
