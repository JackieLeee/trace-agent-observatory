import CoreGraphics

enum FloatingSide: String { case left, right }

// Geometry uses the visible task rail as its anchor, so opening a card never moves the rail.
enum FloatingLayout {
    static let padding: CGFloat = 12
    static let railWidth: CGFloat = 76
    static let collapsedWidth: CGFloat = 100
    static let expandedWidth: CGFloat = 426

    static func railX(_ frame: CGRect, side: FloatingSide) -> CGFloat {
        side == .left ? frame.minX + padding : frame.maxX - padding - railWidth
    }

    static func nearestEdge(_ frame: CGRect, side: FloatingSide, screen: CGRect) -> FloatingSide? {
        let x = railX(frame, side: side)
        if abs(x - screen.minX) <= 36 { return .left }
        if abs(x + railWidth - screen.maxX) <= 36 { return .right }
        return nil
    }

    static func frame(current: CGRect, side: FloatingSide, expanded: Bool,
                      height: CGFloat, screen: CGRect, docked: Bool) -> CGRect {
        let width = expanded ? expandedWidth : collapsedWidth
        let h = min(screen.height, min(560, max(130, height)))
        let anchor = railX(current, side: side)
        var x = side == .left ? anchor - padding : anchor + railWidth + padding - width
        if docked {
            x = side == .left ? screen.minX - padding : screen.maxX + padding - width
        } else {
            x = min(screen.maxX - width, max(screen.minX, x))
        }
        let y = min(screen.maxY - h, max(screen.minY, current.maxY - h))
        return CGRect(x: x, y: y, width: width, height: h)
    }
}
