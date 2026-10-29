"""Thumbnail exports: JPG under 2 MB from each 3840x2160 master, 320x180 and 160x90 previews, comparison sheet.

Usage: video/.tts/venv/bin/python tools/demo-video/qa/thumbs.py <dir> A B C
Reads <dir>/thumbnail-<v>-master.png; writes thumbnail-<v>.jpg, previews/<v>-320.png, previews/<v>-160.png,
previews/comparison.png. Prints JSON with sizes.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

LIMIT = 2_000_000


def main() -> None:
    folder = Path(sys.argv[1])
    (folder / "previews").mkdir(exist_ok=True)
    report, minis = {}, []
    for v in sys.argv[2:]:
        master = Image.open(folder / f"thumbnail-{v.lower()}-master.png").convert("RGB")
        for q in (92, 88, 84, 80, 75, 70):
            buf = io.BytesIO()
            master.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
            if buf.tell() < LIMIT:
                break
        (folder / f"thumbnail-{v.lower()}.jpg").write_bytes(buf.getvalue())
        p320 = master.resize((320, 180), Image.LANCZOS)
        p160 = master.resize((160, 90), Image.LANCZOS)
        p320.save(folder / "previews" / f"{v.lower()}-320.png")
        p160.save(folder / "previews" / f"{v.lower()}-160.png")
        minis.append((v, p320, p160))
        report[v] = {"master": list(master.size), "jpg_bytes": buf.tell(), "jpg_quality": q}
    sheet = Image.new("RGB", (len(minis) * 340 + 20, 330), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    for i, (v, p320, p160) in enumerate(minis):
        x = 20 + i * 340
        d.text((x, 4), f"Variant {v}: 320x180 and 160x90", fill=(0, 0, 0))
        sheet.paste(p320, (x, 20))
        sheet.paste(p160, (x, 220))
        # YouTube draws the duration in the lower-right corner; show where it would sit.
        d.rectangle((x + 320 - 44, 20 + 180 - 22, x + 320 - 4, 20 + 180 - 6), outline=(255, 0, 0))
    sheet.save(folder / "previews" / "comparison.png")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
