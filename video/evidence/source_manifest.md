# Source manifest and production notes

## What is real and what is illustrative

| Time | Scene | Footage type | Source |
|---|---|---|---|
| 0:00–0:12 | Hook | ILLUSTRATIVE / SYNTHETIC line drawing | Drawn in Remotion (`src/scenes/Explainer.tsx`). The e-mail values match the synthetic Scenario A fixture |
| 0:12–0:30 | Mechanism | ILLUSTRATIVE / SYNTHETIC line drawing | Same. Northbridge University is a synthetic institution (`.example` domain) |
| 0:30–0:47 | Reported evidence | Text cards with on-screen citations | detikSumut (23 Feb 2025), Kompas.com (24 Feb 2025), Singapore Police Force advisory (19 Mar 2026). Figures as reported. Not combined |
| 0:47–1:03 | Root cause | ILLUSTRATIVE line drawing | Drawn in Remotion |
| 1:03–1:16 | CEKBAO flow | ILLUSTRATIVE line drawing | Drawn in Remotion |
| 1:16–2:00 | Scenario A | REAL APP CAPTURE | `public/captures/A*.png`, `A_full.png`, plus the real HTTP 409 response in `manifest.json` |
| 2:00–2:42 | Scenario B | REAL APP CAPTURE, closing line diagram | `public/captures/B*.png`, `B_full.png` |
| 2:42–3:24 | Scenario C | REAL APP CAPTURE | `public/captures/C*.png`, `C_full.png` |
| 3:24–3:46 | Security | Line diagram + REAL HTTP responses + REAL capture | `manifest.json` `api` entries (401, 404, 403), `D2_injection_hold.png` |
| 3:46–4:04 | Evidence and limits | REAL test output re-run today | `public/evidence/pytest_live.txt`, `scenarios_live.txt` -> `src/generated/evidence.ts` |
| 4:04–4:13 | Close | Title card | Drawn in Remotion |

Real-capture share of runtime: Scenarios A, B, C (128 s) + security responses and capture (about 14 s) + re-run test output (18 s) = about 160 s of 253 s (63%).

### How the real captures were made

- App: the CEKBAO FastAPI sandbox at the pinned commit, started with `CEKBAO_DB_PATH=data/video_demo.sqlite3` (fresh database), on `127.0.0.1:8765`.
- Browser: Playwright 1.64.1 driving the locally installed Google Chrome, headless, clean profile, viewport 1600x900 CSS px at device scale 1.2 (1920x1080 image px), dark color scheme.
- Script: `capture/capture.mjs`. It signs in only with the synthetic personas from `fixtures/demo_users.json` (the access code field is a masked password input), clicks the same buttons a person would click, and saves a screenshot after each step. It records click target boxes, element boxes on full-page screenshots, and real HTTP responses to `public/captures/manifest.json`.
- In the video, motion between screenshots is camera framing (pan, zoom) and crossfades between real states. The cursor is an overlay drawn at the recorded click coordinates. Colored outlines and labels on top of captures are annotations, not part of the app.
- Not used: screen recording of the desktop, CSS reconstructions of the UI, mockups.

## Assets and licenses

| Asset | Origin | License |
|---|---|---|
| App captures (`public/captures/`) | Screenshots of the team's own app with synthetic data | Team HMIF, MIT (repo license) |
| Narration (`public/audio/vo_*.wav`) | Kokoro-82M via kokoro-onnx 0.6.1, voice `af_heart`, generated offline | Kokoro-82M weights: Apache-2.0. kokoro-onnx: MIT. Phonemizer uses espeak-ng (GPL-3.0) as a tool; the generated audio is the team's output |
| Music bed (`public/audio/music_bed.wav`) | Synthesized in `scripts/make_audio.py` from sine waves | Original, no third-party material |
| Sound effects (`sfx_click.wav`, `sfx_hold.wav`) | Synthesized in `scripts/make_audio.py` (seeded noise, sine) | Original, no third-party material |
| Font (`public/fonts/lato-*.woff2`) | Lato from @fontsource/lato 5.2.7 | SIL Open Font License 1.1 (`public/fonts/LICENSE-Lato-OFL.txt`) |
| Remotion 4.0.537 | npm | Remotion License: free for individuals, non-profits and companies with up to 3 employees (see remotion.dev/license). A student team fits; confirm if this changes |
| React, Playwright | npm | MIT, Apache-2.0 |

## Reference videos

The user supplied three KodeKloud MP4s as style references. Their metadata was read (vertical 576x1024 or 720x1280, 110 s, 171 s, 177 s). The files were no longer in `~/Downloads` when frame extraction ran, so no frame-level analysis was done. The video follows the style the user described (black space, thin white line work, small accents, one diagram built step by step). No frames, logos, audio, sound effects, models, characters or motion sequences from those videos were used.

## Claims checked against the repository (commit f33a98d)

| Claim in video | Evidence |
|---|---|
| Seven details do not match (Scenario A) | Verdict text in `A04_verdict.png` / `A_full.png` |
| Plan creation refused with HTTP 409 | `manifest.json` api[0] |
| 1 of 3 slips confirmed, 1 unconfirmed, 1 conflict | `B05_verdict.png`, `B06_slip_*.png` |
| Lowest all-in cost, IDR 8,316,125.00 vs 8,255,000.00 | `C06_quotes_result.png` |
| Plan approved, not executed | `C09_plan_approved.png` |
| 401 no session, 404 cross-student, 403 reviewer approval | `manifest.json` api entries |
| Injection attempt keeps the payment on hold | `D2_injection_hold.png` |
| 117 tests passed, 18/18 sandbox assertions | `public/evidence/pytest_live.txt` (exit 0), `scenarios_live.txt` (exit 0), re-run 2026-10-20 |
| LLM adapter mock-tested only | `tests/test_llm_adapter.py`, no live provider configured |
