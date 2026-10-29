# CEKBAO demo video pipeline

Records the real CEKBAO app with Playwright, composes the edit in Remotion (React + TypeScript), adds narration and captions, renders an H.264 MP4 and validates it. It also prepares a YouTube package (title, description, chapters, rundown, thumbnails) without uploading anything.

## Commands (run in `tools/demo-video`)

| Command | What it does | Calls the model? |
|---|---|---|
| `npm run demo:doctor` | Checks Node, Remotion, Chrome, Playwright ffmpeg, Python venv, PostgreSQL/Redis, Kokoro TTS, Nebius configuration (values never printed), disk space, app access | No |
| `npm run demo:seed` | Re-creates the synthetic registry (`policyguard/seed.py`), idempotent | No |
| `npm run demo:capture` | Starts the app on port 8790 (or uses `DEMO_BASE_URL`), rehearses all four flows without recording, then records them; writes `artifacts/demo/raw/<build>/` (never overwritten) and the redacted evidence manifest | Only if live inference is configured (at most 3 paid calls, budget-capped by the app) |
| `npm run demo:render` | Narration (Kokoro-82M local TTS or `DEMO_VOICEOVER_DIR`), captions (SRT + Remotion `Caption` JSON), storyboard, a representative 10 s segment render plus a still, then the full render | No (uses the stored capture) |
| `npm run demo:validate` | ffprobe checks, faststart, captions, full AVFoundation decode, audio peak/clipping/loudness, frames at every scene, segment and every 2 s, contact sheet, 720p copies, `validation-report.md` | No |
| `npm run demo:build` | doctor → seed → capture → render → validate | As capture |
| `npm run demo:thumbnail` | Renders the three Remotion `Still` thumbnails at 3840×2160 from real app crops; JPGs under 2 MB; 320×180 and 160×90 previews | No |
| `npm run demo:metadata` | `timeline.json`, title options, description, chapters and the final production rundown from the rendered file | No |
| `npm run demo:package` | thumbnail + metadata + `publishing-checklist.md`; `DEMO_THUMBNAIL=A|B|C` picks the final thumbnail | No |
| `npm run demo:validate-package` | Files, thumbnail sizes, links, chapters vs rendered duration, YouTube limits, unsupported claims | No |
| `npm test` / `npm run typecheck` | Pipeline unit tests (node:test) and TypeScript strict check | No |

Re-rendering never starts the app or calls a model. A new capture is the only step that can.

## Outputs (`artifacts/demo/`)

`cekbao-demo.mp4` when every scenario used live or recorded NVIDIA inference; otherwise `cekbao-demo-preview-MOCK.mp4` (a preview, not a submission video). Next to it: `.srt`, `.captions.json`, `narration.md`, `storyboard.md` (planned), `production-rundown.md` (final), `timeline.json`, `evidence-manifest.json`, `validation-report.md`, `qa/<build>/contact_sheet.jpg`, `raw/<build>/` (raw recordings, markers, zoom crops), YouTube files and `thumbnails/`.

## Truth rules built into the pipeline

- The page is never modified: no DOM injection, no fake results. Click indicators are drawn by the editor from recorded click positions.
- A capture aborts if any selector, assertion or expected decision fails; partial captures are not rendered.
- The rehearsal runs on an app started with `PG_MAX_PAID_CALLS=0` (no paid model calls). The app is then restarted with the settings from `.env.local`, so only the recorded run calls NVIDIA Nemotron: one call per checked scenario, three per capture, inside the budget ledger.
- The edit stays under three minutes (Devpost rule: judges are not required to watch beyond three minutes). The reviewer scene is captured but not in the edit.
- The inference mode shown in the video comes from the app's result page, not from configuration. Mock or rules-only runs are labelled and named as previews.
- The manifest refuses secret-like keys and values (API keys, bearer tokens, session cookies).
- Music is off. Sound effects (whoosh, pop, click) are original and synthesized by `sfx/make_sfx.py`, mixed well under the narration. Narration uses a stock Kokoro voice; no voice cloning. To use your own voice, record one WAV per line id from `narration.md` and set `DEMO_VOICEOVER_DIR`.

## Visual style (revised 2026-10-28 after user review)

The first preview used static title cards and plain frames; the reviewer found it looked generic and preferred the animated explainer style of the earlier `video/` project. The edit now uses:

- An animated problem intro (`scenes/Intro.tsx`): the email with the new account, a real capture of the app's result within the first 15 s, where the money would go, the Singapore Police Force advisory of 19 March 2026 (figures as reported), and what CEKBAO compares.
- Kinetic title cards, an animated colour backdrop, a spring entrance and slow push-in on the recordings, pop-out zooms and a callout chip per step. Callouts for results quote the app's own headline.
- An animated policy timeline after Scenario B (`scenes/PolicyTimeline.tsx`): one invoice, two dates, two policy versions, the app's two results.
- Animated NVIDIA pipeline and results scenes (count-up numbers only from measured values).

All motion is frame-driven (`useCurrentFrame`, `interpolate`, `spring`); there are no CSS transitions.

## Requirements

Node 25+, Google Chrome, `npx playwright install ffmpeg`, the repository `.venv`, local PostgreSQL and Redis (`scripts/policyguard_local.sh start`), Swift (macOS) for frame and decode checks, and optionally the Kokoro venv in `video/.tts/` for narration.

## Skills and references

| Skill | Source and commit | Use |
|---|---|---|
| remotion-markup, remotion-captions, remotion-render, remotion-best-practices | remotion-dev/skills `30d4553` (local copies in `video/.agents/skills/`) | `@remotion/media` Video/Audio, frame-driven `interpolate`, `useVideoConfig` timing, `useCurrentFrame` in small components, `Caption` JSON, `render --frames` and `still` for checks |
| ui-demo | affaan-m/ECC `25278e7` | Discover → rehearse → record; semantic selectors; no silent catches; reading pauses. Not adopted: DOM-injected cursor (the brief forbids page injection), 1280×720 output |
| web-product-demo-video | jh941213/web-demo-skills `b6df15f` | Quality reference: full decode, contact sheet. Not adopted: 60 fps, silent output, its FFmpeg renderer (one pipeline: Remotion); direct cuts and restrained zoom were replaced by animated scenes after user review |
