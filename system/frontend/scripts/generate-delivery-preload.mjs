import { createHash } from 'node:crypto'
import { readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const distDirectory = resolve('dist')
const assetsDirectory = resolve(distDirectory, 'assets')
const viteManifestPath = resolve(distDirectory, '.vite', 'manifest.json')
const indexPath = resolve(distDirectory, 'index.html')
const deliveryManifestPath = resolve(distDirectory, 'delivery-preload-manifest.json')

const routeDefinitions = [
  { name: 'layout', path: '/', source: 'src/components/layout/BasicLayout.vue', mode: 'eager' },
  { name: 'dashboard', path: '/dashboard', source: 'src/views/dashboard/index.vue', mode: 'eager' },
  { name: 'crawl', path: '/crawl', source: 'src/views/crawl/index.vue', mode: 'interaction' },
  { name: 'accounts', path: '/accounts', source: 'src/views/accounts/index.vue', mode: 'interaction' },
  { name: 'system', path: '/system', source: 'src/views/system/index.vue', mode: 'interaction' },
  { name: 'coordination', path: '/coordination', source: 'src/views/coordination/index.vue', mode: 'interaction' },
  { name: 'propagation', path: '/propagation', source: 'src/views/propagation/index.vue', mode: 'interaction' },
  { name: 'risk', path: '/risk', source: 'src/views/risk/index.vue', mode: 'interaction' },
]

const viteManifest = JSON.parse(await readFile(viteManifestPath, 'utf8'))

function findManifestEntry(source) {
  const direct = viteManifest[source]
  if (direct) return { key: source, entry: direct }
  const found = Object.entries(viteManifest).find(([, entry]) => entry.src === source)
  if (!found) throw new Error(`Vite manifest is missing route source: ${source}`)
  return { key: found[0], entry: found[1] }
}

function classifyAsset(file) {
  if (file.endsWith('.js')) return { rel: 'modulepreload', as: 'script' }
  return null
}

function collectAssets(entryKey, visited = new Set(), assets = new Map()) {
  if (visited.has(entryKey)) return assets
  visited.add(entryKey)
  const entry = viteManifest[entryKey]
  if (!entry) throw new Error(`Vite manifest references missing import: ${entryKey}`)

  const files = [entry.file, ...(entry.css || []), ...(entry.assets || [])]
  for (const file of files) {
    const descriptor = classifyAsset(file)
    if (!descriptor) continue
    assets.set(file, { href: `/${file}`, ...descriptor })
  }
  for (const importKey of entry.imports || []) {
    collectAssets(importKey, visited, assets)
  }
  return assets
}

const routes = Object.fromEntries(routeDefinitions.map((definition) => {
  const { key } = findManifestEntry(definition.source)
  const assets = [...collectAssets(key).values()]
  return [definition.name, {
    path: definition.path,
    source: definition.source,
    mode: definition.mode,
    assets,
  }]
}))

const deliveryPlan = {
  eager_routes: routeDefinitions.filter((route) => route.mode === 'eager').map((route) => route.name),
  interaction_routes: routeDefinitions.filter((route) => route.mode === 'interaction').map((route) => route.name),
  routes,
}

const scriptSource = `const plan=${JSON.stringify(deliveryPlan)};\nconst prepared=new Set();\nlet scheduled=false;\nlet loginWatch;\nfunction addAsset(asset){if(prepared.has(asset.href)||document.querySelector(\`link[href="\${asset.href}"]\`))return;const link=document.createElement('link');link.rel=asset.rel;link.as=asset.as;link.href=asset.href;if(asset.crossorigin)link.crossOrigin=asset.crossorigin;document.head.append(link);prepared.add(asset.href)}\nfunction prepare(names){for(const name of names){for(const asset of plan.routes[name]?.assets||[])addAsset(asset)}}\nfunction scheduleIdle(callback){if('requestIdleCallback'in window){window.requestIdleCallback(callback,{timeout:750});return}window.setTimeout(callback,0)}\nfunction prepareAuthenticatedShell(){if(scheduled||!localStorage.getItem('access_token'))return;scheduled=true;if(loginWatch)window.clearInterval(loginWatch);scheduleIdle(()=>prepare(plan.eager_routes))}\nfunction routeForLink(link){try{return new URL(link.href,window.location.origin).pathname}catch{return''}}\nfunction routeForMenuKey(key){if(key.startsWith('/'))return key;const marker='$$_';return key.includes(marker)?key.slice(key.lastIndexOf(marker)+marker.length):''}\nfunction routeForElement(element){const link=element?.closest?.('a[href]');if(link)return routeForLink(link);const menuItem=element?.closest?.('[data-menu-id]');return routeForMenuKey(menuItem?.getAttribute('data-menu-id')||'')}\nfunction prepareInteractionFor(event){const path=routeForElement(event.target);for(const [name,route]of Object.entries(plan.routes)){if(route.path===path&&route.mode==='interaction')prepare([name])}}\ndocument.addEventListener('pointerover',prepareInteractionFor);\ndocument.addEventListener('focusin',prepareInteractionFor);\nfunction beginLoginWatch(){prepareAuthenticatedShell();if(!scheduled)loginWatch=window.setInterval(prepareAuthenticatedShell,250)}\nwindow.addEventListener('focus',prepareAuthenticatedShell);\nif(document.readyState==='loading')document.addEventListener('DOMContentLoaded',beginLoginWatch,{once:true});else beginLoginWatch();\n`

const scriptHash = createHash('sha256').update(scriptSource).digest('hex').slice(0, 12)
const scriptFilename = `delivery-preload-${scriptHash}.js`
const scriptPath = resolve(assetsDirectory, scriptFilename)
for (const filename of await readdir(assetsDirectory)) {
  if (filename.startsWith('delivery-preload-') && filename.endsWith('.js')) {
    await rm(resolve(assetsDirectory, filename))
  }
}
await writeFile(scriptPath, scriptSource)

const deliveryManifest = {
  version: 1,
  generated_at: new Date().toISOString(),
  script: `/assets/${scriptFilename}`,
  ...deliveryPlan,
}
await writeFile(deliveryManifestPath, `${JSON.stringify(deliveryManifest, null, 2)}\n`)

const indexHtml = await readFile(indexPath, 'utf8')
const injectedTag = `    <script type="module" data-cogguard-delivery-preload src="${deliveryManifest.script}"></script>`
const cleanedIndex = indexHtml.replace(/\s*<script type="module" data-cogguard-delivery-preload[^>]*><\/script>/g, '')
if (!cleanedIndex.includes('</head>')) throw new Error('Built index is missing </head>.')
await writeFile(indexPath, cleanedIndex.replace('</head>', `${injectedTag}\n  </head>`))

console.log(`Delivery preload plan generated: ${deliveryManifest.eager_routes.join(', ')} eager; ${deliveryManifest.interaction_routes.join(', ')} on interaction`)
