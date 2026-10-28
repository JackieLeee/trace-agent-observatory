import AppKit

let destination = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = size * scale
        let image = NSImage(size: NSSize(width: pixels, height: pixels))
        image.lockFocus()
        let context = NSGraphicsContext.current!.cgContext
        context.scaleBy(x: CGFloat(pixels) / 1024, y: CGFloat(pixels) / 1024)
        let background = NSBezierPath(roundedRect: NSRect(x: 82, y: 82, width: 860, height: 860), xRadius: 198, yRadius: 198)
        NSGradient(starting: NSColor(calibratedRed: 0.16, green: 0.18, blue: 0.30, alpha: 1),
                   ending: NSColor(calibratedRed: 0.065, green: 0.075, blue: 0.11, alpha: 1))!.draw(in: background, angle: -90)
        NSColor(calibratedRed: 0.70, green: 0.66, blue: 1, alpha: 1).setStroke()
        let mark = NSBezierPath()
        mark.lineWidth = 66; mark.lineCapStyle = .round
        mark.move(to: NSPoint(x: 296, y: 688)); mark.line(to: NSPoint(x: 728, y: 688))
        mark.move(to: NSPoint(x: 512, y: 688)); mark.line(to: NSPoint(x: 512, y: 300))
        mark.move(to: NSPoint(x: 296, y: 508)); mark.line(to: NSPoint(x: 708, y: 508)); mark.stroke()
        NSColor(calibratedRed: 0.49, green: 0.83, blue: 0.73, alpha: 1).setFill()
        NSBezierPath(ovalIn: NSRect(x: 674, y: 277, width: 88, height: 88)).fill()
        image.unlockFocus()
        let bitmap = NSBitmapImageRep(data: image.tiffRepresentation!)!
        let data = bitmap.representation(using: .png, properties: [:])!
        let name = "icon_\(size)x\(size)" + (scale == 2 ? "@2x" : "") + ".png"
        try data.write(to: destination.appendingPathComponent(name))
    }
}
