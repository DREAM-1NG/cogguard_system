import { access, readdir, readFile, stat } from 'node:fs/promises'
import { resolve } from 'node:path'

const mapBudget = 2_000_000
const chunkBudget = 1_000_000
const mapPath = resolve('src/assets/world-countries.geojson')
const assetsPath = resolve('dist/assets')
const viteManifestPath = resolve('dist/.vite/manifest.json')
const deliveryManifestPath = resolve('dist/delivery-preload-manifest.json')
const indexPath = resolve('dist/index.html')

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

await access(viteManifestPath)
await access(deliveryManifestPath)

const deliveryManifest = JSON.parse(await readFile(deliveryManifestPath, 'utf8'))
const expectedEagerRoutes = ['layout', 'dashboard']
const expectedInteractionRoutes = ['crawl', 'accounts', 'system', 'coordination', 'propagation', 'risk']
const actualEagerRoutes = deliveryManifest.eager_routes || []
const actualInteractionRoutes = deliveryManifest.interaction_routes || []
for (const route of expectedEagerRoutes) {
  if (!actualEagerRoutes.includes(route)) {
    throw new Error(`Delivery preload manifest is missing eager route: ${route}`)
  }
}
for (const route of expectedInteractionRoutes) {
  if (!actualInteractionRoutes.includes(route)) {
    throw new Error(`Delivery preload manifest is missing interaction route: ${route}`)
  }
}

const eagerAssets = expectedEagerRoutes.flatMap((route) => deliveryManifest.routes?.[route]?.assets || [])
const forbiddenEagerAssetPatterns = [/graph3d-view/i, /graph-layout/i, /three-renderer/i, /three-addons/i]
const eagerHeavyAssets = eagerAssets.filter((asset) => forbiddenEagerAssetPatterns.some((pattern) => pattern.test(asset.href)))
if (eagerHeavyAssets.length > 0) {
  throw new Error(`Heavy graph assets leaked into eager preload: ${eagerHeavyAssets.map((asset) => asset.href).join(', ')}`)
}

const builtIndex = await readFile(indexPath, 'utf8')
const preloadScriptPath = String(deliveryManifest.script || '')
if (!preloadScriptPath || !builtIndex.includes(`data-cogguard-delivery-preload src="${preloadScriptPath}"`)) {
  throw new Error('Built index is missing the generated delivery preload script.')
}
await access(resolve('dist', preloadScriptPath.replace(/^\//, '')))

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

console.log(`Frontend budgets verified: map=${mapBytes} bytes, JS chunks <= ${chunkBudget} bytes, delivery preload plan ready`)
