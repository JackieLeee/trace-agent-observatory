# Trace — 本机 Agent 执行观测

本机单用户工作台：Agent 通过 CLI 汇报，页面展示主任务列表、嵌套子任务、加权进度和每项任务关联的架构／流程／时序图。SQLite 保存真实数据；SSE 通知页面获取最新快照。没有外部服务、图片素材或运行时第三方依赖。

## Mac App

构建并安装后，在 Finder 中打开 `~/Applications/Trace.app` 即可启动独立窗口和本机服务；运行时无需另装 Python。

- 原生标题栏、Dock 图标、窗口位置保存、Mac 菜单和 JSON 导出保存面板。
- `⌘1` 任务总览、`⌘2` 结构图谱、`⌘,` 外观设置、`⌘R` 重新载入。
- 浅色／深色设置同步到窗口外观；跟随系统继续由 macOS 控制。App 的外观偏好与浏览器分别保存。
- 关闭窗口后可从 Dock 重新打开；退出 App 后服务继续运行，Agent 不受影响。彻底停止服务仍使用 `~/.local/bin/agent-trace stop`。
- 数据库保存在 `~/.local/share/agent-trace`，独立于应用包。安装器将 `~/.local/bin/agent-trace` 指向 App 内的运行环境。
- 主任务右侧可废弃或永久删除；「已废弃」筛选可以查看并恢复任务。永久删除需要在 App 中确认，并移除任务及其子任务、计划、图示版本和运行记录，不删除任务中引用的工作文件。

当前构建为 Apple Silicon（arm64）、macOS 13+，已在本机验证。应用包约 62 MB，使用本地 ad-hoc 签名；未做 Developer ID 公证、外部分发或登录自启。

App 内附一份服务和页面代码，修改源码后需要重新打包。先退出 App 并停止本机服务，再运行：

```sh
cd /path/to/trace-agent-observatory
python3 mac/build.py --install
python3 mac/check_bundle.py mac/dist/Trace.app
```

构建需要本机 Xcode 命令行工具和 python.org framework Python，不下载第三方依赖；只为构建机器的架构打包。安装器保留上一版应用为 `~/Applications/.Trace.backup-*.app`，任务数据独立于应用包。完整构建说明见 `mac/README.md`。

## 启动与查看

需要 macOS / Linux、Python 3.10+。Mac App 安装后 CLI 位于 `~/.local/bin/agent-trace`，使用完整路径即可；未安装 App 时可从仓库根目录运行 `python3 agent_trace.py`。

```sh
~/.local/bin/agent-trace start
~/.local/bin/agent-trace status
# 浏览器打开 http://127.0.0.1:8770/
~/.local/bin/agent-trace stop
```

`start` 后台运行，重复调用会识别已有服务。`serve` 前台运行，可用于诊断。可用 `start --port 8771` 更换端口，但先停止已有实例。没有配置登录自启；重启电脑后再次运行 `start`。

CLI 本体是同目录的 `agent_trace.py`，也可以直接使用：

```sh
python3 agent_trace.py start
```

顶部「本机任务」展示真实持久化记录；「演示样例」展示原来的交互样例，互不写入。明暗主题支持浅色、深色、跟随系统，偏好单独保存；切换主题保留页面选择与回放位置。

## 最短 Agent 接入流程

以下 CLI 命令可以从任意工作目录执行；图示示例中的相对路径需要在仓库根目录运行。为每个主目标选择稳定且唯一的任务 ID；子任务 ID 在该主任务内唯一。

```sh
# 1. 确保服务运行
~/.local/bin/agent-trace start

# 2. 创建主任务；同样的 ID 和元数据重复提交不会创建重复项
~/.local/bin/agent-trace task create \
  --id my-task --title '实现文档检索' \
  --description '完成接口实现和验收' --owner coordinator

# 3. 提交完整执行计划；父任务通过 parent_id 建立嵌套关系
~/.local/bin/agent-trace plan put --task my-task --file - <<'JSON'
{
  "reason": "建立执行计划",
  "tasks": [
    {"id":"build","title":"实现与验证","agent":"coordinator"},
    {"id":"implement","parent_id":"build","title":"完成实现","agent":"builder","weight":70},
    {"id":"verify","parent_id":"build","title":"验证并交付","agent":"verifier","weight":30,"dependencies":["implement"]}
  ]
}
JSON

# 4. 只对叶子任务汇报；页面无需刷新
~/.local/bin/agent-trace task report --task my-task --node implement \
  --status running --progress 40 --current '正在实现检索接口'

~/.local/bin/agent-trace task report --task my-task --node implement \
  --status done --current '接口实现并通过单元验证' --done '完成接口' --artifact 'src/search.py'

~/.local/bin/agent-trace task report --task my-task --node verify \
  --status running --progress 20 --current '正在验证端到端行为'

~/.local/bin/agent-trace task report --task my-task --node verify \
  --status done --current '验收通过' --done '完成端到端验证'

~/.local/bin/agent-trace task show --task my-task
~/.local/bin/agent-trace task list
```

总体进度 `Σ(叶子权重 × 叶子进度) / Σ叶子权重`。父任务不重复计入，完成数也是叶子任务数。`done` 自动设为 100%。未完成的前置依赖会阻止子任务开始／完成；服务不执行或调度任务，Agent 自己决定下一步。

任务状态：`waiting`、`running`、`recovery`、`blocked`、`done`、`error`。父级汇总把异常与恢复显示为「自主恢复」。汇报 `recovery` 并用 `current` 说明当前处理，再汇报恢复后的状态即可。

遇到阻塞时，Agent 可以汇报原因以及正在采取的处理动作；主页会突出显示阻塞并支持筛选，详情可查看原因。恢复后重新汇报 `running` 或 `done`，当前阻塞提示会自动清除。阻塞由 Agent 自己处理，不会自动暂停其他子任务。

