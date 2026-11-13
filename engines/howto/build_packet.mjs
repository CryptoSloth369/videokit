#!/usr/bin/env node
/**
 * Build a tutorial page ("packet"): a how-to help center as one static folder.
 *
 *   node build_packet.mjs <folder>/packet.json [--out <dir>]
 *
 * The page is an index first: categories (nested as deep as packet.json nests them) with one row
 * per tutorial, and a fuzzy search over titles, categories, keywords, and every step's words.
 * Opening a tutorial shows its written steps with a screenshot each; the video loads only when
 * someone presses Play. So the index loads no media at all, a tutorial loads its step screenshots
 * (lazily), and only Play fetches the MP4. Steps under every video made the screen bloated, and
 * people mostly want the answer, not the whole video.
 *
 * packet.json (beside the app folders):
 *   { "project": "<page title, e.g. your customer's business name>", "tagline": "<optional line under it>",
 *     "brand": "<optional two-letter badge text, default: initials of project>",
 *     "accent": "<optional hex color, default #1735BB>", "note": "<optional banner, e.g. 'Draft: ...'>",
 *     "groups": [
 *       { "name": "<app or area>", "dir": "<app folder>", "groups": [
 *           { "name": "<screen>", "videos": ["<slug>", { "slug": "<slug>", "keywords": "print pdf export" }] }
 *       ] } ] }
 *   A group holds "videos", child "groups", or both. "dir" is inherited by child groups.
 *   "keywords" are extra search words people might type that the steps don't say.
 *
 * Each video must have been rendered by render_modal.py, which writes <dir>/out/<slug>/web/
 * (web MP4, poster, step crops, howto.json). The page copies those files beside index.html, so the
 * folder can be hosted anywhere static files go, or opened straight from disk.
 * Output: <folder>/out/packet/ unless --out says otherwise.
 *
 * Links: #/t/<slug> opens a tutorial, #/t/<slug>/<n> opens it at step n, #/c/<category id> jumps
 * the index to a category. A reply to a customer question can link straight to the answer.
 */
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const args = process.argv.slice(2);
const packetPath = args.find((a) => !a.startsWith("--"));
if (!packetPath) {
  console.error("usage: node build_packet.mjs <folder>/packet.json [--out <dir>]");
  process.exit(1);
}
const root = dirname(resolve(packetPath));
const packet = JSON.parse(readFileSync(packetPath, "utf8"));
const outIdx = args.indexOf("--out");
const out = resolve(outIdx >= 0 ? args[outIdx + 1] : join(root, "out", "packet"));

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const clock = (sec) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;
const initials = (s) => s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

// ---- read the category tree and copy each tutorial's web files ----
const tutorials = [];
let videoBytes = 0;
let shotBytes = 0;
function walk(g, parentDir, path, parentId) {
  const dir = g.dir ?? parentDir;
  const id = (parentId ? `${parentId}--` : "") + slugify(g.name);
  const names = [...path, g.name];
  const node = { name: g.name, id, tutorials: [], children: [] };
  for (const v of g.videos ?? []) {
    const { slug, keywords = "" } = typeof v === "string" ? { slug: v } : v;
    if (!dir) {
      console.error(`group "${g.name}" lists videos but has no "dir" (set it here or on a parent group)`);
      process.exit(1);
    }
    if (tutorials.some((t) => t.slug === slug)) {
      console.error(`"${slug}" is listed twice in packet.json`);
      process.exit(1);
    }
    const web = join(root, dir, "out", slug, "web");
    const metaFile = join(web, "howto.json");
    if (!existsSync(metaFile)) {
      console.error(`missing ${metaFile}: render ${slug} with render_modal.py first`);
      process.exit(2);
    }
    const meta = JSON.parse(readFileSync(metaFile, "utf8"));
    cpSync(web, join(out, "v", slug), { recursive: true });
    videoBytes += meta.bytes ?? 0;
    for (const s of meta.steps) shotBytes += statSync(join(web, s.image)).size;
    const t = {
      slug,
      title: meta.title,
      seconds: Math.round((meta.seconds - 0.05) * 100) / 100,
      video: meta.video,
      steps: meta.steps.map(({ n, text, image }) => ({ n, text, image })),
      keywords,
      path: names,
      cat: id,
      base: `v/${slug}`,
    };
    tutorials.push(t);
    node.tutorials.push(t);
  }
  for (const c of g.groups ?? []) node.children.push(walk(c, dir, names, id));
  node.count = node.tutorials.length + node.children.reduce((a, c) => a + c.count, 0);
  return node;
}
const tree = packet.groups.map((g) => walk(g, undefined, [], ""));
const total = tutorials.length;

