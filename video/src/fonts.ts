// Lato (SIL Open Font License 1.1), bundled locally from @fontsource/lato.
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const fontsLoaded = Promise.all([
  loadFont({ family: "Lato", url: staticFile("fonts/lato-latin-400-normal.woff2"), weight: "400" }),
  loadFont({ family: "Lato", url: staticFile("fonts/lato-latin-400-italic.woff2"), weight: "400", style: "italic" }),
  loadFont({ family: "Lato", url: staticFile("fonts/lato-latin-700-normal.woff2"), weight: "700" }),
  loadFont({ family: "Lato", url: staticFile("fonts/lato-latin-900-normal.woff2"), weight: "900" }),
]);