```sh
~/.local/bin/agent-trace task report --task my-task --node implement \
  --status blocked --blocker '等待接口凭据' --current '正在检查可用的测试凭据'
~/.local/bin/agent-trace task report --task my-task --node implement \
  --status running --current '凭据已就绪，继续实现'
```

`blocked` 必须提供非空 `--blocker`。这是当前状态，不是完整的阻塞历史；只能展示 Agent 主动汇报的阻塞，无法推测未汇报的情况。

`--done`、`--todo` 可重复，提交时替换对应列表。需要清空列表或批量字段时使用 JSON：

```sh
~/.local/bin/agent-trace task report --task my-task --node implement --file - <<'JSON'
{"status":"done","current":"实现完成","done":["接口完成","验证通过"],"todo":[],"artifact":"src/search.py"}
JSON
```

单个节点还支持 `objective`、`duration`、`agent`、`agent_role`。`artifact` 是产物说明／路径文本，页面显示提交摘要，不会任意读取本机文件。

废弃任务仍在 `task list` 和 `task show` 中，`archived_at` 为废弃时间（正常任务为 `null`），可以读取原进度和图示。CLI 不能废弃、恢复或删除任务；废弃期间，创建同 ID 的任务、替换计划、汇报进度、修改图示、开始或更新运行均会被服务拒绝。请由用户在 Mac App 恢复后再继续汇报。主列表和总体统计不包含已废弃任务。

计划调整重新执行 `plan put`，提交**完整计划**并写明 `--reason`。相同 ID 未显式覆盖的执行字段会保留；遗漏的节点从当前计划移除。可用 `--expected-version N` 防止并发替换计划；执行汇报可用 `--expected-revision N` 做乐观并发检查。不同节点的部分汇报不会相互覆盖。

## 图示与真实运行

图示和任务进度分别汇报，不会把任务状态自动猜测为图中运行步骤。一个任务可关联多张图；每张图都有稳定 ID。图示变更生成新版本，运行记录固定引用开始时的版本。

```sh
~/.local/bin/agent-trace diagram put --task my-task \
  --file examples/diagram.json

~/.local/bin/agent-trace diagram put --task my-task \
  --file examples/sequence.json

~/.local/bin/agent-trace run start --task my-task --diagram delivery-flow --id run-001

~/.local/bin/agent-trace run step --run run-001 --node implement \
  --status running --event-id implement-start --title '开始实现'

~/.local/bin/agent-trace run step --run run-001 --node implement --edge implemented \
  --status done --duration-ms 42 --event-id implement-done --title '实现完成'

~/.local/bin/agent-trace run step --run run-001 --node verify --edge verified \
  --status done --event-id verify-done --title '验证通过'

~/.local/bin/agent-trace run step --run run-001 --node deliver \
  --status done --event-id deliver-done --title '交付完成'

~/.local/bin/agent-trace run finish --run run-001 --status done
```

`--node` 和 `--edge` 可以重复。`event_id` 由 Agent 为一次逻辑汇报生成并在重试时复用：相同事件重复提交不重复计数，内容不一致返回冲突。运行结束后不可追加新步骤；下一次执行使用新的 run ID。异常步骤可先汇报 `error`，恢复后再汇报对应对象 `done`。

`duration_ms` 表示该条操作的耗时，不是从启动到现在的累计时间；回放展示所选事件前的耗时之和。未汇报的对象保持「未经过」，不会被自动标为完成。

图定义格式：

```json
{
  "id":"my-flow","kind":"flow","title":"数据处理",
  "nodes":[
    {"id":"read","title":"读取","description":"加载数据","inputs":["输入"],"outputs":["原始数据"]},
    {"id":"save","title":"保存","inputs":["原始数据"],"outputs":["结果"]}
  ],
  "edges":[{"id":"read-save","from":"read","to":"save","label":"数据"}]
}
```

`kind` 可以是 `flow` 或 `architecture`；默认自动布局，也可给每个节点提供一对非负 `x` / `y` 坐标。时序图用 `kind: sequence`、`participants` 和 `messages`，完整格式见 `examples/sequence.json`。时序运行的 `--node` 引用 **message ID**，不引用 participant ID。

## 给其他 Agent 的接入指令

把下面这段加入目标 Agent 的任务提示或项目说明即可；本次没有修改其他项目的 Agent 规则：

> 使用 `~/.local/bin/agent-trace` 汇报本机任务进度。先执行 `start`，为当前目标创建稳定 task ID，再用 `plan put` 提交带权重和依赖的子任务。只在开始、阶段完成、计划改变、恢复及最终交付时对叶子任务 `task report`，如实汇报，不模拟进度。CLI 失败时读取 JSON 错误，查询当前状态并处理。需要展示逻辑结构时单独 `diagram put`；实际运行时用 `run start/step/finish`，步骤引用图中 ID，重试复用 event_id。命令成功输出 JSON，错误输出到 stderr 并返回非零码。完整说明见 Trace 仓库的 `README.md`。

## 数据与接口

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

## 检查

```sh
cd /path/to/trace-agent-observatory
python3 -m unittest discover -s checks -p 'test_service.py' -v
node checks/live.test.cjs
node checks/model.test.cjs
node checks/theme.test.cjs
python3 checks/contrast.py
```

服务测试使用临时数据库和随机端口，覆盖 CLI、重启持久化、并发汇报、依赖校验、计划变更、图示版本固定、事件去重、SSE 重连和访问边界。页面另做真实 CLI 到浏览器验证；对比度脚本只覆盖所选语义色配对，不代表完整可访问性审计。
