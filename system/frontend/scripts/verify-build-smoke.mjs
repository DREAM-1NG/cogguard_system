import { spawn } from 'node:child_process'
import { readdir, stat } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve('.')
const dist = resolve(root, 'dist')
const port = 4173
const preview = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(port)], {
  cwd: root,
  stdio: 'ignore',
})

const sleep = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms))
const urls = [`http://127.0.0.1:${port}/`, `http://127.0.0.1:${port}/dashboard`, `http://127.0.0.1:${port}/risk`]

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) files.push(...await filesUnder(path))
    else files.push(path)
  }
  return files
}

try {
  let ready = false
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(urls[0])
      if (response.ok) {
        ready = true
        break
      }
    } catch {}
    await sleep(200)
  }
  if (!ready) throw new Error('Vite preview server did not become ready')

  for (const url of urls) {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`)
  }

  const assetFiles = (await filesUnder(dist)).filter((path) => /\.(?:js|css|geojson)$/.test(path))
  for (const path of assetFiles) {
    const relative = path.slice(dist.length).replaceAll('\\', '/')
    const response = await fetch(`http://127.0.0.1:${port}${relative}`)
    if (!response.ok) throw new Error(`${relative} returned HTTP ${response.status}`)
  }
  console.log(`Build smoke passed: ${urls.length} routes, ${assetFiles.length} assets`)
} finally {
  preview.kill('SIGTERM')
}
