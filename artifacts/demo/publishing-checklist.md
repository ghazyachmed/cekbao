# Publishing checklist

Build `20261029T001918Z-745bb1f`. Prepared 2026-10-29T14:31:14.148Z. Nothing has been uploaded or published.

| Item | Status |
|---|---|
| Video | cekbao-demo-preview-MOCK.mp4: **preview (MOCK)**: the NVIDIA model was not called; not a final submission video |
| Thumbnail | thumbnail-final.jpg = variant A (see thumbnails/ and youtube-package-validation.md) |
| Title, description, chapters | youtube-title.txt, youtube-description.txt, youtube-chapters.txt |
| Code link | https://github.com/ghazyachmed/cekbao.git is public (checked HTTP 200 on 2026-10-28), but the PolicyGuard work in this video is **not yet committed or pushed**: push before publishing |
| Demo or Devpost link | not provided; omitted from the description |
| YouTube URL | not created (no upload performed) |
| Live NVIDIA evidence | missing: set NEBIUS_API_KEY, NEBIUS_MODEL_ID, PG_INFERENCE_BUDGET_USD and PG_MAX_PAID_CALLS in .env.local, run scripts/nebius_live_check.py, then npm run demo:build and npm run demo:package |
| Human review | watch the full video and listen to the narration before upload |