// ---- static markup: the rail (categories only) and the index (categories with tutorial rows) ----
const railHtml = (nodes) =>
  `<ul>${nodes
    .map(
      (n) => `<li><a href="#/c/${esc(n.id)}" data-cat="${esc(n.id)}"><span>${esc(n.name)}</span><em>${n.count}</em></a>${
        n.children.length ? railHtml(n.children) : ""
      }</li>`,
    )
    .join("")}</ul>`;

const rowHtml = (t) => `
          <li><a class="hv-row" href="#/t/${esc(t.slug)}"><span class="hv-row-t">${esc(t.title)}</span><span class="hv-row-m">${t.steps.length} steps · ${clock(t.seconds)} video</span><span class="hv-row-go" aria-hidden="true">&rsaquo;</span></a></li>`;
const rowsHtml = (ts) => (ts.length ? `<ul class="hv-rows">${ts.map(rowHtml).join("")}</ul>` : "");
// Depth 0 = a heading over cards, depth 1 = a card, deeper = a titled block inside the card.
const subHtml = (n) => `
        <div class="hv-sub" id="c-${esc(n.id)}"><h4>${esc(n.name)}</h4>${rowsHtml(n.tutorials)}${n.children.map(subHtml).join("")}</div>`;
const cardHtml = (n) => `
      <div class="hv-card" id="c-${esc(n.id)}">
        <h3>${esc(n.name)}</h3>${rowsHtml(n.tutorials)}${n.children.map(subHtml).join("")}
      </div>`;
const indexHtml = tree
  .map(
    (n) => `
    <section class="hv-cat" id="c-${esc(n.id)}">
      <h2 class="hv-cat-h">${esc(n.name)}<span>${n.count} ${n.count === 1 ? "how-to" : "how-tos"}</span></h2>${
        n.tutorials.length ? `<div class="hv-card">${rowsHtml(n.tutorials)}</div>` : ""
      }${n.children.map(cardHtml).join("")}
    </section>`,
  )
  .join("");

// Everything the browser needs to search and to draw a tutorial.
const data = JSON.stringify({ tutorials }).replace(/</g, "\\u003c");

