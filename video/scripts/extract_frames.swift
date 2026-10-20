// Decode exact frames from the rendered MP4 with AVFoundation (macOS).
// Usage: swift scripts/extract_frames.swift VIDEO.mp4 OUT_DIR t1 t2 ...   (seconds)
import AVFoundation
import AppKit

let args = CommandLine.arguments
guard args.count > 3 else { print("usage: VIDEO OUT_DIR t1 [t2 ...]"); exit(2) }
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
let outDir = URL(fileURLWithPath: args[2], isDirectory: true)
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
var failures = 0
for s in args.dropFirst(3) {
    guard let sec = Double(s) else { continue }
    let time = CMTime(seconds: sec, preferredTimescale: 600)
    do {
        let img = try gen.copyCGImage(at: time, actualTime: nil)
        let rep = NSBitmapImageRep(cgImage: img)
        let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.9])!
        let frame = Int((sec * 30).rounded())
        try data.write(to: outDir.appendingPathComponent(String(format: "f%05d.jpg", frame)))
        print(String(format: "%7.2fs  %dx%d", sec, img.width, img.height))
    } catch {
        print("failed at \(sec): \(error)")
        failures += 1
    }
}
exit(failures == 0 ? 0 : 1)
