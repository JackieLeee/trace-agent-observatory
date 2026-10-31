import AppKit
import WebKit

struct FloatingPreferences: Codable {
    var enabled = true
    var autoHide = true
    var edge = "right"
    var taskMode = "automatic"
    var taskIDs: [String] = []
    static let key = "TraceFloatingPreferencesV1"

    static func load() -> FloatingPreferences {
        if let data = UserDefaults.standard.data(forKey: key),
           let value = try? JSONDecoder().decode(Self.self, from: data), value.isValid { return value }
        var value = Self()
        value.edge = UserDefaults.standard.string(forKey: "TraceFloatingEdge") == "left" ? "left" : "right"
        return value
    }
    var isValid: Bool {
        ["left", "right"].contains(edge) && ["automatic", "manual"].contains(taskMode) && taskIDs.count <= 4 &&
        Set(taskIDs).count == taskIDs.count && taskIDs.allSatisfy {
            $0.range(of: "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$", options: .regularExpression) != nil
        }
    }
    func save() { if let data = try? JSONEncoder().encode(self) { UserDefaults.standard.set(data, forKey: Self.key) } }
    var object: [String: Any] { ["enabled": enabled, "autoHide": autoHide, "edge": edge, "taskMode": taskMode, "taskIDs": taskIDs] }
}

private final class FloatingSurface: NSView {
    var hover: ((Bool, NSEvent) -> Void)?
    var peeking = false { didSet { needsDisplay = true } }
    override var isOpaque: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        trackingAreas.forEach(removeTrackingArea)
        addTrackingArea(NSTrackingArea(rect: .zero, options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect], owner: self))
    }
    override func mouseEntered(with event: NSEvent) { hover?(true, event) }
    override func mouseExited(with event: NSEvent) { hover?(false, event) }
    override func draw(_ dirtyRect: NSRect) {
        NSGraphicsContext.current?.cgContext.clear(bounds)
        guard peeking else { return }
        let dark = effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        (dark ? NSColor(calibratedWhite: 0.12, alpha: 1) : NSColor(calibratedWhite: 0.90, alpha: 1)).setFill()
        NSBezierPath(roundedRect: bounds, xRadius: 6, yRadius: 6).fill()
        (dark ? NSColor(calibratedRed: 0.33, green: 0.73, blue: 0.62, alpha: 1) : NSColor(calibratedRed: 0.18, green: 0.46, blue: 0.37, alpha: 1)).setFill()
        NSBezierPath(roundedRect: NSRect(x: bounds.midX - 1, y: bounds.midY - 12, width: 2, height: 24), xRadius: 1, yRadius: 1).fill()
    }
}

final class FloatingPanel: NSPanel { override var canBecomeKey: Bool { true } }

// Owns only floating-window behavior. Task writes and lifecycle actions remain in the main app.
final class FloatingController: NSObject {
    private(set) var preferences: FloatingPreferences
    private(set) var webView: WKWebView?
    private var panel: NSPanel?
    private var surface: FloatingSurface?
    private var serviceURL: URL?
    private var fullFrame = NSRect.zero
    private var side: FloatingSide
    private var docked = true
    private var expanded = false
    private var height = 140
    private var compactHeight = 140
    private var peeking = false
    private var hideWork: DispatchWorkItem?
    private var monitor: Any?
    private var dragStart: NSPoint?
    private var dragFrame = NSRect.zero
    private var dragging = false
    private var menuOpen = false
    private var pointerInside = false
    var changed: (() -> Void)?
    var openWorkspace: (() -> Void)?
    var openSettings: (() -> Void)?
    var makeConfiguration: (() -> WKWebViewConfiguration)!
    weak var navigationDelegate: WKNavigationDelegate?
    var appearance: NSAppearance? { didSet { panel?.appearance = appearance; surface?.needsDisplay = true } }

    override init() {
        let saved = FloatingPreferences.load()
        preferences = saved; side = FloatingSide(rawValue: saved.edge) ?? .right
        super.init()
    }
    deinit { if let monitor { NSEvent.removeMonitor(monitor) }; hideWork?.cancel() }

