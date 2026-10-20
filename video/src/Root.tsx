import React from "react";
import { Composition, Still } from "remotion";
import "./fonts";
import { CEKBAODemo } from "./CEKBAODemo";
import { Thumbnail } from "./Thumbnail";
import { TOTAL_SECONDS } from "./theme";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="CEKBAODemo" component={CEKBAODemo} durationInFrames={TOTAL_SECONDS * 30} fps={30} width={1920} height={1080} />
    <Still id="Thumbnail" component={Thumbnail} width={1280} height={720} />
  </>
);
