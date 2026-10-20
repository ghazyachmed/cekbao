import React from "react";
import { C, FONT } from "../theme";

/** Provenance label: tells the viewer what kind of footage this is. */
export const Tag: React.FC<{ text: string; color?: string; x?: number; y?: number; opacity?: number }> = ({ text, color = C.dim, x = 120, y = 100, opacity = 1 }) => (
  <div style={{
    position: "absolute", left: x, top: y, fontFamily: FONT, fontSize: 24, fontWeight: 700, letterSpacing: 2.5,
    textTransform: "uppercase", color, border: `1.5px solid ${color}`, borderRadius: 999, padding: "6px 16px", opacity,
  }}>
    {text}
  </div>
);

/** Small source citation (>= 22 px). */
export const Source: React.FC<{ text: string; x?: number; y?: number; w?: number; opacity?: number }> = ({ text, x = 120, y = 820, w = 1680, opacity = 1 }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, fontFamily: FONT, fontSize: 24, color: C.dim, lineHeight: 1.35, opacity }}>
    {text}
  </div>
);
