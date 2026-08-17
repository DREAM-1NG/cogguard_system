import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const systemRoot = resolve(__dirname, '..', '..')
const startupScript = readFileSync(resolve(systemRoot, 'start-system.ps1'), 'utf8')
const demoWarmupScript = readFileSync(resolve(systemRoot, 'ops', 'Invoke-DemoWarmup.ps1'), 'utf8')
const mongoIndexScript = readFileSync(resolve(systemRoot, 'ops', 'Apply-MongoPerformanceIndexes.ps1'), 'utf8')
const frontendPackage = JSON.parse(readFileSync(resolve(systemRoot, 'frontend', 'package.json'), 'utf8'))
const nginxTemplate = readFileSync(resolve(systemRoot, 'deploy', 'nginx', 'default.conf.template'), 'utf8')

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
  assert.doesNotMatch(startupScript, /Demo data warmup failed with exit code/)
  assert.doesNotMatch(startupScript, /\$warmupArguments/)
  assert.match(startupScript, /\$backendPythonPath = \[System\.IO\.Path\]::GetFullPath\(\$backendPython\)/)
  assert.match(startupScript, /\[string\]::Equals\(/)
  assert.match(startupScript, /\$executablePath,\s*\$backendPythonPath/)
  assert.match(startupScript, /\(\?i\)\(\?:\^\|\\s\)-m\\s\+celery/)
  assert.doesNotMatch(startupScript, /celery\.\*account_training\|account_training\.\*celery/)
  assert.match(startupScript, /\$hasDockerOwner = \$portOwnerProcesses \| Where-Object/)
  assert.match(startupScript, /wslrelay/)
  assert.doesNotMatch(startupScript, /--reload/)
})

test('warms the propagation projection with the delivery page hierarchy budget', () => {
  const observedAnalysisRequest = demoWarmupScript.match(
    /\/api\/v1\/propagation\/observed-analysis'[\s\S]*?\}\s+-Token \$accessToken/,
  )

  assert.ok(observedAnalysisRequest, 'the demo warmup must request observed propagation analysis')
  assert.match(observedAnalysisRequest[0], /node_limit\s*=\s*160/)
  assert.match(observedAnalysisRequest[0], /first_layer_limit\s*=\s*40/)
  assert.match(observedAnalysisRequest[0], /second_layer_limit\s*=\s*80/)
  assert.doesNotMatch(observedAnalysisRequest[0], /node_limit\s*=\s*300/)
})

test('warms the demo event prediction cache for the propagation forecast tab', () => {
  const predictionWarmupRequest = demoWarmupScript.match(
    /\/api\/v1\/propagation\/model-event-predict'[\s\S]*?\}\s+-Token \$accessToken/,
  )

  assert.ok(predictionWarmupRequest, 'the demo warmup must generate the forecast cache')
  assert.match(predictionWarmupRequest[0], /event_id\s*=\s*\$EventId/)
  assert.match(predictionWarmupRequest[0], /observation_ratio\s*=\s*0\.5/)
  assert.match(predictionWarmupRequest[0], /top_k\s*=\s*10/)
  assert.match(predictionWarmupRequest[0], /force_refresh\s*=\s*\$true/)
})

test('prepares indexes through the reused MongoDB container when infrastructure already exists', () => {
  assert.match(startupScript, /\$reusedInfrastructure\s*=\s*\$true/)
  assert.match(startupScript, /-ContainerName 'cogguard-mongodb'/)
  assert.match(mongoIndexScript, /\[string\]\$ContainerName/)
  assert.match(mongoIndexScript, /if \(\$ContainerName\)/)
  assert.match(mongoIndexScript, /\$arguments = @\(\s*if \(\$ContainerName\)/)
  assert.match(mongoIndexScript, /if \(\$ContainerName\) \{\s*'exec'/)
  assert.doesNotMatch(mongoIndexScript, /if \(\$ContainerName\) \{\s*'exec', '-T'/)
  assert.match(mongoIndexScript, /\$arguments \+= if \(\$ContainerName\) \{ @\(\$ContainerName\) \}/)
})

test('applies every Alembic head so independent migration branches deploy together', () => {
  assert.match(startupScript, /& \$backendPython -m alembic upgrade heads/)
  assert.doesNotMatch(startupScript, /& \$backendPython -m alembic upgrade head\s*(?:\r?\n|$)/)
})

test('allows the static delivery proxy enough time to connect to the local analysis backend', () => {
  const apiLocation = nginxTemplate.match(/location \/api\/ \{[\s\S]*?\n    \}/)?.[0] || ''
  const streamLocation = nginxTemplate.match(/location ~ \^\/api\/v2\/review-cases\/[\^\/\]\+\/events\/stream\$ \{[\s\S]*?\n    \}/)?.[0] || ''

  assert.match(apiLocation, /proxy_connect_timeout 30s;/)
  assert.match(apiLocation, /proxy_read_timeout 185s;/)
  assert.match(streamLocation, /proxy_connect_timeout 30s;/)
  assert.match(streamLocation, /proxy_read_timeout 185s;/)
})
