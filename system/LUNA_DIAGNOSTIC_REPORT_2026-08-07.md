# Luna 运行链路诊断报告

日期：2026-08-07（Asia/Shanghai）
范围：`G:\CISCN\CogGuard\system`；本次只读诊断与验证，未修改生产源代码。

## 结论摘要

当前趋势预测页面失败的首要原因是认证与运行态不一致，不是前端 URL 拼接或基础健康接口故障：

1. 现场 `127.0.0.1:8000/api/v1/health` 返回 `200 {"status":"ok"}`，但传播分析和预测接口在无有效 Bearer token 时全部返回 `401`。
2. `system/.env` 只有 `BACKEND_DEBUG=true`，没有 `BACKEND_ENV=local`、`PREVIEW_AUTH_ENABLED=true`、`PREVIEW_AUTH_TOKEN`，因此代码中的本地预览令牌旁路不会生效；请求 query 中加 `preview=1` 也不会改变认证结果。
3. 8000 的现场进程关系异常：`PID 32088` 是当前 system venv 的 uvicorn 父进程，但监听者 `PID 6716` 是 `D:\Anaconda\python.exe` 子进程。随后在诊断期间 8000 监听者退出，端口变为连接失败，说明旧/重载进程链不稳定。
4. 历史运行日志同时记录过同一路径 `200` 和 `401`。成功记录使用的是事件 `trump_visit_2026_05_21`，而页面默认/本次试验的 `default` 没有证据表明存在数据；认证恢复后仍需判断是否返回结构化 `model_status=unavailable`/abstain。
5. 当前生产代码的前后端响应契约是匹配的：前端发 `POST .../model-event-predict`，query 传参、空 body；后端返回顶层 `{code,data,msg}`，Axios 拦截器解包为 `data` 后供页面使用。旧进程若加载旧代码，则可能仍接受 `prediction_horizon`，而当前源码明确拒绝它。

## 准确入口与脚本

后端启动入口：

```powershell
cd G:\CISCN\CogGuard\system\backend
\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`start-system.ps1` 会运行数据库迁移，然后用上述入口启动后端；前端命令为：

```powershell
cd G:\CISCN\CogGuard\system\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

`start-preview.ps1` 使用相同入口但后端不带 `--reload`。两个脚本都尝试清理 8000 和 5173 的旧 owner，并要求 owner 命令行匹配 `uvicorn app.main:app` / Vite。实际前端 `package.json` scripts 只有：

```text
dev     = vite
build   = vue-tsc -b && node --max-old-space-size=4096 ./node_modules/vite/bin/vite.js build
preview = vite preview
```

Vite 配置把 `/api` 代理到 `http://localhost:8000`，不是 `127.0.0.1`；在本机通常等价，但应使用同一 host 做最终验证。

## 进程与端口证据

检查命令：

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object {$_.LocalPort -in 5173,5174,5175,8000} |
  Select-Object LocalAddress,LocalPort,OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId = 6716" |
  Select-Object ProcessId,ParentProcessId,Name,CommandLine
Get-CimInstance Win32_Process -Filter "ProcessId = 32088" |
  Select-Object ProcessId,ParentProcessId,Name,CommandLine
```

诊断时结果：

```text
127.0.0.1:8000 -> PID 6716
PID 6716  PPID 32088  D:\Anaconda\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
PID 32088 PPID 25320  G:\CISCN\CogGuard\system\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
127.0.0.1:5175 -> PID 22140
PID 22140 PPID 39176  node ...\system\frontend\node_modules\.bin\..\vite\bin\vite.js --host 127.0.0.1 --port 5175
```

5173 的 Windows owner 是 Docker/WSL relay（`com.docker.backend.exe` / `wslrelay.exe`），而不是可直接对应到当前 system/frontend 的 Node 命令；这与脚本预期的 5173 owner 不一致。当前可确认的 system frontend 进程是 5175，日志也显示它是由 `frontend-system-current` 启动的。

## HTTP 验证

无认证请求命令：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/openapi.json -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/api/v1/propagation/observed-analysis?event_id=default -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/api/v1/propagation/model-event-predict?event_id=default -Method Post -UseBasicParsing
```

实测摘要（8000 尚在监听时）：

```text
GET  /api/v1/health                         -> 200  {"status":"ok"}
GET  /openapi.json                          -> 200  OpenAPI 3.1，包含 v1 propagation routes
GET  /api/v1/propagation/analyze             -> 401  empty body
GET  /api/v1/propagation/observed-analysis   -> 401  empty body
POST /api/v1/propagation/model-event-predict -> 401 empty body
POST /api/v1/propagation/model-predict       -> 401 empty body
```

错误参数也先被认证依赖拦截，因此无 token 时不能用 `0.05` 或 `prediction_horizon=3` 判断业务层响应。

认证后复现命令（仅使用已有本地配置生成 5 分钟诊断 JWT；没有写入数据库或源代码）：

