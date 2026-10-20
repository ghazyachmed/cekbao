"""Generate narration, music bed, UI sounds, the timeline and captions.

Run with the TTS venv (see video/README.md):
    .tts/venv/bin/python scripts/make_audio.py

Inputs:  scripts/voiceover.json, .tts/kokoro-v1.0.onnx, .tts/voices-v1.0.bin
Outputs: public/audio/vo_*.wav, public/audio/music_bed.wav, public/audio/sfx_*.wav,
         src/generated/timeline.ts, out/CEKBAO_HMIF_Captions.srt,
         public/captions.srt, evidence/audio_log.txt

Narration: Kokoro-82M (Apache-2.0) via kokoro-onnx, offline.
Music and sound effects: synthesized here from sine waves and seeded noise
(original, no third-party audio).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
TOTAL_S = float(json.loads((Path(__file__).resolve().parent / "voiceover.json").read_text())["total_seconds"])
SR_MUSIC = 44100
GAP_S = 0.35

spec = json.loads((ROOT / "scripts" / "voiceover.json").read_text())
audio_dir = ROOT / "public" / "audio"
audio_dir.mkdir(parents=True, exist_ok=True)
(ROOT / "src" / "generated").mkdir(parents=True, exist_ok=True)
(ROOT / "out").mkdir(exist_ok=True)
(ROOT / "evidence").mkdir(exist_ok=True)
log: list[str] = []

# ---------------------------------------------------------------- narration
from kokoro_onnx import Kokoro  # noqa: E402

kokoro = Kokoro(str(ROOT / ".tts" / "kokoro-v1.0.onnx"), str(ROOT / ".tts" / "voices-v1.0.bin"))
segments = []
cursor = 0.0
for seg in spec["segments"]:
    samples, sr = kokoro.create(seg.get("tts", seg["text"]), voice=spec["voice"], speed=spec["speed"], lang="en-us")
    samples = np.asarray(samples, dtype=np.float32)
    # Trim leading/trailing silence, add short fades.
    idx = np.where(np.abs(samples) > 0.01)[0]
    if len(idx):
        samples = samples[max(0, idx[0] - int(0.03 * sr)): idx[-1] + int(0.08 * sr)]
    fade = int(0.015 * sr)
    samples[:fade] *= np.linspace(0, 1, fade)
    samples[-fade:] *= np.linspace(1, 0, fade)
    peak = float(np.max(np.abs(samples)))
    samples = samples / peak * 0.89  # about -1 dBFS peak
    dur = len(samples) / sr
    start = max(seg["at"], cursor + GAP_S)
    end = start + dur
    cursor = end
    path = audio_dir / f"vo_{seg['id']}.wav"
    sf.write(path, samples, sr, subtype="PCM_16")
    words = len(seg["text"].split())
    segments.append({"id": seg["id"], "scene": seg.get("scene", ""), "text": seg["text"], "start": round(start, 3), "end": round(end, 3),
                     "file": f"audio/vo_{seg['id']}.wav", "added": bool(seg.get("added"))})
    log.append(f"vo {seg['id']:<7} start {start:7.2f}s  dur {dur:5.2f}s  {words:3d} words  {words / dur * 60:5.0f} wpm")
print("\n".join(log))
if cursor > TOTAL_S - 1.0:
    raise SystemExit(f"narration ends at {cursor:.2f}s, beyond the {TOTAL_S}s cut")

# ---------------------------------------------------------------- captions
def split_caption(text: str, max_chars: int = 84) -> list[str]:
    """Split into chunks of at most two lines (~42 chars each)."""
    sentences = re.split(r"(?<=[.!?:])\s+", text.strip())
    chunks: list[str] = []
    for s in sentences:
        while len(s) > max_chars:
            cut = s.rfind(",", 0, max_chars)
            cut = cut + 1 if cut > 30 else s.rfind(" ", 0, max_chars)
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if chunks and len(chunks[-1]) + 1 + len(s) <= max_chars and not chunks[-1].endswith((".", "?", "!")):
            chunks[-1] += " " + s
        else:
            chunks.append(s)
    return chunks


def two_lines(chunk: str, width: int = 44) -> str:
    if len(chunk) <= width:
        return chunk
    mid = len(chunk) // 2
    left = chunk.rfind(" ", 0, mid + 6)
    right = chunk.find(" ", mid - 6)
    cut = left if left != -1 and (right == -1 or mid - left <= right - mid) else right
    return chunk[:cut].strip() + "\n" + chunk[cut:].strip()


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


cues = []
for seg in segments:
    chunks = split_caption(seg["text"])
    total_chars = sum(len(c) for c in chunks)
    t = seg["start"]
    span = seg["end"] - seg["start"]
    for c in chunks:
        d = span * len(c) / total_chars
        cues.append((t, t + d, two_lines(c)))
        t += d
# Hold each cue 0.25 s longer for reading, but never into the next cue.
fixed = []
for k, (a, b, txt) in enumerate(cues):
    nxt = cues[k + 1][0] if k + 1 < len(cues) else TOTAL_S
    fixed.append((a, min(b + 0.25, nxt - 0.04), txt))
cues = fixed
srt = "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(cues, 1))
(ROOT / "out" / "CEKBAO_HMIF_subtitles.srt").write_text(srt)
(ROOT / "public" / "captions.srt").write_text(srt)
log.append(f"captions: {len(cues)} cues")

# ---------------------------------------------------------------- music bed (original)
def note(freq: float, length: float, sr: int = SR_MUSIC) -> np.ndarray:
    t = np.arange(int(length * sr)) / sr
    tone = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
            + 0.12 * np.sin(2 * np.pi * 3 * freq * t))
    env = np.minimum(1, t / 2.5) * np.minimum(1, (length - t) / 2.5)
    return tone * np.clip(env, 0, 1)


# A minor-ish calm progression, 8 s per chord: Am9, Fmaj7, Cmaj7, G6
chords = [[110.0, 164.81, 196.0, 246.94, 261.63], [87.31, 130.81, 174.61, 220.0, 261.63],
          [130.81, 164.81, 196.0, 246.94, 293.66], [98.0, 146.83, 196.0, 246.94, 329.63]]
seg_len = 8.0
music = np.zeros(int(TOTAL_S * SR_MUSIC) + SR_MUSIC, dtype=np.float32)
pos = 0
i = 0
while pos < len(music) - int(seg_len * SR_MUSIC):
    block = sum(note(f, seg_len + 2.0) for f in chords[i % 4]) / 5
    end = min(len(music), pos + len(block))
    music[pos:end] += block[: end - pos].astype(np.float32)
    pos += int(seg_len * SR_MUSIC)
    i += 1
music = music[: int(TOTAL_S * SR_MUSIC)]
total = len(music)
fade_in, fade_out = int(3 * SR_MUSIC), int(5 * SR_MUSIC)
music[:fade_in] *= np.linspace(0, 1, fade_in)
music[-fade_out:] *= np.linspace(1, 0, fade_out)
music = music / np.max(np.abs(music)) * 0.5
sf.write(audio_dir / "music_bed.wav", music, SR_MUSIC, subtype="PCM_16")
log.append(f"music_bed.wav: original synthesized pad, {TOTAL_S:.0f} s, peak -6 dBFS before the in-video volume")

# ---------------------------------------------------------------- sound effects (original)
rng = np.random.default_rng(7)
click_len = int(0.03 * SR_MUSIC)
click = rng.standard_normal(click_len) * np.exp(-np.linspace(0, 9, click_len))
click = np.convolve(click, np.ones(6) / 6, mode="same")
sf.write(audio_dir / "sfx_click.wav", (click / np.max(np.abs(click)) * 0.5).astype(np.float32), SR_MUSIC, subtype="PCM_16")
t = np.arange(int(0.7 * SR_MUSIC)) / SR_MUSIC
hold = (np.sin(2 * np.pi * 70 * t) + 0.4 * np.sin(2 * np.pi * 140 * t)) * np.exp(-t * 6)
sf.write(audio_dir / "sfx_hold.wav", (hold / np.max(np.abs(hold)) * 0.6).astype(np.float32), SR_MUSIC, subtype="PCM_16")
log.append("sfx_click.wav, sfx_hold.wav: original synthesized")

# ---------------------------------------------------------------- timeline for Remotion
ts_lines = ["// Generated by scripts/make_audio.py. Do not edit by hand.",
            "export type VoSegment = { id: string; scene: string; text: string; start: number; end: number; file: string; added: boolean };",
            f"export const VO: VoSegment[] = {json.dumps(segments, indent=2)};",
            f"export const CAPTIONS_SRT = {json.dumps(srt)};"]
(ROOT / "src" / "generated" / "timeline.ts").write_text("\n".join(ts_lines) + "\n")
words = sum(len(s["text"].split()) for s in segments)
speech = sum(s["end"] - s["start"] for s in segments)
log.append(f"narration: {len(segments)} segments, {words} words, {speech:.1f} s of speech, average {words / speech * 60:.0f} wpm, ends at {cursor:.2f} s")
(ROOT / "evidence" / "audio_log.txt").write_text("\n".join(log) + "\n")
print("\n".join(log[-4:]))
