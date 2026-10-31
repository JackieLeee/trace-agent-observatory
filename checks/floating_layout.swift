import CoreGraphics

@main
struct FloatingLayoutCheck {
    static func main() {
        let screen = CGRect(x: -1440, y: 30, width: 1440, height: 900)
        let original = CGRect(x: -100, y: 350, width: 100, height: 356)
        let right = FloatingLayout.frame(current: original, side: .right, expanded: false, height: 356, screen: screen, docked: true)
        assert(FloatingLayout.railX(right, side: .right) + 76 == screen.maxX)
        let card = FloatingLayout.frame(current: right, side: .right, expanded: true, height: 500, screen: screen, docked: true)
        assert(FloatingLayout.railX(card, side: .right) == FloatingLayout.railX(right, side: .right))
        assert(card.maxY == right.maxY)
        let left = FloatingLayout.frame(current: card, side: .left, expanded: true, height: 500, screen: screen, docked: true)
        assert(FloatingLayout.railX(left, side: .left) == screen.minX)
        assert(left.maxX <= screen.maxX)
        assert(FloatingLayout.nearestEdge(left, side: .left, screen: screen) == .left)
        assert(FloatingLayout.nearestEdge(card, side: .right, screen: screen) == .right)
        let nearLeft = CGRect(x: screen.minX + 14, y: 400, width: 100, height: 156)
        assert(FloatingLayout.nearestEdge(nearLeft, side: .right, screen: screen) == .left)
        let free = CGRect(x: -900, y: 400, width: 100, height: 156)
        assert(FloatingLayout.nearestEdge(free, side: .right, screen: screen) == nil)
        let short = CGRect(x: 0, y: 0, width: 800, height: 300)
        let bounded = FloatingLayout.frame(current: original, side: .left, expanded: true, height: 500, screen: short, docked: true)
        assert(bounded.minY >= short.minY && bounded.maxY <= short.maxY)
        for side in [FloatingSide.left, .right] {
            let peek = FloatingLayout.peekFrame(full: card, side: side, screen: screen)
            assert(peek.width == 10 && peek.height == 64)
            assert(peek.minY >= screen.minY && peek.maxY <= screen.maxY)
            assert(side == .left ? peek.minX == screen.minX : peek.maxX == screen.maxX)
        }
        print("PASS: left/right snap, threshold, expansion anchor, negative monitor coordinates and screen bounds")
    }
}