```powershell
$py = 'G:\CISCN\CogGuard\system\backend\.venv\Scripts\python.exe'
$token = & $py -c "from jose import jwt; from datetime import datetime,timedelta,timezone; print(jwt.encode({'sub':'21','role':'admin','exp':datetime.now(timezone.utc)+timedelta(minutes=5),'type':'access'}, 'change-me-to-a-random-secret-key-in-production', algorithm='HS256'))"
$headers = @{ Authorization = "Bearer $token" }
Invoke-WebRequest 'http://127.0.0.1:8000/api/v1/auth/profile' -Headers $headers -UseBasicParsing
Invoke-WebRequest 'http://127.0.0.1:8000/api/v1/propagation/model-event-predict?event_id=trump_visit_2026_05_21&platform=twitter&observation_ratio=0.5&top_k=3' -Headers $headers -Method Post -UseBasicParsing
```

认证后的实测结果：

```text
GET  /api/v1/auth/profile -> 200; id=21, username=accounts_check_20260807, role=analyst, is_active=true
POST /api/v1/propagation/model-event-predict?... -> 200
data.status=data_insufficient
data.model_status=unavailable
data_scope.posts=0, comments=0, event_id=trump_visit_2026_05_21, platform=twitter
macro.observed_size=0, macro.trend_points=[]
micro.candidate_count=0
note=No timestamped observed posts are available for model inference.
```

因此响应契约本身在当前实例可用，且不是 500 或前端无法解析；认证恢复后页面应显示结构化“数据不足/模型不可用”状态。要得到趋势点，必须先导入或确认该 event/platform 的带时间戳帖子数据。

源码定义的可调用方式：

```text
POST /api/v1/propagation/model-event-predict
  ?event_id=trump_visit_2026_05_21
  &platform=twitter
  &top_k=10
  &observation_ratio=0.5
  [&observed_until=2026-05-21T00:00:00Z]
  body: empty/null
Authorization: Bearer <real access token>
```

当前源码允许 `observation_ratio` 0.1 到 0.5；`prediction_horizon` 即使在 query schema 中隐藏，传入后也返回 `422`，因为部署模型使用 normalized trajectory steps。前端目前没有传 `prediction_horizon`，只传 `event_id/platform/top_k/observed_until/observation_ratio`。

## 认证结论

认证入口是：

```text
POST /api/v1/auth/login
body: {"username":"...","password":"..."}
```

成功返回 `{code:0,data:{access_token,refresh_token,token_type},msg:"ok"}`，之后必须发送 `Authorization: Bearer <access_token>`。当前 system/.env 没有默认管理员密码，也没有预览 token 配置；代码的预览旁路还要求 `PREVIEW_AUTH_ENABLED`、`BACKEND_DEBUG`、`BACKEND_ENV=local` 和非空 token 全部满足。

## 数据与响应契约证据

历史 `runtime-logs/backend-system-current.out.log` 记录过：

```text
POST ...model-event-predict?event_id=trump_visit_2026_05_21... -> 200 OK
GET  ...observed-analysis?event_id=trump_visit_2026_05_21... -> 200 OK
POST ...event_id=trump_visit_2026_05_21&platform=twitter... -> 401 Unauthorized
POST ...event_id=trump_visit_2026_05_21&observation_ratio=0.5&top_k=5 -> 200 OK
POST ...event_id=trump_visit_2026_05_21&observation_ratio=0.3&top_k=3 -> 200 OK
```

这证明已认证的真实事件链路曾经可用，但日志没有保存完整 JSON body，不能仅凭日志断言模型一定返回 `available`。测试日志还显示 `86 passed, 2 failed`，失败涉及数据源失败结果缺少 `event_id` 以及一个 event-scoped prediction 预期 `ok` 实际为 `model_error`；这支持“数据/模型状态仍需单独验证”，但不是当前无认证 401 的直接原因。

## 下一步由主智能体执行

1. 清理并确认唯一后端：停止 8000 上的旧/重载链，确保唯一命令来自 `system\backend\.venv\Scripts\python.exe`，然后用 `start-preview.ps1` 或明确的 venv uvicorn 启动；不要让 5173 被 Docker/WSL relay 或其他项目占用。
2. 使用实际账号登录获取 JWT；不要把 `preview=1` 当认证。若主智能体要支持本地 preview，应明确配置 `BACKEND_ENV=local`、`PREVIEW_AUTH_ENABLED=true`、`PREVIEW_AUTH_TOKEN=<local-only-token>` 后重启，并仅在本地使用。
3. 先调用 `GET /api/v1/propagation/observed-analysis?event_id=trump_visit_2026_05_21&platform=twitter&node_limit=10`，确认数据 scope 和行数，再调用预测 endpoint；不要使用 `event_id=default`，除非先确认该事件确实存在数据。
4. 对认证后的预测响应记录 HTTP 状态、顶层 keys、`data.status`、`data.model_status`、`data.macro.observed_size`、`len(data.macro.trend_points)`、`data.micro.candidate_count` 和 `data.note`，据此区分 available、结构化 abstain 和 500/契约错误。
5. 若认证后仍失败，再处理已有测试失败和旧进程加载旧契约的问题；本次没有修改这些生产源代码。
