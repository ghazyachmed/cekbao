# Demo video validation report

Build: `20261029T001918Z-745bb1f`. Commit: `745bb1f774ff` with 23 uncommitted changes. Generated 2026-10-29T14:31:00.878Z.

## Status

| Stage | Status |
|---|---|
| CODE_IMPLEMENTED | yes |
| CAPTURED | yes |
| RENDERED | yes |
| VALIDATED | yes |
| SUBMISSION_READY | NO |

Output kind: **preview (MOCK)**. not configured at capture time: NEBIUS_API_KEY, PG_INFERENCE_BUDGET_USD, PG_MAX_PAID_CALLS. The file is named as a preview and is not a submission video.

## Official duration rule

Nebius x NVIDIA Global AI Hackathon (Devpost): the video should be less than three (3) minutes; judges are not required to watch beyond three minutes; it must be publicly visible on YouTube and show the project functioning. All submission materials in English. Source: https://nebiusglobalaihackathon.devpost.com/rules (checked 2026-10-29).
Measured duration 164.46 s; editorial target 170 s (deviation -5.5 s); limit 179 s: within limit.

## Technical checks (ffprobe and file inspection)

| Check | Result | Detail |
|---|---|---|
| video_codec | pass | codec h264 |
| pixel_format | pass | pix_fmt yuv420p |
| resolution | pass | 1920x1080 |
| frame_rate | pass | 30/1 |
| duration | pass | 164.459 s (limit 179) |
| audio | pass | aac 48000 Hz, 2 ch |
| faststart | pass | moov atom before mdat |
| yt_profile | pass | profile 100, progressive |
| yt_video_bitrate | pass | 10.1 Mbps (recommended 8 Mbps) |
| yt_gop | pass | largest keyframe interval 15 frames (recommended 15) |
| yt_color_bt709 | pass | primaries bt709, transfer bt709, matrix bt709 |
| yt_audio_bitrate | pass | aac 48000 Hz, 381 kbps (recommended 384 kbps) |
| yt_edit_list | pass | no edit list |
| captions | pass | 37 cues, max 2 lines, no overlap |
| full_decode | pass | completed; 4932 video frames decoded (expected about 4934); 7891904 audio samples |
| audio_levels | pass | peak -1.2 dBFS, clipped samples 0, 29 narration lines between -18.2 and -16.6 dBFS RMS (spread 1.6 dB, limit 6 dB) |
| frames | pass | 126 decoded frames; no blank frames |

Application footage share: 58 % of the edit (editorial target 60 %, not a competition rule). Product first visible at 3.7 s (real app capture). Sound effects: 34 original synthesized cues under the narration.

## Scenarios captured from the running app

| Scenario | Headlines shown by the app | Read by |
|---|---|---|
| A conflict | Conflicts with the checked policy. | rules |
| B policy_change | Conflicts with the checked policy. / Matches the checked policy. | unknown |
| C insufficient | Not enough evidence to verify. | unknown |
| C escalation | Not enough evidence to verify. | reviewer step (no reading) |

## Frame review

Frames decoded from the final MP4 with AVFoundation: 126 (scene starts, ends, every segment, every 2 s). Contact sheet: `artifacts/demo/qa/20261029T001918Z-745bb1f/contact_sheet.jpg`. 720p copies for legibility: `artifacts/demo/qa/20261029T001918Z-745bb1f/720p`.

## Not done by this script

- Continuous real-time playback by a person (this script decodes every frame and samples images every 2 s).
- Listening test by ear (pronunciation of CEKBAO, NVIDIA, Nebius); levels are measured numerically above.
- Review by the hackathon organisers' player or upload target.
