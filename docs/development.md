# 开发与验证

[返回产品首页](../README.md) · [Mac App 构建](../mac/README.md)

## 运行源码

后端与 CLI 使用 Python 3.10+ 标准库，页面使用原生 HTML、CSS 和 JavaScript。无需安装 npm 或 pip 依赖。

```sh
git clone https://github.com/JackieLeee/trace-agent-observatory.git
cd trace-agent-observatory
python3 agent_trace.py start
```

在浏览器打开 <http://127.0.0.1:8770/>。`serve` 在前台运行，`status` 查询状态，`stop` 停止服务。更换端口前先停止已有实例，再使用 `start --port 8771`。

## 构建 Mac App

需要 macOS 13+、Xcode 命令行工具和 python.org framework Python。在仓库根目录执行：

```sh
python3 mac/build.py
python3 mac/check_bundle.py mac/dist/Trace.app
python3 mac/build.py --install
```

更新已安装版本前先退出 App，并执行 `~/.local/bin/agent-trace stop`。源码更改需要重新打包后才会进入已安装的 App。构建按当前机器架构打包；Apple Silicon 已完成本机验收，Intel 构建尚未运行验收。

安装器保留上一版应用为 `~/Applications/.Trace.backup-*.app`，数据目录独立于应用包。运行环境随 App 打包，使用者不需要另外安装 Python。完整说明见 [Mac 构建文档](../mac/README.md)。

## 项目结构

| 位置 | 内容 |
| --- | --- |
| `app.js`、`app.css`、`live.js` | 任务与图谱界面、实时数据适配 |
| `theme.js`、`theme.css` | 浅色、深色与系统主题偏好 |
| `agent_trace.py` | CLI 与服务进程管理 |
| `trace_server.py`、`trace_store.py` | 本机 API、实时通知与持久化 |
| `mac/` | Mac 原生窗口、图标和构建脚本 |
| `examples/`、`checks/` | 接入示例与验证脚本 |

## 检查

```sh
python3 -m unittest discover -s checks -p 'test_service.py' -v
node checks/live.test.cjs
node checks/floating.test.cjs
node checks/floating-prefs.test.cjs
node checks/settings.test.cjs
xcrun swiftc mac/FloatingLayout.swift checks/floating_layout.swift -o /tmp/trace-floating-layout-check
/tmp/trace-floating-layout-check
xcrun swiftc mac/FloatingLayout.swift mac/FloatingController.swift checks/floating_preferences.swift -o /tmp/trace-floating-prefs-check
/tmp/trace-floating-prefs-check
node checks/model.test.cjs
node checks/theme.test.cjs
python3 checks/contrast.py
```

服务测试使用临时数据库和随机端口，覆盖 CLI、重启持久化、并发汇报、依赖校验、计划变更、图示版本固定、事件去重、SSE 重连和访问边界。页面另做真实 CLI 到浏览器验证；对比度脚本只覆盖所选语义色配对，不代表完整可访问性审计。
