# QA report: CEKBAO demo video

Date: 2026-10-20. Repository commit `f33a98d` (app code identical to `715ea9c`). Machine: Apple M2, macOS 26.6.2, Node 25.9.0, Remotion 4.0.537.

## Commands run and results

| Step | Command | Result |
|---|---|---|
| Tests | `.venv/bin/python -m pytest -v` (repo root) | `117 passed in 1.60s`, exit code 0 (`public/evidence/pytest_live.txt`) |
| Scenario assertions | `.venv/bin/python scripts/run_scenarios.py` | `SUMMARY: 18/18 expectations passed`, exit code 0 (`public/evidence/scenarios_live.txt`) |
| App capture | `npm run capture` against a fresh sandbox database | Exit code 0. 36 screenshots, 6 real HTTP responses (409, 409, 403, 404, 403, 401) in `public/captures/manifest.json` |
| Audio and subtitles | `.tts/venv/bin/python scripts/make_audio.py` | 37 narration lines, 446 words, 157 words/min average, narration ends at 4:11.13. 59 subtitle cues |
| Type check | `npx tsc --noEmit` | Exit code 0 |
| Smoke render | 15 s at half scale | H.264 960x540 yuv420p 30 fps + AAC 48 kHz stereo, 15.02 s |
| Full render | `npx remotion render ... --codec=h264 --audio-codec=aac --crf=18 --pixel-format=yuv420p` | 7,590 frames, 20.4 MB, 2 min 15 s (`render_log.txt`) |
| Reproducibility re-render | `npm run render` (final dependency set) | Remotion exit code 0, 137 s. This is the final file (`render_rerun_log.txt`) |
| Thumbnail | `npm run thumbnail` | 1280x720 JPEG |

## Final file

| Property | Value |
|---|---|
| File | `out/CEKBAO_HMIF_FinTechathon_Demo_1080p.mp4` |
| Size | 20,379,986 bytes |
| SHA-256 | `40d85746115e99e470eee0e60d27996c774285d69735d5cc9f1b2f928bb76c64` |
| Duration | 253.013 s (4:13) |
| Video | H.264 High profile, 1920x1080, 16:9, yuv420p, 30/1 fps, 7,590 frames |
| Audio | AAC-LC, 48 kHz, stereo, peak -0.7 dBFS, RMS -20.3 dBFS |

Source: `ffprobe_final.txt`, `sha256_final.txt`.

## Checks

| Check | How | Outcome |
|---|---|---|
| Plays in a real player | Loaded the MP4 in Chrome (`<video>`), played 4 s | Duration 253.013 s, 1920x1080, no media error, 170,114 audio bytes and 102,130 video bytes decoded, 0 dropped frames |
| Frames from every scene | Decoded 39 exact frames from the final MP4 with AVFoundation (`scripts/extract_frames.swift`), tiled into `out/QA_contact_sheet.jpg` | All scenes present. No black or blank frames. No clipped text found. Captions stay below the app window |
| Legibility | Inspected full-size frames at 1:32 (verdict) and 3:58 (test output) | Text sharp. Smallest on-screen text 22 px (terminal output, citations) |
| Audio levels | Extracted track with macOS `afconvert`, measured in 0.25 s windows | Narration median -19.6 dB, music-only median -39.6 dB (bed about 20 dB under speech) |
| Silence | Windows below -50 dBFS for 1 s or more | Only 0:00-0:01 (fade-in) and 4:11.3-4:12.8 (fade-out after the last line). No silent gaps mid-video |
| Subtitles | Parsed `out/CEKBAO_HMIF_subtitles.srt` | 59 cues, no overlaps, at most 2 lines, at most 45 characters per line. Identical to the burned-in source. One cue at 1:40.8 is short (0.64 s, the end of a sentence) |
| Re-render consistency | Compared 7 decoded frames from both renders | 6 frames pixel-identical. 1 frame (1:32, during an annotation draw) differs in 0.001% of pixels. File bytes differ, so the SHA-256 identifies this exact file only |
| Credentials | Sign-in frames | Access code field is a masked password input. No real credentials, secrets or personal data |
| Claims | Each claim traced to captures, HTTP responses or test output | See `source_manifest.md` |

## Known limitations

- The narration is synthetic (Kokoro-82M, offline). A human listen-through is still recommended, for example for the pronunciation of "CEKBAO", "Budi" and "Citra".
- The three KodeKloud reference files left `~/Downloads` before frame extraction. Only their metadata was read. The style follows the user's written description.
- No 3D was used. The brief allowed 3D only where it improves understanding; the line diagrams carried the explanation.
- No 9:16 vertical cut was made.
- Remotion's bundled ffmpeg is a minimal build (no null encoder, no image muxer). Decode and frame checks therefore used AVFoundation and Chrome instead.