const accent = /^#[0-9a-fA-F]{3,8}$/.test(packet.accent ?? "") ? packet.accent : "#1735BB";
const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(packet.project)} How-to</title>
<style>
/* Light theme. Layout: dark header + sticky tab bar, then a category rail + section cards. */
:root {
  --ink: #1a1a1a; --muted: #6b6b6b; --stone: #f9f9f9; --cream: #f7f3ec; --line: #e6e1d8;
  --redA: #f43f5e; --redB: #fb923c; --red-deep: #c0314a; --header: #16121a;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color-scheme: light;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: var(--font); color: var(--ink); background: var(--stone); line-height: 1.55; font-size: 16px; -webkit-font-smoothing: antialiased; }
a { color: var(--red-deep); text-underline-offset: 2px; }
button { font-family: inherit; }
:focus-visible { outline: 2px solid var(--red-deep); outline-offset: 2px; }
[hidden] { display: none !important; }

.pt-staffbar { height: 36px; display: flex; align-items: center; gap: 10px; padding: 0 16px; background: #1e293b; color: #e2e8f0; font-size: 12.5px; }
.pt-staffbar-dot { width: 8px; height: 8px; border-radius: 50%; background: #fbbf24; flex-shrink: 0; }
.pt-staffbar span:last-child { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.wt-header { background: var(--header); color: #fff; border-bottom: 4px solid var(--redA); border-image: linear-gradient(90deg, var(--redA), var(--redB)) 1; }
.wt-header-inner { max-width: 1240px; margin: 0 auto; padding: 22px 36px; display: flex; align-items: center; gap: 14px; }
.rw-badge { width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0; background: linear-gradient(135deg, var(--redA), var(--redB)); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px; color: #fff; }
.wt-header h1 { margin: 0; font-size: 23px; letter-spacing: 0.01em; text-wrap: balance; }
.wt-header .sub { color: rgba(255,255,255,0.82); font-size: 13.5px; margin-top: 2px; }
.wt-header .sub strong { color: var(--redB); font-weight: 600; }
.pt-whoami { margin-left: auto; display: flex; align-items: center; gap: 9px; flex-shrink: 0; }
.pt-avatar { width: 26px; height: 26px; font-size: 10px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; color: #fff; font-weight: 700; background: #5b6b8c; }
.pt-signout { border: 0; background: rgba(255,255,255,0.12); font-size: 12.5px; color: rgba(255,255,255,0.82); padding: 5px 11px; border-radius: 999px; }

.pt-tabbar { background: #fff; border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }
.pt-tabbar-inner { max-width: 1240px; margin: 0 auto; display: flex; gap: 2px; padding: 0 36px; overflow-x: auto; }
.pt-tab { border: 0; background: none; font-size: 14px; font-weight: 700; color: var(--muted); padding: 14px 16px; border-bottom: 3px solid transparent; white-space: nowrap; cursor: default; }
.pt-tab.on { color: var(--red-deep); border-bottom-color: var(--redA); }
.pt-new { margin-left: 7px; font-size: 9.5px; font-weight: 800; letter-spacing: 0.06em; padding: 2px 6px; border-radius: 4px; color: #fff; background: linear-gradient(135deg, var(--redA), var(--redB)); vertical-align: 2px; }
.pt-reviewbar { background: var(--cream); box-shadow: inset 0 1px 0 var(--line); }
.pt-reviewbar-inner { max-width: 1240px; margin: 0 auto; height: 40px; display: flex; align-items: center; gap: 10px; padding: 0 36px; }
.pt-reviewbar-star { color: #f59e0b; font-size: 18px; line-height: 1; }
.pt-reviewbar-text { flex: 1; font-size: 14px; font-weight: 600; }
.pt-reviewbar-btn { border: 0; font-size: 13px; font-weight: 700; color: #fff; background: linear-gradient(135deg, var(--redA), var(--redB)); padding: 0 14px; height: 30px; border-radius: 999px; }

.wt-layout { display: grid; grid-template-columns: 250px minmax(0,1fr); max-width: 1240px; margin: 0 auto; }
.wt-toc { position: sticky; top: 90px; align-self: start; max-height: calc(100vh - 90px); overflow-y: auto; background: var(--cream); border-right: 1px solid var(--line); padding: 22px 16px; font-size: 13.5px; min-height: calc(100vh - 90px); }
.wt-toc h2 { margin: 0 0 10px; font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--red-deep); font-weight: 700; }
.wt-content { padding: 30px 44px 90px; min-width: 0; }

/* ---- How-to tab (new) ---- */
.hv-tree ul { list-style: none; margin: 0; padding: 0; }
.hv-tree ul ul { margin: 2px 0 6px 12px; padding-left: 8px; border-left: 1px solid var(--line); }
.hv-tree a { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 6px 8px; border-radius: 5px; color: var(--ink); text-decoration: none; line-height: 1.3; }
.hv-tree > ul > li > a, .hv-tree > a { font-weight: 700; }
.hv-tree a em { font-style: normal; font-family: var(--mono); font-size: 11px; color: var(--muted); }
.hv-tree a:hover { background: #fff; color: var(--red-deep); }
.hv-tree a.on { background: #fff; color: var(--red-deep); box-shadow: inset 2px 0 0 var(--redA); }
.hv-tree > a { margin-bottom: 6px; }

.hv-search { display: block; width: 100%; max-width: 560px; margin: 0 0 26px; background: #fff; border: 1px solid var(--line); color: var(--ink); border-radius: 8px; padding: 12px 14px 12px 40px; font-size: 15px; font-family: inherit;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%236b6b6b' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='7' cy='7' r='5'/%3E%3Cpath d='m11 11 3.5 3.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: 14px 50%; }
.hv-search:focus { outline: none; border-color: var(--redA); box-shadow: 0 0 0 3px rgba(244,63,94,0.12); }

.hv-cat { margin-bottom: 30px; scroll-margin-top: 102px; }
.hv-cat-h { display: flex; align-items: baseline; gap: 10px; margin: 0 0 12px; font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--red-deep); }
.hv-cat-h span { letter-spacing: 0; text-transform: none; font-size: 12.5px; font-weight: 500; color: var(--muted); }
.hv-card { background: #fff; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 14px; overflow: hidden; scroll-margin-top: 102px; }
.hv-card > h3 { margin: 0; padding: 14px 20px 10px; font-size: 16px; color: var(--header); border-bottom: 1px solid var(--line); }
.hv-sub { scroll-margin-top: 102px; }
.hv-sub > h4 { margin: 0; padding: 12px 20px 8px; font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); border-top: 1px solid var(--line); }
.hv-rows { list-style: none; margin: 0; padding: 0; }
.hv-rows li + li { border-top: 1px solid var(--line); }
.hv-row { display: grid; grid-template-columns: minmax(0,1fr) auto 12px; gap: 3px 16px; align-items: center; padding: 14px 20px; color: var(--ink); text-decoration: none; }
.hv-row:hover { background: #fff8ee; }
.hv-row-t { font-weight: 600; font-size: 15px; line-height: 1.35; }
.hv-row-m { font-size: 12.5px; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.hv-row-go { color: var(--muted); font-size: 20px; line-height: 1; }
.hv-row-p, .hv-row-s { grid-column: 1; font-size: 13px; color: var(--muted); line-height: 1.45; }
.hv-row-s b { color: var(--ink); font-weight: 600; }
.hv-res-h { margin: 0 0 12px; font-size: 13.5px; color: var(--muted); }
mark { background: #ffe3b8; color: inherit; border-radius: 2px; padding: 0 1px; }

.hv-back { font-size: 13.5px; font-weight: 600; text-decoration: none; }
.hv-back:hover { text-decoration: underline; }
.hv-crumb { margin: 18px 0 6px; font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--red-deep); font-weight: 700; }
.hv-title { margin: 0 0 6px; font-size: 26px; line-height: 1.2; color: var(--header); text-wrap: balance; }
.hv-meta { margin: 0 0 22px; font-size: 13.5px; color: var(--muted); }
.hv-linkbtn { border: 0; background: none; padding: 0; font: inherit; font-weight: 600; color: var(--red-deep); text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }
.hv-steplist { list-style: none; margin: 0; padding: 0; background: #fff; border: 1px solid var(--line); border-radius: 8px; }
.hv-s { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 7fr); gap: 24px; padding: 22px 24px; scroll-margin-top: 102px; }
.hv-s + .hv-s { border-top: 1px solid var(--line); }
.hv-s.on { background: #fff8ee; box-shadow: inset 3px 0 0 var(--redA); }
.hv-s-text { display: flex; gap: 12px; align-items: flex-start; }
.hv-s-n { flex: none; width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 800; color: #fff; background: linear-gradient(135deg, var(--redA), var(--redB)); }
.hv-s-text p { margin: 2px 0 0; font-size: 16px; line-height: 1.5; }
.hv-shot { display: block; width: 100%; padding: 0; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; background: var(--cream); cursor: zoom-in; }
.hv-shot img { display: block; width: 100%; height: auto; aspect-ratio: 8 / 5; }
.hv-watch { margin-top: 18px; padding: 18px 24px; background: #fff; border: 1px solid var(--line); border-radius: 8px; scroll-margin-top: 102px; }
.hv-play { display: inline-flex; align-items: center; gap: 10px; height: 40px; padding: 0 18px 0 14px; border: 0; border-radius: 999px; font-size: 14px; font-weight: 700; color: #fff; background: var(--header); cursor: pointer; }
.hv-play svg { flex: none; }
.hv-player { border-radius: 8px; overflow: hidden; background: var(--header); aspect-ratio: 16 / 9; }
.hv-player video { display: block; width: 100%; height: 100%; background: var(--header); }
.hv-zoom { padding: 0; border: 0; border-radius: 8px; max-width: min(1200px, 96vw); background: transparent; cursor: zoom-out; }
.hv-zoom::backdrop { background: rgba(10, 8, 12, 0.82); }
.hv-zoom img { display: block; width: 100%; height: auto; border-radius: 8px; }

@media (max-width: 880px) {
  .wt-layout { grid-template-columns: 1fr; }
  .wt-toc { display: none; }
}
@media (max-width: 700px) {
  .wt-header-inner, .pt-tabbar-inner, .pt-reviewbar-inner { padding-left: 18px; padding-right: 18px; }
  .wt-content { padding: 20px 14px 60px; }
  .hv-row { grid-template-columns: minmax(0,1fr) 12px; padding: 13px 16px; }
  .hv-row-m { grid-column: 1; grid-row: 2; }
  .hv-row-go { grid-row: 1 / span 2; grid-column: 2; }
  .hv-card > h3, .hv-sub > h4 { padding-left: 16px; padding-right: 16px; }
  .hv-title { font-size: 22px; }
  .hv-s { grid-template-columns: 1fr; gap: 12px; padding: 18px 16px; }
  .hv-watch { padding: 16px; }
  .pt-whoami .pt-signout { display: none; }
}
</style>
<style>:root { --redA: ${accent}; --redB: ${accent}; --red-deep: ${accent}; }</style>
</head>
<body>
${packet.note ? `<div class="pt-staffbar"><span class="pt-staffbar-dot" aria-hidden="true"></span><span>${esc(packet.note)}</span></div>` : ""}
<header class="wt-header">
  <div class="wt-header-inner">
    <div class="rw-badge">${esc(packet.brand ?? initials(packet.project))}</div>
    <div style="min-width:0">
      <h1>${esc(packet.project)}</h1>${packet.tagline ? `
      <div class="sub">${esc(packet.tagline)}</div>` : ""}
    </div>
  </div>
</header>
<div class="pt-tabbar">
  <div class="pt-tabbar-inner">
    <button class="pt-tab on" type="button">How-to</button>
  </div>
</div>
<div class="wt-layout">
  <nav class="wt-toc hv-tree" aria-label="How-to categories">
    <h2>How-to</h2>
    <a href="#/" data-cat=""><span>All how-tos</span><em>${total}</em></a>
    ${railHtml(tree)}
  </nav>
  <main class="wt-content" id="hv-main">
    <input id="hv-q" class="hv-search" type="search" placeholder="Search how-tos" aria-label="Search how-tos" autocomplete="off" spellcheck="false">
    <div id="hv-index">${indexHtml}
    </div>
    <div id="hv-results" hidden></div>
    <article id="hv-detail" hidden></article>
  </main>
</div>
<dialog class="hv-zoom" id="hv-zoom"><img alt=""></dialog>
<script type="application/json" id="hv-data">${data}</script>
<script>
(() => {
  const { tutorials } = JSON.parse(document.getElementById("hv-data").textContent);
  const bySlug = new Map(tutorials.map((t) => [t.slug, t]));
  const $ = (id) => document.getElementById(id);
  const q = $("hv-q"), index = $("hv-index"), results = $("hv-results"), detail = $("hv-detail"), zoom = $("hv-zoom");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const clock = (s) => Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0");

  // ---------------- fuzzy search ----------------
  // Every query word must match a word somewhere in the tutorial: exactly, as the start of a word
  // (typing in progress), or within a typo or two. Light stemming makes "reports" find "report".
  // If no tutorial matches every word, the closest ones (most words matched) are shown instead.
  const STOP = new Set("a an the to of for in on at by is are it its i my me we our do does did how can where what which when this that these and or with from get".split(" "));
  const norm = (s) => String(s).toLowerCase().normalize("NFKD").replace(/[\\u0300-\\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  const stem = (w) => {
    if (w.length <= 4 || /\\d/.test(w)) return w;
    if (w.endsWith("ies")) return w.slice(0, -3) + "y";
    for (const suf of ["ing", "ed", "es", "s", "e"]) if (w.endsWith(suf) && w.length - suf.length >= 3) return w.slice(0, -suf.length);
    return w;
  };
  // Each word keeps its raw form too: stemming a typo ("wating" -> "wat") can leave it too short
  // for typo matching, while the raw forms ("wating" vs "waiting") are one letter apart.
  const words = (s) => norm(s).split(" ").filter(Boolean).map((w) => ({ raw: w, stem: stem(w) }));
  // Optimal string alignment distance (typos incl. swapped letters), giving up past max.
  const osa = (a, b, max) => {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    const d = [];
    for (let i = 0; i <= a.length; i++) d[i] = [i];
    for (let j = 0; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      let rowMin = Infinity;
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
        rowMin = Math.min(rowMin, d[i][j]);
      }
      if (rowMin > max) return max + 1;
    }
    return d[a.length][b.length];
  };
  const quality1 = (t, w) => {
    if (t === w) return 1;
    if (t.length >= 2 && w.startsWith(t)) return 0.85;
    if (t.length >= 4) {
      const max = t.length >= 7 ? 2 : 1;
      if (osa(t, w, max) <= max) return 0.7;
      if (w.length > t.length && osa(t, w.slice(0, t.length), 1) <= 1) return 0.6;
    }
    return 0;
  };
  const quality = (t, w) => Math.max(quality1(t.stem, w.stem), quality1(t.raw, w.raw));
  const docs = tutorials.map((t) => ({
    t,
    fields: [
      { w: 3, words: words(t.title) },
      { w: 2, words: words(t.path.join(" ") + " " + t.keywords) },
      ...t.steps.map((s) => ({ w: 1, step: s.n, words: words(s.text) })),
    ],
  }));
  function search(query) {
    const raw = norm(query).split(" ").filter(Boolean);
    let kept = raw.filter((w) => !STOP.has(w));
    if (!kept.length) kept = raw;
    const toks = [...new Set(kept)].map((w) => ({ raw: w, stem: stem(w) }));
    const hits = [];
    for (const d of docs) {
      let score = 0, matched = 0, titleAll = true;
      const stepScore = new Map();
      for (const tok of toks) {
        let best = 0, inTitle = false;
        for (const f of d.fields) {
          let fq = 0;
          for (const w of f.words) fq = Math.max(fq, quality(tok, w));
          if (!fq) continue;
          best = Math.max(best, fq * f.w);
          if (f.w === 3) inTitle = true;
          if (f.step) stepScore.set(f.step, (stepScore.get(f.step) || 0) + fq);
        }
        if (best) { matched++; score += best; }
        if (!inTitle) titleAll = false;
      }
      if (!matched) continue;
      let step = null, top = 0;
      for (const [n, s] of stepScore) if (s > top) { top = s; step = n; }
      hits.push({ t: d.t, score, matched, step: titleAll ? null : step });
    }
    const all = hits.filter((h) => h.matched === toks.length).sort((a, b) => b.score - a.score);
    if (all.length) return { toks, exact: true, hits: all };
    return { toks, exact: false, hits: hits.sort((a, b) => b.matched - a.matched || b.score - a.score).slice(0, 5) };
  }
  // Wrap the words a query matched in <mark>.
  const mark = (text, toks) =>
    String(text).split(/([A-Za-z0-9]+)/).map((part, i) => {
      if (i % 2 === 0) return esc(part);
      const lower = part.toLowerCase();
      const w = { raw: lower, stem: stem(lower) };
      return toks.some((t) => quality(t, w) > 0) ? "<mark>" + esc(part) + "</mark>" : esc(part);
    }).join("");

  function drawResults() {
    const query = q.value.trim();
    const r = search(query);
    const quoted = "\\u201c" + esc(query) + "\\u201d";
    if (!r.hits.length) {
      results.innerHTML = '<p class="hv-res-h">Nothing matches ' + quoted + '.</p>';
      return;
    }
    const head = r.exact
      ? r.hits.length + (r.hits.length === 1 ? " how-to matches " : " how-tos match ") + quoted
      : "No how-to matches all of " + quoted + ". Closest:";
    results.innerHTML = '<p class="hv-res-h">' + head + '</p><div class="hv-card"><ul class="hv-rows">' +
      r.hits.map((h) => {
        const s = h.step ? h.t.steps.find((x) => x.n === h.step) : null;
        return '<li><a class="hv-row" href="#/t/' + esc(h.t.slug) + (s ? "/" + s.n : "") + '">' +
          '<span class="hv-row-t">' + mark(h.t.title, r.toks) + '</span>' +
          '<span class="hv-row-m">' + h.t.steps.length + " steps \\u00b7 " + clock(h.t.seconds) + ' video</span>' +
          '<span class="hv-row-go" aria-hidden="true">&rsaquo;</span>' +
          '<span class="hv-row-p">' + mark(h.t.path.join(" \\u203a "), r.toks) + '</span>' +
          (s ? '<span class="hv-row-s"><b>Step ' + s.n + ':</b> ' + mark(s.text, r.toks) + '</span>' : "") +
          '</a></li>';
      }).join("") + '</ul></div>';
  }

  // ---------------- views ----------------
  let listY = 0;
  let view = "list";
  const railLinks = [...document.querySelectorAll(".hv-tree a")];
  const markRail = (cat) => railLinks.forEach((a) => a.classList.toggle("on", a.dataset.cat === cat));
  const topOfMain = () => window.scrollTo({ top: Math.max(0, $("hv-main").offsetTop - 90) });

  function showList(cat) {
    detail.hidden = true;
    detail.innerHTML = ""; // drop the video element so nothing keeps downloading
    const searching = !!q.value.trim();
    index.hidden = searching;
    results.hidden = !searching;
    if (searching) drawResults();
    markRail(cat == null ? "" : cat);
    if (cat) {
      const el = document.getElementById("c-" + cat);
      if (el) el.scrollIntoView();
    } else if (view === "detail") {
      window.scrollTo({ top: listY });
    }
    view = "list";
  }

  function showDetail(t, stepN) {
    if (view === "list") listY = window.scrollY;
    view = "detail";
    index.hidden = true;
    results.hidden = true;
    detail.hidden = false;
    markRail(t.cat);
    const base = t.base + "/";
    detail.innerHTML =
      '<a class="hv-back" href="#/">&lsaquo; All how-tos</a>' +
      '<div class="hv-crumb">' + t.path.map(esc).join(" \\u203a ") + '</div>' +
      '<h2 class="hv-title">' + esc(t.title) + '</h2>' +
      '<p class="hv-meta">' + t.steps.length + ' steps \\u00b7 <button type="button" class="hv-linkbtn" data-play>Watch the ' + clock(t.seconds) + ' video</button></p>' +
      '<ol class="hv-steplist">' + t.steps.map((s) =>
        '<li class="hv-s" id="s-' + s.n + '">' +
          '<div class="hv-s-text"><span class="hv-s-n">' + s.n + '</span><p>' + esc(s.text) + '</p></div>' +
          '<button type="button" class="hv-shot" data-zoom="' + esc(base + s.image) + '" aria-label="Enlarge the step ' + s.n + ' screenshot">' +
            '<img src="' + esc(base + s.image) + '" alt="" loading="lazy" width="960" height="600"></button>' +
        '</li>').join("") + '</ol>' +
      '<div class="hv-watch" id="hv-watch"><button type="button" class="hv-play" data-play>' +
        '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 1.5v11l9-5.5z" fill="currentColor"/></svg>' +
        'Watch the video (' + clock(t.seconds) + ')</button></div>';
    for (const b of detail.querySelectorAll("[data-play]")) b.addEventListener("click", () => play(t));
    const target = stepN && document.getElementById("s-" + stepN);
    if (target) {
      target.classList.add("on");
      target.scrollIntoView();
    } else {
      topOfMain();
    }
  }

  // The video is fetched only here, when someone asks for it.
  function play(t) {
    const box = $("hv-watch");
    if (!box.querySelector("video")) {
      box.innerHTML = '<div class="hv-player"><video controls playsinline autoplay src="' + esc(t.base + "/" + t.video) + '"></video></div>';
    }
    box.scrollIntoView({ block: "center" });
  }

  function route() {
    const [kind, a, b] = location.hash.replace(/^#\\/?/, "").split("/");
    if (kind === "t" && bySlug.has(a)) return showDetail(bySlug.get(a), Number(b) || 0);
    if (kind === "c") q.value = "";
    showList(kind === "c" ? a : null);
  }

  // ---------------- wiring ----------------
  window.addEventListener("hashchange", route);
  railLinks.forEach((a) => a.addEventListener("click", (e) => {
    if (a.getAttribute("href") === location.hash || (a.getAttribute("href") === "#/" && !location.hash)) { e.preventDefault(); q.value = ""; route(); }
  }));
  q.addEventListener("input", () => {
    if (view === "detail") { location.hash = "#/"; return; } // hashchange draws the results
    showList(null);
  });
  q.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { const first = results.querySelector("a"); if (first) first.click(); }
    if (e.key === "Escape") { q.value = ""; showList(null); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== q && !zoom.open) { e.preventDefault(); q.focus(); }
  });
  detail.addEventListener("click", (e) => {
    const shot = e.target.closest("[data-zoom]");
    if (!shot) return;
    zoom.querySelector("img").src = shot.dataset.zoom;
    zoom.showModal();
  });
  zoom.addEventListener("click", () => zoom.close());
  route();
})();
</script>
</body>
</html>
`;

writeFileSync(join(out, "index.html"), html);
const kb = (b) => `${Math.round(b / 1024)} KB`;
console.log(
  `${join(out, "index.html")}: ${total} tutorials. Index page loads no media; ` +
    `a tutorial's screenshots average ${kb(shotBytes / Math.max(total, 1))}; ` +
    `videos load on Play (${(videoBytes / 1e6).toFixed(1)} MB in all).`,
);
