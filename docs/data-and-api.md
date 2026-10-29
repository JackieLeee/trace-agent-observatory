# 数据与 API

[返回产品首页](../README.md) · [Agent 接入指南](agent-integration.md)


默认数据目录：`~/.local/share/agent-trace/`。

- `trace.sqlite3`：任务、计划版本、图示版本、运行与步骤，SQLite WAL 事务写入。
- `auth.token`：本地写入凭证，CLI 自动读取；不要提交到代码仓库或贴到页面。
- `app.token`：Mac App 用于废弃、恢复和删除任务的独立本机凭证；不会传给网页或普通 CLI。
- `service.json`：进程标识和地址，防止停止其他进程。
- `service.log`：服务启动与异常诊断，不是任务执行日志面板。

服务停止后可备份整个数据目录。`--data-dir PATH` 必须放在子命令之前；同一自定义目录用于启动、停止和汇报。`--url http://127.0.0.1:PORT` 也放在子命令之前。

HTTP API v1（JSON，所有写入需 `Authorization: Bearer <本机 token>`）：

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| GET | `/api/health` | 服务标识、实例与数据版本 |
| GET | `/api/state` | 当前完整快照，含固定版本的运行定义 |
| GET | `/api/events` | SSE 数据版本通知；重连后读取最新快照 |
| POST | `/api/tasks` | 主任务元数据 |
| PUT | `/api/tasks/{id}/plan` | `{tasks:[], reason?, expected_version?}` |
| PATCH | `/api/tasks/{id}/nodes/{node}` | 叶子任务执行字段，支持 `expected_revision` |
| PUT | `/api/tasks/{id}/diagrams` | 图示定义 |
| POST | `/api/tasks/{id}/diagrams/{diagram}/runs` | `{id?, version?}` |
| POST | `/api/runs/{run}/steps` | `{event_id?, node_ids:[], edge_ids:[], status, title?, duration_ms?}` |
| POST | `/api/runs/{run}/finish` | `{status: "done" 或 "error"}` |

断线时页面保留内存中的最后快照并标记断线；恢复后自动重连并读取最新数据。浏览器刷新后从服务重新加载；页面不是离线应用。

仅监听 `127.0.0.1`，校验 Host / Origin，无跨域写入；网页不持有写入 token，静态路径不暴露数据库与凭证。生命周期操作使用 App 独立凭证和任务版本检查。面向可信的同机用户和 Agent；同一系统用户下拥有文件权限的程序仍可直接访问数据和凭证，这不是抵御恶意本机进程的隔离机制。

本版规模上限：单个请求 2 MiB、单任务 500 个计划节点、层级／依赖深度 64；单图最多 200 个节点、500 条边，时序图最多 12 个参与方和 200 条消息。采用完整状态快照，适合本机中小规模任务；未实现分页、保留期清理、远程协作、MCP、登录自启或 Agent 自动执行。


## 时间与周报读取

`task list` 输出各主任务的当前摘要，`task show --task <ID>` 输出子任务、图示和运行记录。两者均输出 JSON，包含已废弃任务，可供周报 Agent 只读采集。

主任务保存 `created_at`、`updated_at` 和 `archived_at`；子任务目前没有独立的创建、开始和完成时间，也没有每次进度汇报的完整历史。`updated_at` 只表示主任务最近一次变化，不能用它证明某项成果发生在某一周。图示运行有自己的时间与步骤记录，不等同于子任务的工作历史。日期按 UTC 保存，统计时需转换到所需时区。
