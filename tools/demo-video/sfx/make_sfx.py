"""Original synthesized sound effects for the demo video (no samples, no third-party audio).

Usage: python make_sfx.py <out_dir>. Writes whoosh.wav, pop.wav and click.wav (48 kHz, mono, 16-bit).
The output is deterministic (fixed seed). Peaks are normalized to -6 dBFS; the mix volume is set in plan.ts.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48_000
rng = np.random.default_rng(20261028)


def env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.linspace(0, 1, n)
    a = np.clip(t / max(attack, 1e-6), 0, 1)
    return a * np.exp(-np.clip(t - attack, 0, None) * decay)


def lowpass(x: np.ndarray, k: int) -> np.ndarray:
    return np.convolve(x, np.ones(k) / k, mode="same")


def whoosh(seconds: float = 0.7) -> np.ndarray:
    n = int(SR * seconds)
    noise = rng.standard_normal(n)
    # Band sweep: blend of a dark and a bright filtered noise that moves up, then fades.
    dark, bright = lowpass(noise, 48), noise - lowpass(noise, 6)
    sweep = np.linspace(0, 1, n) ** 1.5
    x = dark * (1 - sweep) + bright * 0.35 * sweep
    return x * env(n, 0.45, 5.0)


def pop(seconds: float = 0.25) -> np.ndarray:
    n = int(SR * seconds)
    t = np.arange(n) / SR
    freq = 880 * np.exp(-t * 9) + 320                       # quick downward chirp
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * env(n, 0.02, 14.0)


def click(seconds: float = 0.12) -> np.ndarray:
    n = int(SR * seconds)
    x = lowpass(rng.standard_normal(n), 4) * env(n, 0.005, 40.0)
    t = np.arange(n) / SR
    return x + 0.6 * np.sin(2 * np.pi * 2200 * t) * env(n, 0.005, 55.0)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, x in (("whoosh", whoosh()), ("pop", pop()), ("click", click())):
        x = x / np.max(np.abs(x)) * 10 ** (-6 / 20)
        sf.write(out / f"{name}.wav", x.astype(np.float32), SR, subtype="PCM_16")
        print(f"{name}.wav {len(x) / SR:.2f} s")


if __name__ == "__main__":
    main()
