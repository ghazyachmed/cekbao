"""Frame QA for the rendered MP4: contact sheet, blank-frame check, 720p legibility copies.

Usage: video/.tts/venv/bin/python tools/demo-video/qa/frames.py <frames_dir> <points.json> <out_dir>
points.json: [{"t": 12.5, "label": "conflict: result_shown"}, ...]  (frames named f%05d.jpg at 30 fps)
Prints a JSON summary on stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat


def main() -> None:
    frames, points, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    (out / "720p").mkdir(exist_ok=True)
    thumbs, report = [], []
    for p in points:
        f = frames / f"f{int(p['t'] * 30 + 0.5):05d}.jpg"   # same half-up rounding as extract_frames.swift
        if not f.exists():
            report.append({**p, "ok": False, "issue": "frame not decoded"})
            continue
        img = Image.open(f).convert("RGB")
        gray = img.convert("L")
        std = ImageStat.Stat(gray).stddev[0]
        app_area = gray.crop((192, 70, 1728, 934))              # the app frame region
        caption = gray.crop((0, 948, 1920, 1080))
        entry = {**p, "size": f"{img.width}x{img.height}", "stddev": round(std, 1),
                 "app_area_stddev": round(ImageStat.Stat(app_area).stddev[0], 1),
                 "caption_band_has_text": ImageStat.Stat(caption).extrema[0][1] > 200}
        entry["ok"] = std > 8                                     # a flat frame has almost no variance
        if not entry["ok"]:
            entry["issue"] = "blank or near-blank frame"
        report.append(entry)
        img.resize((1280, 720), Image.LANCZOS).save(out / "720p" / f"{f.stem}.jpg", quality=88)
        t = img.resize((480, 270), Image.LANCZOS)
        d = ImageDraw.Draw(t)
        d.rectangle((0, 246, 480, 270), fill=(0, 0, 0))
        d.text((6, 250), f"{p['t']:.1f}s {p['label']}"[:70], fill=(255, 255, 255), font=ImageFont.load_default())
        thumbs.append(t)
    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 480, max(1, rows) * 270), (20, 20, 20))
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * 480, (i // cols) * 270))
    sheet.save(out / "contact_sheet.jpg", quality=88)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
