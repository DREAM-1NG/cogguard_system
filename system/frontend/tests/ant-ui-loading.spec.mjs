import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(__dirname, '..')
const entry = readFileSync(resolve(frontendRoot, 'src/main.ts'), 'utf8')
const registry = readFileSync(resolve(frontendRoot, 'src/ui/antDesignComponents.ts'), 'utf8')
const semanticWorkspaceControls = readFileSync(resolve(frontendRoot, 'src/ui/semanticWorkspaceControls.ts'), 'utf8')
const viteConfig = readFileSync(resolve(frontendRoot, 'vite.config.ts'), 'utf8')

test('defers low-frequency Ant Design components and groups dense workspace controls', () => {
  assert.match(entry, /installAntDesignComponents\(app\)/)
  assert.doesNotMatch(entry, /from 'ant-design-vue'/)
  assert.match(registry, /defineAsyncComponent/)
  assert.match(registry, /import\('\.\/semanticWorkspaceControls'\)/)
  assert.doesNotMatch(registry, /import\('ant-design-vue\/es\/button'\)/)
  assert.match(registry, /import\('ant-design-vue\/es\/table'\)/)
  assert.match(registry, /registerAsyncComponent\(app, 'a-layout'/)
  assert.match(registry, /registerAsyncComponent\(app, 'a-table'/)
  assert.match(semanticWorkspaceControls, /import AButton from 'ant-design-vue\/es\/button'/)
  assert.match(semanticWorkspaceControls, /import APagination from 'ant-design-vue\/es\/pagination'/)
})

test('leaves asynchronous Ant Design components to Rollup rather than forcing a monolithic vendor chunk', () => {
  assert.doesNotMatch(viteConfig, /ant-design-vue\/es/)
  assert.doesNotMatch(viteConfig, /@ant-design\/icons-vue/)
  assert.doesNotMatch(viteConfig, /return 'ant-ui'/)
  assert.match(viteConfig, /onlyExplicitManualChunks: false/)
  assert.match(viteConfig, /return 'semantic-workspace-ui'/)
})

test('proxies local API requests through the IPv4 backend listener', () => {
  assert.match(viteConfig, /target: 'http:\/\/127\.0\.0\.1:8000'/)
  assert.doesNotMatch(viteConfig, /target: 'http:\/\/localhost:8000'/)
})
