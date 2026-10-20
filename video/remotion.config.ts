import { Config } from "@remotion/cli/config";

// H.264 + AAC in an MP4 container, 4:2:0 chroma for broad player support.
Config.setCodec("h264");
Config.setPixelFormat("yuv420p");
Config.setCrf(18);
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(92);
Config.setOverwriteOutput(true);
