# CEKBAO demo video (Remotion)

Landscape demo video for CEKBAO, Team HMIF (Institut Teknologi Bandung), 2026 Shenzhen FinTechathon, International Track, Topic C. The product segments are real screenshots of the running CEKBAO sandbox app. The opening uses line-drawn explanatory diagrams, labeled ILLUSTRATIVE / SYNTHETIC.

## Outputs

| File | What |
|---|---|
| `out/CEKBAO_HMIF_FinTechathon_Demo_1080p.mp4` | Main video. H.264, AAC, 1920x1080, 30 fps, yuv420p |
| `out/CEKBAO_HMIF_subtitles.srt` | English subtitles, same timings as the burned-in captions |
| `out/CEKBAO_HMIF_thumbnail.jpg` | 1280x720 thumbnail |
| `out/QA_contact_sheet.jpg` | Frames sampled across every scene |
| `evidence/` | Render logs, QA report, source and license manifest, narration script |

`out/` is git-ignored (large binaries). Upload the MP4 where the organizer asks.

<!-- RESULTS:START -->
## Verified result (2026-10-20)

| Property | Value |
|---|---|
| Duration | 253.013 s (4:13) |
| Video | H.264 High, 1920x1080, 16:9, yuv420p, 30 fps, 7,590 frames |
| Audio | AAC-LC 48 kHz stereo, English narration, peak -0.7 dBFS |
| Size | 20,379,986 bytes |
| SHA-256 | `40d85746115e99e470eee0e60d27996c774285d69735d5cc9f1b2f928bb76c64` |
| Render | `npm run render`, Remotion exit code 0, 137 s on an Apple M2 |
| Playback | Played in Chrome: no media error, audio and video decoded, 0 dropped frames |
| Subtitles | 59 cues, no overlaps, max 2 lines, same text as the burned-in captions |

Full logs and checks: `evidence/qa_report.md`, `evidence/render_log.txt`, `evidence/render_rerun_log.txt`, `evidence/ffprobe_final.txt`. A re-render gives a visually identical video but not identical bytes, so the SHA-256 above identifies this exact file.
<!-- RESULTS:END -->

## Pinned source

- Repository commit: `f33a98d` (`f33a98dd344186b85aa9205e0e22dc7a064e1345`). The app code is identical to `715ea9c`. `f33a98d` only adds docs and screenshots.
- Tests re-run in this checkout on 2026-10-20: `117 passed`, exit code 0. Scenario script: `18/18 expectations passed`, exit code 0. Outputs: `public/evidence/`.

## Reproduce the video

All commands run from this `video/` folder unless noted. Steps 1 to 4 regenerate inputs. Step 5 only renders.

1. Install the pinned packages:

```bash
npm ci
```

2. Start the sandbox app with a fresh database (from the repository root, in a second terminal):

```bash
CEKBAO_DB_PATH=data/video_demo.sqlite3 .venv/bin/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8765
```

3. Capture the real app (uses your installed Google Chrome, no browser download):

```bash
npm run capture
```

4. Re-run the tests and the scenario script, then collect the evidence (first command from the repository root, the second from `video/`):

```bash
.venv/bin/python -m pytest -v > video/public/evidence/pytest_live.txt 2>&1; echo "PYTEST_EXIT_CODE=$?" >> video/public/evidence/pytest_live.txt
```

```bash
node scripts/collect_evidence.mjs
```

5. Narration, music, sound effects and subtitles (needs the TTS venv, see below):

```bash
.tts/venv/bin/python scripts/make_audio.py
```

6. Render:

```bash
npx remotion render src/index.ts CEKBAODemo out/CEKBAO_HMIF_FinTechathon_Demo_1080p.mp4 --codec=h264 --audio-codec=aac --crf=18 --pixel-format=yuv420p
```

```bash
npx remotion still src/index.ts Thumbnail out/CEKBAO_HMIF_thumbnail.jpg --image-format=jpeg
```

Preview and edit in Remotion Studio:

```bash
npx remotion studio src/index.ts
```

### TTS venv (offline narration)

Narration uses Kokoro-82M (Apache-2.0) through kokoro-onnx. One-time setup, about 340 MB of model files:

```bash
python3.11 -m venv .tts/venv && .tts/venv/bin/pip install kokoro-onnx soundfile pillow
```

```bash
curl -L -o .tts/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
```

```bash
curl -L -o .tts/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

To use your own voice instead: record each line of `evidence/voiceover_script.md`, save the files over `public/audio/vo_<id>.wav`, update the start and end times in `src/generated/timeline.ts`, and render again.

## Structure

```
src/index.ts, src/Root.tsx      entry and compositions (CEKBAODemo 1920x1080 30 fps, Thumbnail 1280x720)
src/CEKBAODemo.tsx              scene sequences, narration placement, music, captions
src/scenes/Explainer.tsx        hook, mechanism, reported evidence, root cause, CEKBAO flow (line drawings)
src/scenes/Demos.tsx            Scenarios A, B, C on real captures
src/scenes/Proof.tsx            security responses, re-run tests, limits, close
src/components/                 Drawn (SVG strokes), Capture (real-capture viewer), Captions, Tag
src/generated/                  timeline.ts (narration + SRT), evidence.ts (test output); generated, do not edit
capture/capture.mjs             Playwright capture of the running app
scripts/                        make_audio.py, collect_evidence.mjs, contact_sheet.py, voiceover.json
public/                         captures, audio, fonts, evidence, captions.srt
```

All animation is frame-driven (`useCurrentFrame`, `interpolate`). No CSS animations, timers or randomness. Remotion Agent Skills were installed with `npx remotion skills add` (`.agents/skills/`, `skills-lock.json`).

## Truth rules followed

- Product segments use only real screenshots of the running app at the pinned commit. Annotations are drawn on top and look different from the app UI.
- All institutions, students, accounts, ledgers, bank feeds and FX quotes are synthetic. The video says so on screen.
- MATCHED_SOURCE is shown as a registry comparison, not bank confirmation. A slip is shown as a claim, not settlement. The approved plan is shown as NOT EXECUTED.
- No live LLM call was made. The video says the adapter was mock-tested only.
- Reported figures (UMTS 273 students, Singapore 20+ cases, S$31,000) are shown separately, with sources, and never combined.

See `evidence/source_manifest.md` for the shot-by-shot source list and asset licenses.
