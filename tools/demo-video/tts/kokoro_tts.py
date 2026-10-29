"""Offline narration with Kokoro-82M (Apache-2.0) via kokoro-onnx. Stock voice only; no voice cloning.

Usage: video/.tts/venv/bin/python tools/demo-video/tts/kokoro_tts.py <job.json> <out_dir>
job.json: {"voice": "af_heart", "speed": 0.95, "lines": [{"id": "...", "text": "..."}]}
Writes <out_dir>/<id>.wav (24 kHz mono). Every line is normalized to the same RMS (-20 dBFS); a soft limiter (tanh)
keeps transient clicks below -4 dBFS without lowering the whole line, so loudness stays consistent and AAC does not clip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    job = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(str(REPO / "video/.tts/kokoro-v1.0.onnx"), str(REPO / "video/.tts/voices-v1.0.bin"))
    for line in job["lines"]:
        samples, rate = kokoro.create(line["text"], voice=job["voice"], speed=job["speed"], lang="en-us")
        rms = float(np.sqrt(np.mean(np.square(samples)))) or 1.0
        samples = samples * (10 ** (-20 / 20) / rms)
        ceiling = 10 ** (-4 / 20)
        samples = ceiling * np.tanh(samples / ceiling)   # near-linear for speech, compresses only spikes
        sf.write(out / f"{line['id']}.wav", samples, rate, subtype="PCM_16")
    print(f"wrote {len(job['lines'])} lines to {out}")


if __name__ == "__main__":
    main()
