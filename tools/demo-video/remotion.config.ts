// Remotion CLI configuration for the demo video. YouTube recommends a closed GOP of half the frame rate and
// two consecutive B-frames for uploads (YouTube Help 1722171); Remotion does not expose these as flags.
import { Config } from "@remotion/cli/config";

// With parallel encoding the video is encoded by the "pre-stitcher" process; the stitcher then copies it.
Config.overrideFfmpegCommand(({ args }) => {
  if (!args.includes("libx264")) return args;
  const output = args[args.length - 1];
  return [...args.slice(0, -1), "-g", "15", "-keyint_min", "15", "-bf", "2", "-flags", "+cgop", "-sc_threshold", "0", output];
});
