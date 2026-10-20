"""Tile still frames into one labelled contact sheet.

Usage: .tts/venv/bin/python scripts/contact_sheet.py OUT.jpg COLS FRAME_DIR [fps]
Frames are files named element-<frame>.jpeg (from `remotion render --frames`)
or any images; labels show the timestamp when fps is given.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

out, cols, folder = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
fps = float(sys.argv[4]) if len(sys.argv) > 4 else None
files = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
imgs = [Image.open(p).convert("RGB") for p in files]
w = 480
h = int(imgs[0].height * w / imgs[0].width)
rows = (len(imgs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w + (cols + 1) * 8, rows * (h + 34) + (rows + 1) * 8), (7, 11, 16))
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
except OSError:
    font = ImageFont.load_default()
for i, (p, im) in enumerate(zip(files, imgs)):
    x = 8 + (i % cols) * (w + 8)
    y = 8 + (i // cols) * (h + 42)
    sheet.paste(im.resize((w, h)), (x, y))
    label = p.stem
    m = re.search(r"(\d+)$", p.stem)
    if fps and m:
        s = int(m.group(1)) / fps
        label = f"{int(s // 60)}:{s % 60:05.2f}  (frame {int(m.group(1))})"
    draw.text((x, y + h + 6), label, fill=(234, 242, 245), font=font)
sheet.save(out, quality=88)
print(out, sheet.size, len(imgs), "frames")
