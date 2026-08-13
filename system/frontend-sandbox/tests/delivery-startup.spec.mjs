import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const systemRoot = resolve(__dirname, '..', '..')
const startupScript = readFileSync(resolve(systemRoot, 'start-system.ps1'), 'utf8')
const frontendPackage = JSON.parse(readFileSync(resolve(systemRoot, 'frontend', 'package.json'), 'utf8'))

test('uses the optimized static delivery path by default', () => {
  assert.equal(frontendPackage.scripts.build, 'npm run build:optimized')
  assert.match(frontendPackage.scripts['build:optimized'], /generate-delivery-preload\.mjs/)
  assert.match(frontendPackage.scripts['build:optimized'], /verify-build\.mjs/)
  assert.match(startupScript, /\[switch\]\$DevelopmentFrontend/)
  assert.match(startupScript, /--profile production-ui up -d --build frontend_static/)
  assert.match(startupScript, /Wait-HttpEndpoint -Name 'Backend API' -Url 'http:\/\/127\.0\.0\.1:8000\/api\/v2\/health'/)
  assert.match(startupScript, /Preparing idempotent MongoDB delivery indexes/)
  assert.match(startupScript, /-DockerExecutable \$dockerExe -DryRun/)
  assert.match(startupScript, /\[switch\]\$DemoWarmup/)
  assert.match(startupScript, /Invoke-DemoWarmup\.ps1/)
  assert.match(startupScript, /Preloading authenticated demo data before frontend delivery/)
  assert.match(startupScript, /\$warmupParameters = @\{/)
  assert.match(startupScript, /BackendOrigin = 'http:\/\/127\.0\.0\.1:8000'/)
  assert.match(startupScript, /& \$warmupScript @warmupParameters/)
  assert.doesNotMatch(startupScript, /\$warmupArguments/)
  assert.match(startupScript, /\$backendPythonPath = \[System\.IO\.Path\]::GetFullPath\(\$backendPython\)/)
  assert.match(startupScript, /\[string\]::Equals\(/)
  assert.match(startupScript, /\$executablePath,\s*\$backendPythonPath/)
  assert.match(startupScript, /\(\?i\)\(\?:\^\|\\s\)-m\\s\+celery/)
  assert.doesNotMatch(startupScript, /celery\.\*account_training\|account_training\.\*celery/)
  assert.doesNotMatch(startupScript, /--reload/)
})
