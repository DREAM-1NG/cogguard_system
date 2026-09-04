# GPU_SETUP_TEMPLATE

把下面模板复制到本地未跟踪文件后再填写。不要把真实主机、密钥、token、Cookie、私有路径提交到仓库。

## 1. Runner 信息

| 字段 | 占位值 |
|------|------|
| runner_name | `local-cuda` / `lab-gpu` / `vast-01` |
| provider | `local` / `ssh` / `modal` / `vast` |
| technology_line | `tech-01` / `tech-02` / `tech-03` |
| branch | `aris/t*-...` |

## 2. 远端连接

| 字段 | 占位值 |
|------|------|
| remote_host | `<hostname-or-ip>` |
| remote_port | `<port>` |
| remote_user | `<username>` |
| ssh_key_path | `<local-private-key-path>` |
| remote_workspace | `<remote-repo-root>` |

## 3. 环境准备

| 字段 | 占位值 |
|------|------|
| conda_env | `<env-name>` |
| activate_cmd | `conda activate <env-name>` |
| python_version | `3.11+` |
| torch_cuda | `<optional>` |

## 4. 运行命令

| 字段 | 占位值 |
|------|------|
| sync_cmd | `<rsync/scp/git pull command>` |
| backend_test_cmd | `cd new-system/backend && uv run pytest ...` |
| experiment_cmd | `<embedding / evaluation / notebook-free command>` |
| collect_cmd | `<copy summary back into TASK_TRACKER.md>` |

## 5. 安全说明

- 真正的 SSH 配置请放在本地 `~/.ssh/config` 或系统环境变量
- 数据集、模型权重、日志输出默认不入库
- 需要共享结论时，只回写稳定摘要到仓库 Markdown
