# Thumbnail selection

Revised 2026-10-28 after user review: the first set (headline plus a flat app crop) was not eye-catching enough. The new set follows the reference style the user supplied: very large uppercase type with one neon word, a diagonal colour wedge with glow, a tilted phone, and a bold result chip.

All three variants are Remotion `Still` compositions (`tools/demo-video/src/remotion/Thumbnail.tsx`, ids `ThumbnailA/B/C`, props in `thumbnail-*.props.json`). The phone shows a real capture of the running app's result page at 390x844 CSS px, 3x density, with synthetic data (the app's own "Synthetic data" banner is visible). The chip restates the app's own headline for that case; it adds no claim. Masters are 3840×2160; upload JPGs are about 0.65 MB (limit 2 MB).

| Variant | Headline (neon word) | Phone capture | Chip | 320×180 | 160×90 |
|---|---|---|---|---|---|
| A | Check before **you pay** (coral) | Scenario A result: "Conflicts with the checked policy." | ✕ CONFLICTS WITH POLICY | headline and chip readable | headline and chip readable |
| B | Who **authorized** this? (amber) | Scenario C result: "Not enough evidence to verify." | ! NOT ENOUGH EVIDENCE | headline and chip readable | headline readable; chip readable |
| C | When policies **change** (violet) | Scenario B result for 30 November | ✓ 14 AUG MATCHES / ✕ 30 NOV CONFLICTS | headline and both chips readable | headline readable; chips small but legible |

Recommended: **A** (copied to `thumbnail-final.jpg`). It matches the opening story of the video, uses the strongest contrast (coral on navy), and keeps a single message at both preview sizes. C is the strongest alternative because it shows the date idea that makes CEKBAO different. No click-through testing was done, so no performance difference is claimed. To switch: `DEMO_THUMBNAIL=C npm run demo:package`.

The lower-right corner stays free for YouTube's duration label in all three (checked on the 320×180 previews; red box in `previews/comparison.png`).
