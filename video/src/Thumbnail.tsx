import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { C, FONT } from "./theme";

/** 1280x720 thumbnail. The right panel is a real capture of the sandbox app. */
export const Thumbnail: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bg, fontFamily: FONT, color: C.line }}>
    <div style={{ position: "absolute", left: 70, top: 70, fontSize: 26, fontWeight: 800, letterSpacing: 6, color: C.teal }}>CEKBAO</div>
    <div style={{ position: "absolute", left: 70, top: 130, width: 560, fontSize: 82, fontWeight: 900, lineHeight: 1.02 }}>Would you pay this?</div>
    <div style={{ position: "absolute", left: 70, top: 335, width: 520, fontSize: 30, color: C.coral, fontWeight: 700 }}>New bank account in a tuition e-mail</div>
    <div style={{ position: "absolute", left: 70, top: 420, width: 520, fontSize: 28, lineHeight: 1.3, color: C.dim }}>Check the request. Use the official route.</div>
    <div style={{ position: "absolute", left: 70, top: 600, fontSize: 22, color: C.dim }}>HMIF · ITB · FinTechathon 2026 · Topic C</div>
    <div style={{ position: "absolute", left: 650, top: 110, width: 570, height: 500, borderRadius: 16, overflow: "hidden", border: `2px solid ${C.faint}` }}>
      <Img src={staticFile("captures/A04_verdict.png")} style={{ position: "absolute", left: -408 * 0.52, top: -4, width: 1920 * 0.52, maxWidth: "none" }} />
    </div>
    <div style={{ position: "absolute", left: 650, top: 622, fontSize: 20, fontWeight: 700, letterSpacing: 2, color: C.dim, textTransform: "uppercase" }}>Real sandbox app · synthetic data</div>
  </AbsoluteFill>
);
