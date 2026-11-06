import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { Props } from "./types";
import { cameraAt, captionAt, clamp, cursorAt, cursorPress, frameAt, highlightAt, ripplesAt } from "./timeline";

/** The app sits 1:1 at its CSS size (1440x900) so the screencast frames are never upscaled at rest. */
const FRAME = { x: 240, y: 22, w: 1440, h: 900 };
const CAPTION_TOP = FRAME.y + FRAME.h + 18;
const FONT = "Inter, 'Segoe UI', system-ui, sans-serif";
/** Flat on purpose: a radial glow here ended in a visible light arc (a Mach band at the gradient's
 *  last stop, plus H.264 banding on phones). It showed as a weird light line. */
const BG = "#0E1626";

const Cursor: React.FC<{ x: number; y: number; size: number; press: number }> = ({ x, y, size, press }) => (
  <svg
    width={size}
    height={size * 1.4}
    viewBox="0 0 20 28"
    style={{
      position: "absolute",
      left: x - size * 0.12,
      top: y - size * 0.06,
      transform: `scale(${press})`,
      transformOrigin: "12% 4%",
      filter: "drop-shadow(0 2px 3px rgba(0,0,0,.45))",
      overflow: "visible",
    }}
  >
    <path
      d="M2 1.5 L2 22.5 L7.2 17.6 L10.6 25.4 L14.2 23.8 L10.9 16.2 L17.8 16.2 Z"
      fill="#fff"
      stroke="#0B1222"
      strokeWidth={1.6}
      strokeLinejoin="round"
    />
  </svg>
);

export const HowTo: React.FC<Props> = ({ timeline: tl, base, titleSec }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const T = frame / fps;
  const t = clamp(T - titleSec, 0, tl.duration);
  const W = tl.viewport.width;
  const H = tl.viewport.height;
  const k = FRAME.w / W;
  const accent = tl.accent || "#1735BB";

  const cam = cameraAt(tl, t);
  const shot = frameAt(tl.frames, t);
  const cur = cursorAt(tl, t);
  const hl = highlightAt(tl, t);
  const step = T >= titleSec ? captionAt(tl, t) : null;
  const total = tl.steps.length;

  const screenIn = interpolate(T, [titleSec - 0.45, titleSec], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const titleOut = interpolate(T, [titleSec - 0.45, titleSec], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const titleIn = interpolate(T, [0, 0.45], [0, 1], { extrapolateRight: "clamp" });
  const endFade = interpolate(frame, [durationInFrames - 14, durationInFrames - 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const capIn = step ? clamp((t - step.t0 + 0.05) / 0.3, 0, 1) : 0;
  const cursorSize = 26 / Math.sqrt(cam.s);

  return (
    <AbsoluteFill style={{ background: BG, fontFamily: FONT }}>
      {/* ---- the app ---- */}
      <div
        style={{
          position: "absolute",
          left: FRAME.x,
          top: FRAME.y,
          width: FRAME.w,
          height: FRAME.h,
          borderRadius: 14,
          overflow: "hidden",
          background: "#fff",
          opacity: screenIn,
          transform: `scale(${0.97 + 0.03 * screenIn})`,
          boxShadow: "0 30px 80px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.07)",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: W,
            height: H,
            transformOrigin: "0 0",
            transform: `scale(${k}) translate(${W / 2 - cam.s * cam.cx}px, ${H / 2 - cam.s * cam.cy}px) scale(${cam.s})`,
          }}
        >
          <Img src={staticFile(`${base}/frames/${shot.file}`)} style={{ width: W, height: H, display: "block" }} />
          {hl ? (
            <div
              style={{
                position: "absolute",
                left: hl.box.x - 6,
                top: hl.box.y - 6,
                width: hl.box.w + 12,
                height: hl.box.h + 12,
                borderRadius: 10,
                border: `3px solid ${accent}`,
                opacity: hl.opacity,
                boxShadow: `0 0 0 4px ${accent}33, 0 0 0 4000px rgba(11,18,34,${0.2 * hl.opacity})`,
              }}
            />
          ) : null}
          {ripplesAt(tl, t).map((r, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                left: r.x - (10 + 30 * r.p),
                top: r.y - (10 + 30 * r.p),
                width: 2 * (10 + 30 * r.p),
                height: 2 * (10 + 30 * r.p),
                borderRadius: "50%",
                background: `${accent}55`,
                border: `2px solid ${accent}`,
                opacity: 0.85 * (1 - r.p),
              }}
            />
          ))}
          <Cursor x={cur.x} y={cur.y} size={cursorSize} press={cursorPress(tl, t)} />
        </div>
      </div>

      {/* ---- the instruction ---- */}
      {step ? (
        <div
          style={{
            position: "absolute",
            left: FRAME.x,
            top: CAPTION_TOP,
            width: FRAME.w,
            height: 1080 - CAPTION_TOP - 14,
            display: "flex",
            alignItems: "center",
            gap: 22,
            opacity: capIn,
            transform: `translateY(${(1 - capIn) * 10}px)`,
          }}
        >
          <div
            style={{
              flex: "none",
              background: accent,
              color: "#fff",
              fontSize: 21,
              fontWeight: 700,
              letterSpacing: "0.08em",
              padding: "10px 16px",
              borderRadius: 10,
              whiteSpace: "nowrap",
            }}
          >
            STEP {step.i + 1} OF {total}
          </div>
          <div style={{ color: "#fff", fontSize: 33, fontWeight: 600, lineHeight: 1.22 }}>{step.text}</div>
        </div>
      ) : null}

      {/* ---- title card ---- */}
      {titleOut > 0 ? (
        <AbsoluteFill
          style={{
            background: BG,
            opacity: titleOut,
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            padding: "0 220px",
          }}
        >
          <div style={{ transform: `translateY(${(1 - titleIn) * 14}px)`, opacity: titleIn }}>
            <div style={{ color: "#93A5FF", fontSize: 24, fontWeight: 700, letterSpacing: "0.14em", marginBottom: 22 }}>
              {/* Skip a subtitle the app name already says ("Acme Records · Records"). */}
              {[tl.app, tl.subtitle && !(tl.app ?? "").toLowerCase().includes(tl.subtitle.toLowerCase()) ? tl.subtitle : null]
                .filter(Boolean)
                .join("  ·  ")
                .toUpperCase()}
            </div>
            <div style={{ color: "#fff", fontSize: 76, fontWeight: 800, lineHeight: 1.1 }}>{tl.title}</div>
            <div style={{ color: "#94A3B8", fontSize: 28, fontWeight: 500, marginTop: 26 }}>{total} steps</div>
          </div>
        </AbsoluteFill>
      ) : null}

      <AbsoluteFill style={{ background: BG, opacity: endFade }} />
    </AbsoluteFill>
  );
};
