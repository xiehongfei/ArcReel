---
id: service-management
title: 服务启停与运维脚本
sidebar_position: 3
update_docs: fact-check
---

# 服务启停与运维脚本 {#service-management}

本页说明本地开发服务的启停脚本用法，以及生产部署下服务启停与日志的速查命令。部署配置、升级、备份与恢复见[部署与运维](deployment.md)，SQLite 到 PostgreSQL 的迁移见[从 SQLite 迁移到 PostgreSQL](migrate-to-postgres.md)。

## 本地开发：scripts/dev.py {#dev-script}

`scripts/dev.py` 管理从源码启动的后端与前端：服务在后台运行，PID、启动时间与日志落在 `.dev/` 下。脚本只用标准库，可直接执行，不需要 `uv` 或项目 venv，Python 3.9+ 即可；在任意目录调用都可以，工作目录按脚本位置推导。脚本依赖 POSIX 进程组信号，仅支持 macOS、Linux 与 WSL2。

### 命令 {#dev-script-commands}

| 命令 | 作用 |
| --- | --- |
| `./scripts/dev.py help` | 列出全部命令与参数 |
| `./scripts/dev.py setup` | 首次准备：`uv sync`、`pnpm install`、生成 `.env`、`alembic upgrade head`、安装 git 钩子；可重复执行 |
| `./scripts/dev.py start [服务]` | 后台启动服务，服务取 `backend`、`frontend` 或 `all`（默认）；等待端口就绪后返回 |
| `./scripts/dev.py stop [服务]` | 停止服务，先发 SIGTERM，超过宽限时间再发 SIGKILL |
| `./scripts/dev.py restart [服务]` | 先停止再启动 |
| `./scripts/dev.py status` | 显示运行状态、端口、访问地址与就绪探测结果 |
| `./scripts/dev.py logs [-f] [-n 行数] [服务]` | 显示日志末尾若干行（默认 80 行）；`-f` 持续跟踪新日志，按 Ctrl-C 退出 |
| `./scripts/dev.py doctor` | 检查 uv、node、pnpm 版本、`.env`、依赖目录与端口占用 |

`.env` 缺失时，`setup` 与 `start` 由 `.env.example` 复制一份，`AUTH_PASSWORD` 留空并在首次启动时自动生成。

### 参数 {#dev-script-options}

- `start --timeout 秒`：等待就绪的最长秒数，默认 60；取 0 表示发完命令即返回。
- `stop --timeout 秒`：SIGTERM 宽限秒数，默认 10。
- `restart --timeout 秒`：重启后等待就绪的最长秒数，默认 60。
- `stop --force`：跳过进程身份校验，强制停止；`restart --force` 只作用于停止阶段。

### 运行文件与端口 {#dev-script-files}

- 状态写在 `.dev/run/`，记录 PID、进程组与启动时间，`status` 与 `stop` 读取这份状态。
- 日志追加在 `.dev/logs/`，按服务分文件；`logs -f` 同时跟踪多个服务时用 `[backend]`、`[frontend]` 前缀区分来源。
- 端口：后端 `1241`，前端 `5173`。`.dev/` 已加入 `.gitignore`，不会进入提交。

端口被其他进程占用时，脚本报告占用者 PID 并放弃启动，不会结束该进程；停止前用 `ps` 校验进程身份，命令与记录不符时拒绝停止。退出码：0 表示成功，1 表示检查或操作失败（例如服务没有全部运行），2 表示用法错误。

## 生产部署：Docker Compose {#production-compose}

生产部署在 `deploy/`（SQLite）或 `deploy/production/`（PostgreSQL）目录下用 Docker Compose 管理：

| 操作 | 命令 |
| --- | --- |
| 启动 | `docker compose up -d` |
| 查看状态 | `docker compose ps` |
| 查看日志 | `docker compose logs --tail=100 arcreel` |
| 持续跟踪日志 | `docker compose logs -f arcreel` |
| 重启 | `docker compose restart arcreel` |
| 停止并移除容器 | `docker compose down` |

健康检查、升级与数据持久化的完整说明见[部署与运维](deployment.md)，检查与排障命令另见其中[健康检查和日志](deployment.md#health-and-logs)一节。