    func connect(to url: URL) {
        serviceURL = url
        if let webView { webView.load(URLRequest(url: url.appendingPathComponent("floating.html"))) }
        if preferences.enabled { show() }
    }
    func toggle() { var value = preferences; value.enabled.toggle(); apply(value, activate: true) }
    func apply(_ value: FloatingPreferences, activate: Bool = false) {
        guard value.isValid else { return }
        let edgeChanged = preferences.edge != value.edge
        preferences = value; preferences.save()
        if edgeChanged { side = FloatingSide(rawValue: value.edge) ?? .right; docked = true }
        hideWork?.cancel()
        if !value.enabled { panel?.orderOut(nil) }
        else {
            show(activate: activate)
            if peeking && (!value.autoHide || edgeChanged) { reveal() }
            layout(expanded: expanded, height: height, compactHeight: compactHeight)
            scheduleHide()
        }
        if let webView { publish(to: webView) }
        changed?()
    }
    func publish(to view: WKWebView) {
        view.callAsyncJavaScript("window.TraceNativeFloatingPreferences = preferences; window.dispatchEvent(new CustomEvent('trace:floating-preferences', {detail:preferences}))",
            arguments: ["preferences": preferences.object], in: nil, in: .page, completionHandler: nil)
    }
    func didFinish() { updatePlacement(); if let webView { publish(to: webView) }; scheduleHide() }

