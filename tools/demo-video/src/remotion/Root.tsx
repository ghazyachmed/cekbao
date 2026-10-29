import { loadFont } from "@remotion/fonts";
import { Composition, Still, staticFile } from "remotion";
import { DemoVideo, type DemoProps } from "./DemoVideo.tsx";
import { Gallery, type GalleryProps } from "./Gallery.tsx";
import { Thumbnail, type ThumbnailProps } from "./Thumbnail.tsx";

// Inter (SIL OFL 1.1), the same files the app serves.
loadFont({ family: "Inter", url: staticFile("fonts/inter-latin-wght-normal.woff2"), weight: "100 900" });
loadFont({ family: "Inter", url: staticFile("fonts/inter-latin-ext-wght-normal.woff2"), weight: "100 900",
           unicodeRange: "U+0100-02BA, U+1E00-1E9F, U+20A0-20C0" });

const thumb = (text: string): ThumbnailProps =>
  ({ lines: text.split(" / ").map((t) => ({ text: t })), accent: "#ff6b7d", phone: null, note: "REAL APP · SYNTHETIC DATA" });

export const Root: React.FC = () => (
  <>
    <Composition
      id="CekbaoDemo"
      component={DemoVideo}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={300}
      defaultProps={{ plan: null } as DemoProps}
      calculateMetadata={async ({ props }) => {
        // Studio: read the plan written by `npm run demo:render`; CLI renders pass it with --props.
        const plan = props.plan ?? await fetch(staticFile("build/plan.json")).then((r) => (r.ok ? r.json() : null));
        return { durationInFrames: plan?.totalFrames ?? 300, props: { plan } };
      }}
    />
    <Still id="ThumbnailA" component={Thumbnail} width={1920} height={1080} defaultProps={thumb("Check / before / you pay")} />
    <Still id="ThumbnailB" component={Thumbnail} width={1920} height={1080} defaultProps={thumb("Who / authorized / this?")} />
    <Still id="ThumbnailC" component={Thumbnail} width={1920} height={1080} defaultProps={thumb("When / policies / change")} />
    <Still id="Gallery" component={Gallery} width={1800} height={1200}
           defaultProps={{ index: 1, total: 1, title: "CEKBAO", caption: "", accent: "#2ee6c5" } as GalleryProps} />
  </>
);
