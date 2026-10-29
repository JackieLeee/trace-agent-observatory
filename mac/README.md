# Trace Mac app

[返回产品首页](../README.md) · [开发与验证](../docs/development.md)

AppKit + WKWebView 窗口，复用现有本机服务与主题系统。不是浏览器快捷方式；服务、页面和 Python 标准运行环境均随 `.app` 打包。内置后端与 CLI 保持同一 HTTP 协议和默认数据目录。

## 构建

构建机器需有 Xcode 命令行工具和 python.org framework Python。运行环境从该 Python 复制，排除第三方包和测试模块；重定位动态库路径、按当前 CPU 架构精简，然后逐项本地签名。不会下载包或修改系统 Python。

```sh
python3 mac/build.py                 # mac/dist/Trace.app
python3 mac/check_bundle.py mac/dist/Trace.app
python3 mac/build.py --install       # 安装到 ~/Applications/Trace.app 并更新 CLI
```

更新前先退出 App、执行 `~/.local/bin/agent-trace stop`。安装器只替换相同 bundle ID 的应用；上一版保留为 `~/Applications/.Trace.backup-*.app`。原 CLI 文件首次替换时备份为 `~/.local/bin/agent-trace.before-mac-app`。数据库不进入构建或安装步骤。

若应用移动到其他文件夹，应用自身仍能运行，内附 CLI 也能通过 `APP路径/Contents/Resources/bin/agent-trace` 使用；当前 `~/.local/bin/agent-trace` 入口指向安装位置，需要随之调整。

## 行为

快捷键：`⌘1` 打开任务总览，`⌘2` 打开结构图谱，`⌘,` 打开外观设置，`⌘R` 重新载入。外观偏好在 App 与浏览器中分别保存。

- 启动执行内附 CLI `start`，复用已确认的本机服务实例，再载入该本机地址。
- 网页仅可导航到当前服务和本地下载链接；用户点击的外部 HTTP 链接交给系统浏览器。
- 默认持久化 WebKit 存储保留主题；原生标题栏跟随网页的显式偏好，system 模式解除窗口覆盖。
- 下载交给原生 `NSSavePanel`；编辑菜单提供标准复制、粘贴和全选。
- 废弃、恢复和永久删除仅由 App 的原生桥接执行；永久删除显示确认对话框。App 用独立凭证与服务通信，网页和 CLI 不获得该凭证。
- 关闭窗口不会终止程序，Dock 重新点击可恢复窗口；退出程序也不停止后端，保证 Agent 持续汇报。
- 本地端口或启动失败会显示错误和重试按钮。未安装后台登录项。

## 验证与边界

`check_bundle.py` 将应用复制到一个带空格的新路径，清空 PATH，使用临时数据库检查内置 CLI、依赖进度、图示运行和重启持久化，并在运行后检查签名有效。测试不会写入真实数据库。

另在实际 App 中检查：原有任务可见、CLI 汇报实时更新、深浅色和窗口外观、原生导出生成有效 JSON、退出重开后的状态恢复。

当前只在本机 Apple Silicon Mac 验证。构建脚本也支持在 Intel Mac 上生成对应架构，但未运行验收。最低目标 macOS 13；使用 ad-hoc 本地签名，没有 Developer ID 公证和外部分发安装器。
