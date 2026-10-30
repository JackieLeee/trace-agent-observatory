import AppKit
import WebKit

final class NoRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

enum LocalService {
    struct Info { let url: URL; let dataDirectory: URL }
    static func start(cli: URL) throws -> Info {
        let process = Process()
        let output = Pipe()
        process.executableURL = cli
        #if TRACE_UI_TEST
        guard let directory = Bundle.main.object(forInfoDictionaryKey: "TraceTestDataDirectory") as? String,
              directory.hasPrefix("/") else { throw NSError(domain: "TraceUITest", code: 1) }
        process.arguments = ["--data-dir", directory, "start", "--port", "0"]
        #else
        process.arguments = ["start"]
        #endif
        process.standardOutput = output
        process.standardError = output
        try process.run()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0,
              let result = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let directory = result["data_dir"] as? String, directory.hasPrefix("/"),
              let value = result["url"] as? String,
              let url = URL(string: value), url.scheme == "http",
              ["127.0.0.1", "localhost"].contains(url.host ?? ""),
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              ["", "/"].contains(url.path), url.port != nil else {
            let detail = String(data: data, encoding: .utf8) ?? "无法启动本机服务。"
            throw NSError(domain: "Trace", code: 1, userInfo: [NSLocalizedDescriptionKey: detail])
        }
        return Info(url: url, dataDirectory: URL(fileURLWithPath: directory, isDirectory: true).standardizedFileURL)
    }
}

final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
}

final class FloatingDragHandle: NSView {
    var afterDrag: (() -> Void)?
    var showMenu: (() -> Void)?
    private var dragStart: NSPoint?
    private var windowStart: NSPoint?
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func resetCursorRects() { addCursorRect(bounds, cursor: .openHand) }
    private func screenPoint(_ event: NSEvent) -> NSPoint {
        // Read the event's own position; the global cursor may have advanced while events were queued.
        if let point = event.cgEvent?.location {
            return NSPoint(x: point.x, y: (NSScreen.screens.first?.frame.maxY ?? 0) - point.y)
        }
        return window?.convertPoint(toScreen: event.locationInWindow) ?? .zero
    }
    override func mouseDown(with event: NSEvent) {
        dragStart = screenPoint(event)
        windowStart = window?.frame.origin
    }
    override func mouseDragged(with event: NSEvent) {
        guard let dragStart, let windowStart else { return }
        let mouse = screenPoint(event)
        window?.setFrameOrigin(NSPoint(x: windowStart.x + mouse.x - dragStart.x,
                                      y: windowStart.y + mouse.y - dragStart.y))
    }
    override func mouseUp(with event: NSEvent) {
        if dragStart != nil { mouseDragged(with: event); afterDrag?() }
        dragStart = nil
        windowStart = nil
    }
    override func rightMouseDown(with event: NSEvent) { showMenu?() }
}

