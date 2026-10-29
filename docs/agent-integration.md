# Agent 接入指南

[返回产品首页](../README.md)

Mac App 安装后，以下命令使用 `~/.local/bin/agent-trace`。从源码运行时，将这一命令替换为 `python3 agent_trace.py`，并在仓库根目录执行。

## 创建任务与汇报进度

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

`kind` 可以是 `flow` 或 `architecture`；默认自动布局，也可给每个节点提供一对非负 `x` / `y` 坐标。时序图用 `kind: sequence`、`participants` 和 `messages`，完整格式见 [`examples/sequence.json`](../examples/sequence.json)。时序运行的 `--node` 引用 **message ID**，不引用 participant ID。

## 给其他 Agent 的接入指令

把下面这段加入目标 Agent 的任务提示或项目说明即可：

> 使用 `~/.local/bin/agent-trace` 汇报本机任务进度。先执行 `start`，为当前目标创建稳定 task ID，再用 `plan put` 提交带权重和依赖的子任务。在开始、阶段完成、计划改变、阻塞、恢复及最终交付时对叶子任务 `task report`，如实汇报，不模拟进度。阻塞时提供 `status=blocked`、`blocker` 原因及 `current` 处理进展，解除后更新状态。CLI 失败时读取 JSON 错误，查询当前状态并处理。需要展示逻辑结构时单独 `diagram put`；实际运行时用 `run start/step/finish`，步骤引用图中 ID，重试复用 event_id。命令成功输出 JSON，错误输出到 stderr 并返回非零码。完整说明见 Trace 仓库的 `docs/agent-integration.md`。