    private func show(activate: Bool = false) {
        guard let serviceURL else { return }
        if panel == nil {
            let value = FloatingPanel(contentRect: NSRect(x: 0, y: 0, width: 100, height: 140), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
            value.title = "Trace · 悬浮进度"; value.level = .floating; value.hidesOnDeactivate = false
            value.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
            value.isReleasedWhenClosed = false; value.isOpaque = false; value.backgroundColor = .clear; value.hasShadow = false; value.appearance = appearance
            let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
            let gap = UserDefaults.standard.object(forKey: "TraceFloatingTopGap") as? Double ?? Double(screen.height / 3)
            value.setFrameOrigin(NSPoint(x: screen.maxX - 100, y: screen.maxY - CGFloat(gap) - 140))
            let content = FloatingSurface()
            let view = WKWebView(frame: .zero, configuration: makeConfiguration())
            view.navigationDelegate = navigationDelegate; view.underPageBackgroundColor = .clear; view.setValue(false, forKey: "drawsBackground")
            view.translatesAutoresizingMaskIntoConstraints = false; content.addSubview(view)
            NSLayoutConstraint.activate([view.topAnchor.constraint(equalTo: content.topAnchor), view.bottomAnchor.constraint(equalTo: content.bottomAnchor), view.leadingAnchor.constraint(equalTo: content.leadingAnchor), view.trailingAnchor.constraint(equalTo: content.trailingAnchor)])
            content.hover = { [weak self] inside, event in self?.hover(inside, event: event) }
            value.contentView = content; panel = value; surface = content; webView = view; fullFrame = value.frame
            monitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown, .leftMouseDragged, .leftMouseUp]) { [weak self] event in guard let self else { return event }; return self.handle(event) }
            layout(expanded: false, height: 140, compactHeight: 140)
            view.load(URLRequest(url: serviceURL.appendingPathComponent("floating.html")))
        }
        if activate { panel?.makeKeyAndOrderFront(nil) } else { panel?.orderFrontRegardless() }
        scheduleHide()
    }

    private var visibleScreen: NSRect {
        let frame = peeking ? fullFrame : panel?.frame ?? fullFrame
        let point = NSPoint(x: FloatingLayout.railX(frame, side: side) + 38, y: frame.maxY - 60)
        return (NSScreen.screens.first { $0.visibleFrame.contains(point) } ?? panel?.screen ?? NSScreen.main)?.visibleFrame ?? frame
    }
    func layout(expanded: Bool, height: Int, compactHeight: Int) {
        guard let panel else { return }
        self.expanded = expanded; self.height = height; self.compactHeight = compactHeight
        guard !dragging, dragStart == nil else { return }
        let current = peeking ? fullFrame : panel.frame
        fullFrame = FloatingLayout.frame(current: current, side: side, expanded: expanded, height: CGFloat(height), screen: visibleScreen, docked: docked)
        panel.setFrame(peeking ? FloatingLayout.peekFrame(full: fullFrame, side: side, screen: visibleScreen) : fullFrame, display: true)
        updatePlacement()
    }
    private func updatePlacement() {
        webView?.callAsyncJavaScript("document.documentElement.dataset.edge = side; document.documentElement.dataset.docked = docked ? side : ''", arguments: ["side": side.rawValue, "docked": docked], in: nil, in: .page, completionHandler: nil)
    }
    private func hover(_ inside: Bool, event: NSEvent) {
        // Resizing can emit an exit for the old bounds while the pointer is inside the new rail.
        pointerInside = inside || (panel?.frame.contains(screenPoint(event)) ?? false)
        if pointerInside { hideWork?.cancel(); if peeking { reveal() } }
        else { scheduleHide() }
    }
    private func scheduleHide() {
        hideWork?.cancel()
        guard preferences.enabled, preferences.autoHide, docked, !peeking, !dragging, !menuOpen, !pointerInside, dragStart == nil else { return }
        let work = DispatchWorkItem { [weak self] in
            guard let self, let panel = self.panel, panel.isVisible, self.preferences.enabled, self.preferences.autoHide, self.docked, !self.peeking, !self.pointerInside, !self.dragging, !self.menuOpen else { return }
            self.retract()
        }
        hideWork = work; DispatchQueue.main.asyncAfter(deadline: .now() + 0.55, execute: work)
    }
    private func retract() {
        guard let panel else { return }
        webView?.evaluateJavaScript("window.TraceFloatingInteraction?.collapse()", completionHandler: nil)
        layout(expanded: false, height: compactHeight, compactHeight: compactHeight)
        peeking = true; surface?.peeking = true; webView?.isHidden = true
        panel.setFrame(FloatingLayout.peekFrame(full: fullFrame, side: side, screen: visibleScreen), display: true)
    }
    private func reveal() {
        guard let panel else { return }
        hideWork?.cancel(); peeking = false; surface?.peeking = false; webView?.isHidden = false
        panel.setFrame(fullFrame, display: true)
        // A geometry change may emit mouseExited before the pointer reaches the restored rail.
        scheduleHide()
    }

    private func screenPoint(_ event: NSEvent) -> NSPoint {
        if let point = event.cgEvent?.location { return NSPoint(x: point.x, y: (NSScreen.screens.first?.frame.maxY ?? 0) - point.y) }
        return panel?.convertPoint(toScreen: event.locationInWindow) ?? .zero
    }
    private func handle(_ event: NSEvent) -> NSEvent? {
        guard let panel else { return event }
        guard event.window === panel else {
            if event.type == .leftMouseDown { pointerInside = false; scheduleHide() }
            return event
        }
        switch event.type {
        case .leftMouseDown:
            pointerInside = true
            hideWork?.cancel()
            if peeking { reveal(); return nil }
            dragStart = screenPoint(event); dragFrame = panel.frame; dragging = false
        case .leftMouseDragged:
            guard let dragStart else { return event }
            let point = screenPoint(event), dx = point.x - dragStart.x, dy = point.y - dragStart.y
            if !dragging && hypot(dx, dy) > 4 {
                dragging = true
                webView?.evaluateJavaScript("window.TraceFloatingInteraction?.setDragging(true)", completionHandler: nil)
            }
            if dragging { panel.setFrameOrigin(NSPoint(x: dragFrame.minX + dx, y: dragFrame.minY + dy)) }
        case .leftMouseUp:
            let moved = dragging
            if moved, let dragStart {
                let point = screenPoint(event)
                panel.setFrameOrigin(NSPoint(x: dragFrame.minX + point.x - dragStart.x, y: dragFrame.minY + point.y - dragStart.y))
            }
            dragging = false; dragStart = nil
            if moved {
                finishDrag()
                webView?.evaluateJavaScript("window.TraceFloatingInteraction?.setDragging(false)", completionHandler: nil)
            } else { layout(expanded: expanded, height: height, compactHeight: compactHeight) }
            pointerInside = panel.frame.contains(screenPoint(event)); scheduleHide()
        default: break
        }
        return event
    }
    private func finishDrag() {
        guard let panel else { return }
        let screen = visibleScreen
        if let edge = FloatingLayout.nearestEdge(panel.frame, side: side, screen: screen) {
            side = edge; docked = true; preferences.edge = edge.rawValue; preferences.save()
            if let webView { publish(to: webView) }; changed?()
        } else { docked = false }
        layout(expanded: expanded, height: height, compactHeight: compactHeight)
        UserDefaults.standard.set(Double(screen.maxY - panel.frame.maxY), forKey: "TraceFloatingTopGap")
    }
    @objc private func settingsAction() { openSettings?() }
    @objc private func workspaceAction() { openWorkspace?() }
    @objc private func hideAction() { var value = preferences; value.enabled = false; apply(value) }
    func showMenu() {
        guard let panel, let view = webView else { return }
        hideWork?.cancel(); menuOpen = true
        let menu = NSMenu()
        for (title, action) in [("悬浮窗设置…", #selector(settingsAction)), ("打开 Trace", #selector(workspaceAction)), ("隐藏悬浮窗", #selector(hideAction))] {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: ""); item.target = self; menu.addItem(item)
        }
        menu.popUp(positioning: nil, at: view.convert(panel.convertPoint(fromScreen: NSEvent.mouseLocation), from: nil), in: view)
        menuOpen = false; scheduleHide()
    }
}
