/**
 * Pure helpers: given the capture timeline and a time t (seconds into the capture), where is the
 * camera, the cursor, the highlight, and which screen frame shows. No React here, so the maths can
 * be checked without rendering.
 */
import type { Box, Point, Timeline } from "./types";

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
/** Same curve record.mjs moves the real mouse with. */
export const ease = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

/** The newest frame (screencast or still) at or before t. Frames are sorted by t. */
export function frameAt(frames: Timeline["frames"], t: number) {
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].t <= t) lo = mid;
    else hi = mid - 1;
  }
  return frames[lo];
}

export function cursorAt(tl: Timeline, t: number): Point {
  let pos = tl.cursorStart;
  for (const m of tl.moves) {
    if (t < m.t0) break;
    if (t <= m.t1) {
      const k = ease(clamp((t - m.t0) / Math.max(0.001, m.t1 - m.t0), 0, 1));
      return { x: lerp(m.from.x, m.to.x, k), y: lerp(m.from.y, m.to.y, k) };
    }
    pos = m.to;
  }
  return pos;
}

/** Press feedback: 1 → 0.82 → 1 around each click. */
export function cursorPress(tl: Timeline, t: number) {
  for (const c of tl.clicks) {
    const d = t - c.t;
    if (d > -0.06 && d < 0.18) return 1 - 0.18 * Math.sin(((d + 0.06) / 0.24) * Math.PI);
  }
  return 1;
}

export function ripplesAt(tl: Timeline, t: number) {
  const out: { x: number; y: number; p: number }[] = [];
  for (const c of tl.clicks) {
    const p = (t - c.t) / 0.6;
    if (p >= 0 && p <= 1) out.push({ x: c.x, y: c.y, p });
  }
  return out;
}

/** Did this step's click lead somewhere new (page or query)? Then the view resets after it. */
function clickNav(tl: Timeline, s: Timeline["steps"][number]) {
  const click = tl.clicks.find((c) => c.t >= s.t0 && c.t <= s.t1);
  if (!click) return null;
  const nav = tl.navs.some((n) => n.t >= click.t && n.t <= s.t1 + 0.05);
  return nav ? click.t : null;
}

export function highlightAt(tl: Timeline, t: number): { box: Box; opacity: number } | null {
  for (const s of tl.steps) {
    if (!s.box) continue;
    const start = s.t0 + 0.2;
    const navClick = clickNav(tl, s);
    let end = navClick != null ? navClick + 0.25 : s.t1 - 0.2;
    // The action removed the framed element: fade the ring then, not at the step's end (no empty box).
    if (s.boxEnd != null) end = Math.min(end, s.boxEnd);
    if (t < start || t > end + 0.3) continue;
    const opacity = Math.min(clamp((t - start) / 0.3, 0, 1), clamp((end + 0.3 - t) / 0.3, 0, 1));
    // The action moved the page under the ring: glide it to where the element sits now.
    const a = s.boxAfter;
    if (a && t > a.t) {
      const k = ease(clamp((t - a.t) / 0.25, 0, 1));
      const box = { x: s.box.x + (a.x - s.box.x) * k, y: s.box.y + (a.y - s.box.y) * k, w: s.box.w + (a.w - s.box.w) * k, h: s.box.h + (a.h - s.box.h) * k };
      return { box, opacity };
    }
    return { box: s.box, opacity };
  }
  return null;
}

export type Cam = { s: number; cx: number; cy: number };

export function cameraAt(tl: Timeline, t: number, maxZoom = 1.4): Cam {
  const W = tl.viewport.width;
  const H = tl.viewport.height;
  const home: Cam = { s: 1, cx: W / 2, cy: H / 2 };
  const toward = (box: Box, zoom: number | false | null): Cam => {
    if (zoom === false) return home;
    const s =
      typeof zoom === "number"
        ? zoom
        : clamp(Math.min((W * 0.5) / Math.max(1, box.w), (H * 0.45) / Math.max(1, box.h)), 1, maxZoom);
    const hw = W / (2 * s);
    const hh = H / (2 * s);
    return { s, cx: clamp(box.x + box.w / 2, hw, W - hw), cy: clamp(box.y + box.h / 2, hh, H - hh) };
  };

  const kfs: { t: number; cam: Cam; dur: number }[] = [];
  for (const s of tl.steps) {
    kfs.push({ t: s.t0 + 0.05, cam: s.box ? toward(s.box, s.zoom) : home, dur: 0.75 });
    const navClick = clickNav(tl, s);
    if (navClick != null) kfs.push({ t: navClick + 0.3, cam: home, dur: 0.75 });
  }
  kfs.push({ t: tl.duration - 1.2, cam: home, dur: 0.9 });
  kfs.sort((a, b) => a.t - b.t);

  const blend = (from: Cam, k: (typeof kfs)[number], time: number): Cam => {
    const e = ease(clamp((time - k.t) / k.dur, 0, 1));
    return { s: lerp(from.s, k.cam.s, e), cx: lerp(from.cx, k.cam.cx, e), cy: lerp(from.cy, k.cam.cy, e) };
  };
  let from = home;
  let state = home;
  for (let i = 0; i < kfs.length; i++) {
    if (t < kfs[i].t) break;
    if (i > 0) from = blend(from, kfs[i - 1], kfs[i].t);
    state = blend(from, kfs[i], t);
  }
  return state;
}

export function captionAt(tl: Timeline, t: number) {
  let cur: Timeline["steps"][number] | null = null;
  for (const s of tl.steps) if (t >= s.t0 - 0.05) cur = s;
  return cur;
}
