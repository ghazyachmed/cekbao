// validation: ffprobe checks, faststart check and the validation report helpers.
export type Check = { name: string; ok: boolean; detail: string };
export type ProbeExpect = { width: number; height: number; fps: number; limit: number | null; expectAudio: boolean };

export function checkProbe(probe: any, e: ProbeExpect): Check[] {
  const v = probe.streams.find((s: any) => s.codec_type === "video");
  const a = probe.streams.find((s: any) => s.codec_type === "audio");
  const [num, den] = String(v?.r_frame_rate ?? "0/1").split("/").map(Number);
  const fps = den ? num / den : 0;
  const duration = Number(probe.format?.duration ?? 0);
  return [
    { name: "video_codec", ok: v?.codec_name === "h264", detail: `codec ${v?.codec_name}` },
    { name: "pixel_format", ok: v?.pix_fmt === "yuv420p", detail: `pix_fmt ${v?.pix_fmt}` },
    { name: "resolution", ok: v?.width === e.width && v?.height === e.height, detail: `${v?.width}x${v?.height}` },
    { name: "frame_rate", ok: Math.abs(fps - e.fps) < 0.01, detail: `${v?.r_frame_rate}` },
    { name: "duration", ok: duration > 0 && (e.limit === null || duration <= e.limit),
      detail: `${duration.toFixed(3)} s (limit ${e.limit ?? "none"})` },
    { name: "audio", ok: e.expectAudio ? a?.codec_name === "aac" : true,
      detail: a ? `${a.codec_name} ${a.sample_rate} Hz, ${a.channels} ch` : "no audio stream" },
  ];
}

export function moovBeforeMdat(buf: Buffer): boolean {
  let offset = 0;
  let moov = -1, mdat = -1;
  while (offset + 8 <= buf.length) {
    let size = buf.readUInt32BE(offset);
    const type = buf.toString("latin1", offset + 4, offset + 8);
    if (size === 1 && offset + 16 <= buf.length) size = Number(buf.readBigUInt64BE(offset + 8));
    if (type === "moov" && moov < 0) moov = offset;
    if (type === "mdat" && mdat < 0) mdat = offset;
    if (size < 8) break;
    offset += size;
  }
  return moov >= 0 && (mdat < 0 || moov < mdat);
}

// YouTube recommended upload encoding settings (YouTube Help 1722171, checked 2026-10-28): H.264 High profile,
// progressive, closed GOP of half the frame rate, 8 Mbps for 1080p at 24-30 fps (SDR), BT.709 primaries, transfer
// and matrix, AAC-LC 48 kHz stereo at 384 kbps, MP4 without edit lists. Recommendations, not upload requirements.
export type YoutubeFacts = { height: number; fps: number; keyframeGap: number; editList: boolean };

export function checkYoutubeRecommended(probe: any, x: YoutubeFacts): Check[] {
  const v = probe.streams.find((s: any) => s.codec_type === "video");
  const a = probe.streams.find((s: any) => s.codec_type === "audio");
  const minVideo = x.height >= 2160 ? 35e6 : x.height >= 1440 ? 16e6 : x.height >= 1080 ? (x.fps > 30 ? 12e6 : 8e6) : 5e6;
  const vbr = Number(v?.bit_rate ?? 0), abr = Number(a?.bit_rate ?? 0);
  const bt709 = ["color_primaries", "color_transfer", "color_space"].every((k) => v?.[k] === "bt709");
  return [
    { name: "yt_profile", ok: ["High", "100"].includes(String(v?.profile)) && v?.field_order !== "tt" && v?.field_order !== "bb",
      detail: `profile ${v?.profile}, ${v?.field_order ?? "progressive"}` },
    { name: "yt_video_bitrate", ok: vbr >= minVideo * 0.95,
      detail: `${(vbr / 1e6).toFixed(1)} Mbps (recommended ${minVideo / 1e6} Mbps)` },
    { name: "yt_gop", ok: x.keyframeGap > 0 && x.keyframeGap <= Math.ceil(x.fps / 2),
      detail: `largest keyframe interval ${x.keyframeGap} frames (recommended ${Math.ceil(x.fps / 2)})` },
    { name: "yt_color_bt709", ok: bt709,
      detail: `primaries ${v?.color_primaries}, transfer ${v?.color_transfer}, matrix ${v?.color_space}` },
    { name: "yt_audio_bitrate", ok: a?.codec_name === "aac" && Number(a?.sample_rate) === 48000 && abr >= 384e3 * 0.95,
      detail: `${a?.codec_name} ${a?.sample_rate} Hz, ${(abr / 1e3).toFixed(0)} kbps (recommended 384 kbps)` },
    { name: "yt_edit_list", ok: !x.editList, detail: x.editList ? "MP4 contains an edit list (elst)" : "no edit list" },
  ];
}

/** Largest distance in frames between keyframes, from a list of key_frame flags in display order. */
export function maxKeyframeGap(flags: number[]): number {
  const keys = flags.flatMap((f, i) => (f ? [i] : []));
  if (keys.length < 2) return flags.length;
  return Math.max(...keys.slice(1).map((k, i) => k - keys[i]));
}

/** True when any track in the moov box has an edit list. */
export function hasEditList(buf: Buffer): boolean {
  const walk = (start: number, end: number): boolean => {
    let off = start;
    while (off + 8 <= end) {
      const size = buf.readUInt32BE(off);
      const type = buf.toString("latin1", off + 4, off + 8);
      if (size < 8) return false;
      if (type === "elst") return true;
      if (["moov", "trak", "edts"].includes(type) && walk(off + 8, Math.min(end, off + size))) return true;
      off += size;
    }
    return false;
  };
  return walk(0, buf.length);
}
