// TTS adapters. The interface is the substitution point: local Kokoro, a user-recorded voiceover, or none.
import fs from "node:fs";
import path from "node:path";
import type { NarrationLine } from "./narration.ts";
import { REPO, TOOL_DIR, run, wavSeconds } from "./util.ts";

export type Voiced = { id: string; file: string | null; seconds: number };

export interface TtsAdapter {
  readonly name: string;
  readonly hasAudio: boolean;
  synthesize(lines: NarrationLine[], outDir: string): Voiced[];
}

/** Kokoro-82M (Apache-2.0) through kokoro-onnx, offline, stock voice. No voice cloning. */
export class KokoroLocalTts implements TtsAdapter {
  readonly name = "kokoro-82m-local";
  readonly hasAudio = true;
  readonly voice: string;
  readonly speed: number;
  constructor(voice: string, speed: number) { this.voice = voice; this.speed = speed; }

  static available(): boolean {
    return ["video/.tts/venv/bin/python", "video/.tts/kokoro-v1.0.onnx", "video/.tts/voices-v1.0.bin"]
      .every((p) => fs.existsSync(path.join(REPO, p)));
  }

  synthesize(lines: NarrationLine[], outDir: string): Voiced[] {
    fs.mkdirSync(outDir, { recursive: true });
    const job = path.join(outDir, "tts-job.json");
    fs.writeFileSync(job, JSON.stringify({ voice: this.voice, speed: this.speed,
      lines: lines.map((l) => ({ id: l.id, text: l.tts ?? l.text })) }));
    run(path.join(REPO, "video/.tts/venv/bin/python"), [path.join(TOOL_DIR, "tts/kokoro_tts.py"), job, outDir]);
    return lines.map((l) => {
      const file = path.join(outDir, `${l.id}.wav`);
      return { id: l.id, file, seconds: wavSeconds(file) };
    });
  }
}

/** Files recorded by a person: voiceover/<line id>.wav. Missing lines fail loudly. */
export class UserVoiceover implements TtsAdapter {
  readonly name = "user-voiceover";
  readonly hasAudio = true;
  readonly dir: string;
  constructor(dir: string) { this.dir = dir; }
  synthesize(lines: NarrationLine[], outDir: string): Voiced[] {
    fs.mkdirSync(outDir, { recursive: true });
    return lines.map((l) => {
      const src = path.join(this.dir, `${l.id}.wav`);
      if (!fs.existsSync(src)) throw new Error(`voiceover file missing: ${src}`);
      const file = path.join(outDir, `${l.id}.wav`);
      fs.copyFileSync(src, file);
      return { id: l.id, file, seconds: wavSeconds(file) };
    });
  }
}

/** No audio: timing from reading speed (2.6 words per second) so captions stay readable. */
export class NoTts implements TtsAdapter {
  readonly name = "none (captions only)";
  readonly hasAudio = false;
  synthesize(lines: NarrationLine[]): Voiced[] {
    return lines.map((l) => ({ id: l.id, file: null, seconds: Math.max(1.5, l.text.split(/\s+/).length / 2.6) }));
  }
}

export function chooseTts(cfg: { engine?: string; voice?: string; speed?: number } | undefined): TtsAdapter {
  const voiceDir = process.env.DEMO_VOICEOVER_DIR;
  if (voiceDir) return new UserVoiceover(voiceDir);
  if (cfg?.engine === "kokoro-local" && KokoroLocalTts.available()) {
    return new KokoroLocalTts(cfg.voice ?? "af_heart", cfg.speed ?? 0.95);
  }
  return new NoTts();
}