final class TraceApp: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate,
                       WKScriptMessageHandler, WKDownloadDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var floatingPanel: NSPanel?
    private var floatingWebView: WKWebView?
    private var floatingDragHandle: NSView?
    private var floatingSide = FloatingSide(rawValue: UserDefaults.standard.string(forKey: "TraceFloatingEdge") ?? "right") ?? .right
    private var floatingDocked = true
    private var floatingExpanded = false
    private var floatingHeight = 156
    private var loadingView: NSView!
    private var progress: NSProgressIndicator!
    private var statusLabel: NSTextField!
    private var retryButton: NSButton!
    private var serviceURL: URL?
    private var serviceDataDirectory: URL?
    private var connecting = false
    private var lifecycleBusy = false
    private let noRedirects = NoRedirects()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        makeWindow()
        makeMenus()
        connect()
        NSApp.activate(ignoringOtherApps: true)
    }

    private func makeWebConfiguration(lifecycle: Bool) -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.userContentController.add(self, name: "traceTheme")
        configuration.userContentController.add(self, name: "traceFloating")
        if lifecycle { configuration.userContentController.add(self, name: "traceLifecycle") }
        let bridge = """
        (() => {
          function report() {
            let mode = 'system';
            try { mode = JSON.parse(localStorage.getItem('trace.appearance.v1'))?.mode || 'system'; } catch {}
            window.webkit.messageHandlers.traceTheme.postMessage({mode});
          }
          new MutationObserver(report).observe(document.documentElement, {attributes:true,attributeFilter:['data-mode']});
          document.addEventListener('change', e => { if(e.target.dataset.pref === 'mode') report(); });
          const note = document.getElementById('theme-note');
          if (note) note.textContent = '偏好保存在此 Mac App，切换时保留当前任务、图示与回放位置。';
          report();
        })();
        """
        configuration.userContentController.addUserScript(WKUserScript(source: bridge, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        return configuration
    }

    private func makeWindow() {
        let bounds = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 960)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: min(1320, bounds.width - 64), height: min(900, bounds.height - 72)),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Trace · Agent 工作台"
        window.minSize = NSSize(width: 780, height: 600)
        window.tabbingMode = .disallowed
        window.isReleasedWhenClosed = false
        window.titlebarSeparatorStyle = .none
        window.center()
        window.setFrameAutosaveName("TraceWorkspace")
        let floatingButton = NSButton(title: "悬浮窗", target: self, action: #selector(toggleFloating))
        floatingButton.bezelStyle = .rounded
        floatingButton.setFrameSize(NSSize(width: 74, height: 25))
        let accessory = NSTitlebarAccessoryViewController()
        accessory.layoutAttribute = .right
        accessory.view = floatingButton
        window.addTitlebarAccessoryViewController(accessory)

        let configuration = makeWebConfiguration(lifecycle: true)
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.isHidden = true

        let content = NSView()
        content.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: content.topAnchor), webView.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: content.leadingAnchor), webView.trailingAnchor.constraint(equalTo: content.trailingAnchor)
        ])
        loadingView = NSView()
        loadingView.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(loadingView)
        NSLayoutConstraint.activate([
            loadingView.topAnchor.constraint(equalTo: content.topAnchor), loadingView.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            loadingView.leadingAnchor.constraint(equalTo: content.leadingAnchor), loadingView.trailingAnchor.constraint(equalTo: content.trailingAnchor)
        ])
        let title = NSTextField(labelWithString: "Trace")
        title.font = .systemFont(ofSize: 32, weight: .semibold)
        title.alignment = .center
        statusLabel = NSTextField(wrappingLabelWithString: "正在启动本机工作台…")
        statusLabel.alignment = .center
        statusLabel.textColor = .secondaryLabelColor
        progress = NSProgressIndicator()
        progress.style = .spinning
        progress.controlSize = .regular
        retryButton = NSButton(title: "重新连接", target: self, action: #selector(reconnect))
        retryButton.bezelStyle = .rounded
        retryButton.isHidden = true
        let stack = NSStackView(views: [title, statusLabel, progress, retryButton])
        stack.orientation = .vertical
        stack.spacing = 20
        stack.translatesAutoresizingMaskIntoConstraints = false
        loadingView.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: loadingView.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: loadingView.centerYAnchor),
            stack.widthAnchor.constraint(equalToConstant: 440)
        ])
        window.contentView = content
        window.makeKeyAndOrderFront(nil)
    }

    private func connect() {
        guard !connecting else { return }
        connecting = true
        loadingView.isHidden = false
        retryButton.isHidden = true
        statusLabel.stringValue = "正在连接本机服务，任务数据会继续保存在这台 Mac 上。"
        progress.startAnimation(nil)
        let cli = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/bin/agent-trace")
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Result { try LocalService.start(cli: cli) }
            DispatchQueue.main.async {
                self.connecting = false
                switch result {
                case .success(let info):
                    self.serviceURL = info.url
                    self.serviceDataDirectory = info.dataDirectory
                    var components = URLComponents(url: info.url, resolvingAgainstBaseURL: false)!
                    components.fragment = "tasks"
                    self.webView.load(URLRequest(url: components.url!))
                    self.loadFloatingPage()
                case .failure(let error): self.showFailure(error.localizedDescription)
                }
            }
        }
    }

    private func showFailure(_ message: String) {
        loadingView.isHidden = false
        progress.stopAnimation(nil)
        retryButton.isHidden = false
        statusLabel.stringValue = "工作台暂时无法打开。\n" + String(message.prefix(700))
    }

    private func loadFloatingPage() {
        guard let serviceURL, let floatingWebView else { return }
        floatingWebView.load(URLRequest(url: serviceURL.appendingPathComponent("floating.html")))
    }

    @objc private func toggleFloating() {
        if let panel = floatingPanel, panel.isVisible { panel.orderOut(nil); return }
        guard serviceURL != nil else { connect(); return }
        if floatingPanel == nil {
            let panel = FloatingPanel(contentRect: NSRect(x: 0, y: 0, width: 100, height: 156),
                styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
            panel.title = "Trace · 悬浮进度"
            panel.level = .floating
            panel.hidesOnDeactivate = false
            panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
            panel.isReleasedWhenClosed = false
            panel.isOpaque = false
            panel.backgroundColor = .clear
            panel.hasShadow = false
            panel.appearance = window.appearance
            let visible = (window.screen ?? NSScreen.main)?.visibleFrame ?? window.frame
            let topGap = UserDefaults.standard.object(forKey: "TraceFloatingTopGap") as? Double ?? Double(visible.height / 3)
            panel.setFrameOrigin(NSPoint(x: visible.maxX - 100, y: visible.maxY - CGFloat(topGap) - 156))
            let view = WKWebView(frame: .zero, configuration: makeWebConfiguration(lifecycle: false))
            view.navigationDelegate = self
            view.underPageBackgroundColor = .clear
            view.setValue(false, forKey: "drawsBackground")
            view.translatesAutoresizingMaskIntoConstraints = false
            floatingWebView = view
            let content = NSView()
            content.addSubview(view)
            NSLayoutConstraint.activate([
                view.topAnchor.constraint(equalTo: content.topAnchor), view.bottomAnchor.constraint(equalTo: content.bottomAnchor),
                view.leadingAnchor.constraint(equalTo: content.leadingAnchor), view.trailingAnchor.constraint(equalTo: content.trailingAnchor)
            ])
            let handle = FloatingDragHandle(frame: NSRect(x: 17, y: 114, width: 66, height: 22))
            handle.toolTip = "拖动移动，靠近屏幕边缘自动吸附；右键打开菜单"
            handle.afterDrag = { [weak self] in self?.finishFloatingDrag() }
            handle.showMenu = { [weak self] in self?.showFloatingMenu() }
            handle.autoresizingMask = [.minXMargin, .minYMargin]
            content.addSubview(handle)
            floatingDragHandle = handle
            panel.contentView = content
            floatingPanel = panel
            layoutFloating(expanded: false, height: floatingHeight)
            loadFloatingPage()
        }
        floatingPanel?.makeKeyAndOrderFront(nil)
    }

    private func layoutFloating(expanded: Bool, height: Int) {
        guard let panel = floatingPanel else { return }
        floatingExpanded = expanded
        floatingHeight = height
        let visible = (panel.screen ?? NSScreen.main)?.visibleFrame ?? panel.frame
        let frame = FloatingLayout.frame(current: panel.frame, side: floatingSide, expanded: expanded,
            height: CGFloat(height), screen: visible, docked: floatingDocked)
        panel.setFrame(frame, display: true)
        let handleX = floatingSide == .left ? 17 : frame.width - 83
        floatingDragHandle?.frame = NSRect(x: handleX, y: frame.height - 42, width: 66, height: 22)
        updateFloatingPlacement()
    }

    private func updateFloatingPlacement() {
        floatingWebView?.callAsyncJavaScript("document.documentElement.dataset.edge = side; document.documentElement.dataset.docked = docked ? side : ''",
            arguments: ["side": floatingSide.rawValue, "docked": floatingDocked], in: nil, in: .page, completionHandler: nil)
    }

    private func finishFloatingDrag() {
        guard let panel = floatingPanel else { return }
        let visible = (panel.screen ?? NSScreen.main)?.visibleFrame ?? panel.frame
        if let side = FloatingLayout.nearestEdge(panel.frame, side: floatingSide, screen: visible) {
            floatingSide = side
            floatingDocked = true
            UserDefaults.standard.set(side.rawValue, forKey: "TraceFloatingEdge")
        } else { floatingDocked = false }
        layoutFloating(expanded: floatingExpanded, height: floatingHeight)
        UserDefaults.standard.set(Double(visible.maxY - panel.frame.maxY), forKey: "TraceFloatingTopGap")
    }

    @objc private func hideFloating() { floatingPanel?.orderOut(nil) }
    @objc private func openFloatingWorkspace() { openMain() }
    @objc private func dockFloatingLeft() { dockFloating(.left) }
    @objc private func dockFloatingRight() { dockFloating(.right) }
    private func dockFloating(_ side: FloatingSide) {
        floatingSide = side
        floatingDocked = true
        UserDefaults.standard.set(side.rawValue, forKey: "TraceFloatingEdge")
        layoutFloating(expanded: floatingExpanded, height: floatingHeight)
    }

    private func showFloatingMenu() {
        guard let panel = floatingPanel, let view = floatingWebView else { return }
        let menu = NSMenu()
        for (title, action) in [("打开 Trace", #selector(openFloatingWorkspace)), ("隐藏悬浮窗", #selector(hideFloating)),
                                ("吸附到屏幕左侧", #selector(dockFloatingLeft)), ("吸附到屏幕右侧", #selector(dockFloatingRight))] {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
            item.target = self
            menu.addItem(item)
        }
        let point = view.convert(panel.convertPoint(fromScreen: NSEvent.mouseLocation), from: nil)
        menu.popUp(positioning: nil, at: point, in: view)
    }

    private func openMain(taskID: String? = nil) {
        if let taskID {
            webView.callAsyncJavaScript("location.hash = 'task/' + taskID", arguments: ["taskID": taskID],
                in: nil, in: .page, completionHandler: nil)
        }
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
    }

    @objc private func reconnect() { connect() }
    @objc private func reloadPage() { webView.reload() }
    @objc private func showTasks() { runAction("document.querySelector('[data-route=tasks]')?.click()") }
    @objc private func showDiagrams() { runAction("document.querySelector('[data-route=diagrams]')?.click()") }
    @objc private func showAppearance() { runAction("document.querySelector('[data-action=appearance]')?.click()") }
    @objc private func showIntegration() { runAction("document.querySelector('[data-action=integration]')?.click()") }
    @objc private func exportData() { runAction("document.querySelector('[data-action=integration]')?.click(); document.querySelector('[data-action=download]')?.click(); document.getElementById('info-dialog')?.close()") }
    private func runAction(_ script: String) { webView.evaluateJavaScript(script, completionHandler: nil) }
    @objc private func showInBrowser() { if let url = webView.url ?? serviceURL { NSWorkspace.shared.open(url) } }
    @objc private func showDataFolder() {
        NSWorkspace.shared.open(FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/share/agent-trace"))
    }
    @objc private func showAbout() {
        NSApp.orderFrontStandardAboutPanel(options: [
            .applicationName: "Trace", .applicationVersion: "0.3.0", .version: "Mac 本机版",
            .credits: NSAttributedString(string: "Agent 任务、进度与结构图谱。\n关闭窗口或退出 App 后，本机服务继续接收 CLI 汇报。")
        ])
    }

    private func makeMenus() {
        let menu = NSMenu()
        func submenu(_ title: String) -> NSMenu {
            let root = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            let child = NSMenu(title: title)
            root.submenu = child; menu.addItem(root); return child
        }
        func item(_ menu: NSMenu, _ title: String, _ action: Selector?, _ key: String = "", _ target: AnyObject? = nil) {
            let entry = NSMenuItem(title: title, action: action, keyEquivalent: key)
            entry.target = target ?? self; menu.addItem(entry)
        }
        let app = submenu("Trace")
        item(app, "关于 Trace", #selector(showAbout))
        item(app, "外观…", #selector(showAppearance), ",")
        app.addItem(.separator())
        item(app, "隐藏 Trace", #selector(NSApplication.hide(_:)), "h", NSApp)
        app.addItem(.separator())
        item(app, "退出 Trace", #selector(NSApplication.terminate(_:)), "q", NSApp)
        let file = submenu("文件")
        item(file, "导出任务数据…", #selector(exportData))
        item(file, "打开数据文件夹", #selector(showDataFolder))
        file.addItem(.separator())
        item(file, "关闭窗口", #selector(NSWindow.performClose(_:)), "w", window)
        let edit = submenu("编辑")
        for (title, action, key) in [("撤销", "undo:", "z"), ("剪切", "cut:", "x"), ("复制", "copy:", "c"), ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] {
            let entry = NSMenuItem(title: title, action: Selector(action), keyEquivalent: key)
            edit.addItem(entry)
        }
        let view = submenu("显示")
        item(view, "任务总览", #selector(showTasks), "1")
        item(view, "结构图谱", #selector(showDiagrams), "2")
        item(view, "显示／隐藏悬浮窗", #selector(toggleFloating), "3")
        view.addItem(.separator())
        item(view, "重新载入", #selector(reloadPage), "r")
        item(view, "重新连接本机服务", #selector(reconnect))
        item(view, "在浏览器中打开", #selector(showInBrowser))
        let windows = submenu("窗口")
        let minimize = NSMenuItem(title: "最小化", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windows.addItem(minimize)
        windows.addItem(withTitle: "缩放", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        NSApp.windowsMenu = windows
        let help = submenu("帮助")
        item(help, "Agent 接入说明", #selector(showIntegration))
        NSApp.mainMenu = menu
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if webView === floatingWebView { updateFloatingPlacement(); return }
        guard webView === self.webView else { return }
        progress.stopAnimation(nil)
        loadingView.isHidden = true
        webView.isHidden = false
        window.makeFirstResponder(webView)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if webView === self.webView, (error as NSError).code != NSURLErrorCancelled { showFailure(error.localizedDescription) }
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }
    private func isLocal(_ url: URL) -> Bool {
        url.scheme == "http" && url.host == serviceURL?.host && url.port == serviceURL?.port
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if isLocal(url) || url.scheme == "blob" {
            decisionHandler(action.shouldPerformDownload ? .download : .allow)
        } else {
            if action.navigationType == .linkActivated, ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, isLocal(url) { webView.load(action.request) }
        else if let url = action.request.url, ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
        return nil
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = suggestedFilename
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.url : nil) }
    }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        let alert = NSAlert()
        alert.messageText = "无法导出数据"
        alert.informativeText = error.localizedDescription
        alert.beginSheetModal(for: window)
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, let url = message.frameInfo.request.url, isLocal(url) else { return }
        if message.name == "traceFloating" {
            guard let value = message.body as? [String: Any], let action = value["action"] as? String else { return }
            if action == "layout", message.webView === floatingWebView,
               let expanded = value["expanded"] as? Bool, let height = value["height"] as? Int {
                layoutFloating(expanded: expanded, height: height)
            } else if action == "menu", message.webView === floatingWebView { showFloatingMenu() }
            else if action == "open-main" { openMain() }
            else if action == "open-task", let id = value["id"] as? String,
                    id.range(of: "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$", options: .regularExpression) != nil {
                openMain(taskID: id)
            }
            return
        }
        if message.name == "traceLifecycle" {
            guard message.webView === webView else { return }
            guard !lifecycleBusy, let value = message.body as? [String: Any],
                  let id = value["id"] as? String,
                  id.range(of: "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$", options: .regularExpression) != nil,
                  let title = value["title"] as? String, title.count <= 240,
                  let action = value["action"] as? String, ["archive", "restore", "delete"].contains(action),
                  let revision = value["revision"] as? Int, revision > 0,
                  let created = value["createdAt"] as? String, !created.isEmpty, created.count <= 100 else { return }
            lifecycleBusy = true
            if action == "delete" {
                let alert = NSAlert()
                alert.alertStyle = .warning
                alert.messageText = "永久删除任务？"
                alert.informativeText = "“\(title)”及其所有子任务、计划、图示和运行记录将被永久删除，无法恢复。"
                alert.addButton(withTitle: "取消")
                alert.addButton(withTitle: "永久删除").hasDestructiveAction = true
                alert.beginSheetModal(for: window) { result in
                    if result == .alertSecondButtonReturn {
                        self.performLifecycle(id: id, action: action, revision: revision, created: created)
                    } else {
                        self.lifecycleResult(action: action, status: "cancelled", message: "")
                    }
                }
            } else {
                performLifecycle(id: id, action: action, revision: revision, created: created)
            }
            return
        }
        guard message.name == "traceTheme", let value = message.body as? [String: String] else { return }
        switch value["mode"] {
        case "light": window.appearance = NSAppearance(named: .aqua)
        case "dark": window.appearance = NSAppearance(named: .darkAqua)
        default: window.appearance = nil
        }
        floatingPanel?.appearance = window.appearance
    }

    private func performLifecycle(id: String, action: String, revision: Int, created: String) {
        guard let serviceURL, let serviceDataDirectory else { lifecycleResult(action: action, status: "error", message: "本机服务未连接，请重试。"); return }
        let tokenURL = serviceDataDirectory.appendingPathComponent("app.token")
        guard let token = try? String(contentsOf: tokenURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines),
              token.count >= 32, token.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil else {
            lifecycleResult(action: action, status: "error", message: "无法读取本机 App 授权，请重启本机服务。")
            return
        }
        let url = serviceURL.appendingPathComponent("api").appendingPathComponent("app")
            .appendingPathComponent("tasks").appendingPathComponent(id).appendingPathComponent(action)
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 10)
        request.httpMethod = "POST"
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["expected_revision": revision, "expected_created_at": created])
        let config = URLSessionConfiguration.ephemeral
        config.connectionProxyDictionary = ["HTTPEnable": 0, "HTTPSEnable": 0]
        let session = URLSession(configuration: config, delegate: noRedirects, delegateQueue: nil)
        session.dataTask(with: request) { _, response, error in
            defer { session.finishTasksAndInvalidate() }
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            let success = error == nil && code == 200
            let message: String
            if success {
                message = action == "archive" ? "任务已废弃，可在「已废弃」中恢复。" : action == "restore" ? "任务已恢复。" : "任务已永久删除。"
            } else if code == 409 {
                message = "任务已发生变化，请刷新后重试。"
            } else if code == 404 {
                message = "任务不存在或服务版本不匹配，请刷新后重试。"
            } else {
                message = "操作未完成，请检查本机服务后重试。"
            }
            DispatchQueue.main.async { self.lifecycleResult(action: action, status: success ? "ok" : "error", message: message) }
        }.resume()
    }

    private func lifecycleResult(action: String, status: String, message: String) {
        lifecycleBusy = false
        webView.callAsyncJavaScript("document.dispatchEvent(new CustomEvent('trace:lifecycle-result', { detail: result }))",
            arguments: ["result": ["action": action, "status": status, "message": message]],
            in: nil, in: .page, completionHandler: nil)
    }
}

@main
struct TraceMain {
    static func main() {
        let application = NSApplication.shared
        let delegate = TraceApp()
        application.delegate = delegate
        withExtendedLifetime(delegate) { application.run() }
    }
}
