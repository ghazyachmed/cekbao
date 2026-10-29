// Full decode check of an MP4 with AVFoundation: decodes every video frame and every audio sample.
// Prints JSON: frame count, decode errors, audio peak and loudness per 0.5 s window, clipped samples.
// Usage: swift qa/decode_all.swift VIDEO.mp4
import AVFoundation
import Foundation

let url = URL(fileURLWithPath: CommandLine.arguments[1])
let asset = AVURLAsset(url: url)
var result: [String: Any] = [:]
let sem = DispatchSemaphore(value: 0)
Task {
    do {
        let reader = try AVAssetReader(asset: asset)
        let vTrack = try await asset.loadTracks(withMediaType: .video).first!
        let aTracks = try await asset.loadTracks(withMediaType: .audio)
        let vOut = AVAssetReaderTrackOutput(track: vTrack, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
        reader.add(vOut)
        var aOut: AVAssetReaderTrackOutput? = nil
        if let a = aTracks.first {
            let o = AVAssetReaderTrackOutput(track: a, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 32,
                                                                       AVLinearPCMIsFloatKey: true, AVLinearPCMIsNonInterleaved: false,
                                                                       AVNumberOfChannelsKey: 1, AVSampleRateKey: 48000])
            reader.add(o); aOut = o
        }
        reader.startReading()
        var frames = 0
        var windows: [Float] = []
        var acc: Float = 0, accN = 0, peak: Float = 0, clipped = 0, total = 0
        var videoDone = false, audioDone = aOut == nil
        while !(videoDone && audioDone) {
            if !videoDone { if vOut.copyNextSampleBuffer() != nil { frames += 1 } else { videoDone = true } }
            if !audioDone, let o = aOut {
                if let sb = o.copyNextSampleBuffer(), let block = CMSampleBufferGetDataBuffer(sb) {
                    var length = 0; var ptr: UnsafeMutablePointer<Int8>? = nil
                    CMBlockBufferGetDataPointer(block, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &length, dataPointerOut: &ptr)
                    let n = length / 4
                    ptr!.withMemoryRebound(to: Float.self, capacity: n) { f in
                        for i in 0..<n {
                            let v = abs(f[i]); peak = max(peak, v); if v >= 0.999 { clipped += 1 }
                            acc += v * v; accN += 1; total += 1
                            if accN == 24000 { windows.append(sqrt(acc / Float(accN))); acc = 0; accN = 0 }
                        }
                    }
                } else { audioDone = true }
            }
        }
        result["status"] = reader.status == .completed ? "completed" : "failed: \(String(describing: reader.error))"
        result["video_frames_decoded"] = frames
        let db = { (x: Float) -> Double in x > 0 ? Double(20 * log10(x)) : -120 }
        result["audio_samples"] = total
        result["audio_peak_dbfs"] = db(peak)
        result["audio_clipped_samples"] = clipped
        result["audio_rms_windows_dbfs"] = windows.map { (db($0) * 10).rounded() / 10 }
    } catch { result["status"] = "error: \(error)" }
    sem.signal()
}
sem.wait()
let data = try! JSONSerialization.data(withJSONObject: result)
print(String(data: data, encoding: .utf8)!)
