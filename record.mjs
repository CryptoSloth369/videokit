#!/usr/bin/env node
/**
 * howto-video recorder: plays one step file in headless Chrome and saves the raw capture.
 *
 *   node record.mjs <step-file.json> [more.json ...] [--out <dir>]
 *
 * The step file's folder must hold `howto.config.mjs` (base URL, viewport, how to sign in, CSS to
 * hide). Output per step file: `<step folder>/out/<slug>/capture/`
 *   frames/fNNNNN.jpg  Chrome's screencast frames, written only when the screen changes
 *   timeline.json      captions, target boxes, cursor moves and clicks, in seconds from frame 0
 * render_modal.py turns that into the finished MP4 on Modal (the cursor, highlight, zoom and
 * captions are drawn there, never baked into the frames).
 *
 * Exit code 2 means a step's target wasn't found: the app changed under the step file. A
 * screenshot of the screen at that moment is saved as failed-step-<n>.png beside the capture.
 *
 * Headless only: no browser window ever comes forward.
 *
 * Read-only, ENFORCED: apps are recorded on demo data only, so every request that could write (any method but GET/HEAD/OPTIONS, to any host) is
 * refused before it leaves the browser, and the run stops with exit code 3 naming the request.
 * A route that only reads over POST (a file parse, a preview) can be let through by listing its
 * path in the config's `readsOverPost`. Flows that save are filmed up to the final button with a
 * `hover`, never a click; if a step would autosave, this guard catches it.
 */
import { chromium } from "playwright";
import { mkdirSync, rmSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const wordCount = (s) => (s ?? "").trim().split(/\s+/).filter(Boolean).length;
/** Same curve the renderer uses for the cursor, so the real mouse and the drawn one agree. */
const ease = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

/**
 * How long a caption needs on screen to be read. Only a short lead comes BEFORE the action (the
 * cursor starts moving as the highlight lands); the rest of the reading time goes into the hold
 * after it. (The zoom and highlight sat too long waiting for the mouse in early cuts.)
 */
const readMs = (text) => clamp(450 + 170 * wordCount(text), 1100, 3000);
const LEAD_MS = 450;

/**
 * readsOverPost entries: an exact path, or a pattern where `*` is one path segment and `**` is the rest of the
 * path ("/api/sb/storage/v1/object/**"). Patterns let a recording copy's uploads and id-in-path routes through
 * (Without patterns, every upload and autosave in an app exits 3.) Same function in snap.mjs.
 */
function allowList(entries) {
  const exact = new Set(entries.filter((p) => !p.includes("*")));
  const esc = (s) => s.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  const pats = entries
    .filter((p) => p.includes("*"))
    .map((p) => new RegExp(`^${p.split("**").map((part) => part.split("*").map(esc).join("[^/]+")).join(".*")}$`));
  return { has: (path) => exact.has(path) || pats.some((re) => re.test(path)) };
}

function parseArgs(argv) {
  const files = [];
  let out = null;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--out") out = argv[++i];
    else files.push(argv[i]);
  }
  return { files, out };
}

/** Step targets map onto Playwright's user-facing locators; `within` scopes to a CSS container. */
function locate(page, t) {
  const base = t.within ? page.locator(t.within) : page;
  const exact = t.exact ?? false;
  let loc;
  if (t.role) loc = base.getByRole(t.role, t.name ? { name: t.name, exact } : {});
  else if (t.label) loc = base.getByLabel(t.label, { exact });
  else if (t.placeholder) loc = base.getByPlaceholder(t.placeholder, { exact });
  else if (t.text) loc = base.getByText(t.text, { exact });
  else if (t.css) loc = base.locator(t.css);
  else if (t.testId) loc = base.getByTestId(t.testId);
  else throw new Error(`target needs role, label, placeholder, text, css or testId: ${JSON.stringify(t)}`);
  return t.nth != null ? loc.nth(t.nth) : loc;
}

/** Wait until the DOM has been quiet for a moment (client-side navigations fire no load event). */
async function settle(page, quietMs = 450, maxMs = 7000) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      await page.evaluate(
        ([quiet, max]) =>
          new Promise((res) => {
            let last = performance.now();
            const start = last;
            const obs = new MutationObserver(() => (last = performance.now()));
            obs.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
            const tick = () => {
              const now = performance.now();
              if (now - last > quiet || now - start > max) {
                obs.disconnect();
                res();
              } else setTimeout(tick, 100);
            };
            setTimeout(tick, 150);
          }),
        [quietMs, maxMs],
      );
      return;
    } catch {
      // A full navigation destroyed the context mid-wait: let it load, then wait again.
      await page.waitForLoadState("load").catch(() => {});
    }
  }
}

async function recordOne(stepFile, outOverride) {
  const stepPath = resolve(stepFile);
  const spec = JSON.parse(readFileSync(stepPath, "utf8"));
  const dir = dirname(stepPath);
  const cfgPath = join(dir, "howto.config.mjs");
  if (!existsSync(cfgPath)) throw new Error(`no howto.config.mjs beside ${stepPath}`);
  const cfg = (await import(pathToFileURL(cfgPath).href)).default;

  const slug = spec.slug ?? basename(stepPath).replace(/\.json$/, "");
  const outDir = outOverride ? resolve(outOverride, slug, "capture") : join(dir, "out", slug, "capture");
  rmSync(outDir, { recursive: true, force: true });
  const framesDir = join(outDir, "frames");
  mkdirSync(framesDir, { recursive: true });

  const vp = cfg.viewport ?? { width: 1440, height: 900 };
  const dsf = cfg.deviceScaleFactor ?? 1.5;
  const baseUrl = (cfg.baseUrl ?? "").replace(/\/$/, "");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: vp,
    deviceScaleFactor: dsf,
    serviceWorkers: "block",
    reducedMotion: "no-preference",
  });
  if (cfg.hideCss) {
    await context.addInitScript((css) => {
      const add = () => {
        const s = document.createElement("style");
        s.dataset.howto = "hide";
        s.textContent = css;
        (document.head ?? document.documentElement).appendChild(s);
      };
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add);
      else add();
    }, cfg.hideCss);
  }
  // Real names that show up even on a demo site (a shared location list, a default in a menu, an
  // example in a placeholder) are swapped for invented ones in the browser before anything is
  // painted, so they never reach a frame. `replaceText` in the config: { "real": "invented" },
  // longest first. Like the apps' own silent demo mode: nothing on screen says it happened.
  if (cfg.replaceText) {
    const pairs = Object.entries(cfg.replaceText).sort((a, b) => b[0].length - a[0].length);
    await context.addInitScript((pairs) => {
      const swap = (s) => {
        let out = s;
        for (const [real, fake] of pairs) if (out.includes(real)) out = out.split(real).join(fake);
        return out;
      };
      const ATTRS = ["placeholder", "title", "aria-label", "alt"];
      const fixEl = (el) => {
        for (const a of ATTRS) {
          const v = el.getAttribute?.(a);
          if (v != null && swap(v) !== v) el.setAttribute(a, swap(v));
        }
      };
      const fix = (node) => {
        if (node.nodeType === 3) {
          const v = swap(node.nodeValue);
          if (v !== node.nodeValue) node.nodeValue = v;
          return;
        }
        if (node.nodeType !== 1) return;
        fixEl(node);
        const walk = document.createTreeWalker(node, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
          if (n.nodeType === 3) {
            const v = swap(n.nodeValue);
            if (v !== n.nodeValue) n.nodeValue = v;
          } else fixEl(n);
        }
      };
      new MutationObserver((muts) => {
        for (const m of muts) {
          if (m.type === "childList") m.addedNodes.forEach(fix);
          else if (m.type === "characterData") fix(m.target);
          else if (m.type === "attributes") fixEl(m.target);
        }
      }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
      const all = () => fix(document.documentElement);
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", all);
      else all();
    }, pairs);
  }

  if (cfg.signIn) await cfg.signIn(context, { baseUrl });

  // The write guard (see the header). Refused requests never reach the server.
  const blocked = [];
  const appOrigin = new URL(baseUrl).origin;
  // `/__nextjs_original-stack-frames` is Next's dev error overlay reading source maps: never app data. A dev-mode
  // warning (e.g. a duplicate React key) fires it, and refusing it stopped a take with exit 3.
  const readsOverPost = allowList([...(cfg.readsOverPost ?? []), "/__nextjs_original-stack-frames"]);
  await context.route("**/*", (route) => {
    const req = route.request();
    const method = req.method();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") return route.continue();
    const u = new URL(req.url());
    if (u.origin === appOrigin && readsOverPost.has(u.pathname)) return route.continue();
    blocked.push(`${method} ${u.origin === appOrigin ? u.pathname : u.href}`);
    return route.abort("blockedbyclient");
  });
  const assertNoWrites = (where) => {
    if (!blocked.length) return;
    const e = new Error(`${where} tried to write (${blocked.join(", ")}); refused, nothing was saved`);
    e.code = 3;
    throw e;
  };

  const page = await context.newPage();
  await page.goto(baseUrl + spec.start, { waitUntil: "load" });
  await settle(page, 600, 10000);
  try {
    assertNoWrites("opening the start page");
  } catch (err) {
    await browser.close();
    throw err;
  }

  // ---- capture -----------------------------------------------------------------------------
  const frames = [];
  let n = 0;
  const t0 = Date.now() / 1000;
  const first = "f00000.jpg";
  writeFileSync(join(framesDir, first), await page.screenshot({ type: "jpeg", quality: 90 }));
  frames.push({ file: first, t: 0, hi: true });
  const cdp = await context.newCDPSession(page);
  cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
    const file = `f${String(++n).padStart(5, "0")}.jpg`;
    writeFileSync(join(framesDir, file), Buffer.from(data, "base64"));
    frames.push({ file, t: Math.max(0, metadata.timestamp - t0) });
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: 90,
    maxWidth: Math.round(vp.width * dsf),
    maxHeight: Math.round(vp.height * dsf),
    everyNthFrame: 1,
  });
  const now = () => Date.now() / 1000 - t0;

  // Chrome's screencast always arrives at CSS-pixel size (1440x900), even with a 1.5 device scale,
  // which goes soft once the renderer zooms in. So every time the screen settles we also take a
  // full-resolution screenshot ("still"). The renderer shows the newest frame of either kind, so
  // the stills cover every pause and the low-res frames only fill the motion between them.
  // A screenshot can force a repaint that Chrome also sends as a screencast frame; frames that
  // land inside a still's capture window are dropped at the end.
  const stillWindows = [];
  let sN = 0;
  const still = async () => {
    const tA = now();
    const buf = await page.screenshot({ type: "jpeg", quality: 90 });
    const tB = now();
    const file = `s${String(++sN).padStart(4, "0")}.jpg`;
    writeFileSync(join(framesDir, file), buf);
    frames.push({ file, t: tA, hi: true });
    stillWindows.push([tA - 0.02, tB + 0.12]);
  };

  const steps = [];
  const moves = [];
  const clicks = [];
  const navs = [];
  let cursor = { x: Math.round(vp.width * 0.62), y: Math.round(vp.height * 0.72) };
  const cursorStart = { ...cursor };
  await page.mouse.move(cursor.x, cursor.y);
  await sleep(spec.leadIn ?? 900);

  for (let i = 0; i < spec.steps.length; i++) {
    const st = spec.steps[i];
    const rec = { i, text: st.say, action: st.do, t0: now(), box: null, zoom: st.zoom ?? null };
    const urlBefore = page.url();
    try {
      // Where the eye goes: the target, or a wider `show` box when the step says so.
      let loc = null;
      let box = null;
      if (st.target) {
        loc = locate(page, st.target);
        await loc.waitFor({ state: "visible", timeout: st.timeout ?? 10000 });
        await loc.scrollIntoViewIfNeeded();
        await settle(page, 250, 1500);
        box = await loc.boundingBox();
      }
      const showBox = st.show ? await locate(page, st.show).boundingBox() : box;
      if (showBox) rec.box = { x: showBox.x, y: showBox.y, w: showBox.width, h: showBox.height };

      await still();
      // The step starts on screen HERE, not when we began looking for its target: finding it and
      // waiting for the page to settle can take a second or more, and the renderer shows the zoom,
      // highlight and caption from t0. Until now the previous step's caption stays up.
      rec.t0 = now();
      await sleep(st.read ?? LEAD_MS);

      if (box) {
        const to = { x: Math.round(box.x + box.width / 2), y: Math.round(box.y + box.height / 2) };
        const dist = Math.hypot(to.x - cursor.x, to.y - cursor.y);
        const ms = clamp(220 + dist * 0.55, 380, 800);
        const m = { t0: now(), from: { ...cursor }, to, t1: 0 };
        // Clock-driven, not a fixed count of moves: each page.mouse.move is a round trip to Chrome,
        // and 60 of them stretched a planned 1 s glide to ~2 s (the drawn cursor crawled with it).
        const start = Date.now();
        for (;;) {
          const k = clamp((Date.now() - start) / ms, 0, 1);
          const e = ease(k);
          await page.mouse.move(cursor.x + (to.x - cursor.x) * e, cursor.y + (to.y - cursor.y) * e);
          if (k >= 1) break;
          await sleep(10);
        }
        m.t1 = now();
        moves.push(m);
        cursor = to;
        await settle(page, 120, 600);
        await still(); // the hover state, sharp
      }

      switch (st.do) {
        case "click":
          clicks.push({ t: now(), x: cursor.x, y: cursor.y });
          await loc.click();
          break;
        case "type":
          clicks.push({ t: now(), x: cursor.x, y: cursor.y });
          await loc.click();
          await loc.fill("");
          await loc.pressSequentially(String(st.value ?? ""), { delay: st.typeDelay ?? 75 });
          break;
        case "select":
          clicks.push({ t: now(), x: cursor.x, y: cursor.y });
          await loc.selectOption(st.value);
          break;
        case "press":
          await page.keyboard.press(st.key);
          break;
        case "upload": {
          // Click the visible file control and answer the file picker with `file` (a path relative to
          // the step file, invented data only). Headless: no picker window ever opens.
          clicks.push({ t: now(), x: cursor.x, y: cursor.y });
          const [chooser] = await Promise.all([page.waitForEvent("filechooser", { timeout: 10000 }), loc.click()]);
          // `files` (a list) picks several at once, for pickers that take more than one.
          await chooser.setFiles(st.files ? st.files.map((f) => resolve(dir, f)) : resolve(dir, st.file));
          // A loaded file replaces the view like a page change: mark it as one, so the renderer
          // drops the ring and zoom on the file button (which is gone) instead of leaving an empty box.
          navs.push({ t: now(), url: `${page.url().replace(baseUrl, "")} (file loaded)` });
          break;
        }
        case "goto":
          await page.goto(baseUrl + st.url, { waitUntil: "load" });
          break;
        case "scroll": {
          const dy = st.dy ?? 400;
          const parts = 12;
          const t = { t0: now() };
          for (let k = 0; k < parts; k++) {
            await page.mouse.wheel(0, dy / parts);
            await sleep(45);
          }
          rec.scroll = { ...t, t1: now() };
          break;
        }
        case "look":
        case "hover":
        case undefined:
          break;
        default:
          throw new Error(`unknown action "${st.do}"`);
      }

      const tAct = now();
      if (st.waitFor) await locate(page, st.waitFor).waitFor({ state: "visible", timeout: 15000 });
      await settle(page);
      // The action can move the page under the ring (a ticked box shifts the form, a saved row appears) or
      // remove what it framed. Re-measure, so the ring follows or fades instead of framing an empty spot
      // (a ring framing an empty spot looked broken in stills). look/hover change nothing, so they keep their box.
      if (rec.box && !["look", "hover", undefined].includes(st.do)) {
        const framed = st.show ? locate(page, st.show) : loc;
        const after = framed ? await framed.boundingBox({ timeout: 500 }).catch(() => null) : null;
        if (!after) rec.boxEnd = tAct;
        else if (["x", "y", "width", "height"].some((k, j) => Math.abs(after[k] - rec.box[["x", "y", "w", "h"][j]]) > 4)) {
          rec.boxAfter = { t: tAct, x: after.x, y: after.y, w: after.width, h: after.height };
        }
      }
      assertNoWrites(`step ${i + 1}`);
      if (page.url() !== urlBefore) navs.push({ t: now(), url: page.url().replace(baseUrl, "") });
      await still();
      await sleep(Math.max(st.hold ?? 1300, readMs(st.say) - 600));
      assertNoWrites(`step ${i + 1}`);
    } catch (err) {
      const shot = join(dirname(outDir), `failed-step-${i + 1}.png`);
      await page.screenshot({ path: shot }).catch(() => {});
      await cdp.send("Page.stopScreencast").catch(() => {});
      await browser.close();
      const msg = String(err?.message ?? err).split("\n")[0];
      const e = new Error(`step ${i + 1} ("${st.say}") failed: ${msg}\n  screenshot: ${shot}`);
      e.code = err?.code === 3 ? 3 : 2;
      throw e;
    }
    rec.t1 = now();
    steps.push(rec);
  }

  await sleep(spec.tail ?? 1200);
  await cdp.send("Page.stopScreencast").catch(() => {});
  const duration = now();
  const late = blocked.length;
  await browser.close();
  if (late) {
    const e = new Error(`the page tried to write after the last step (${blocked.join(", ")}); refused, nothing was saved`);
    e.code = 3;
    throw e;
  }

  const forced = (f) => !f.hi && f.t > 0 && stillWindows.some(([a, b]) => f.t >= a && f.t <= b);
  const kept = frames.filter((f) => !forced(f)).sort((a, b) => a.t - b.t);
  for (const f of frames) if (forced(f)) rmSync(join(framesDir, f.file), { force: true });
  frames.length = 0;
  frames.push(...kept);
  const timeline = {
    version: 1,
    slug,
    title: spec.title,
    subtitle: spec.subtitle ?? null,
    app: cfg.app ?? null,
    accent: cfg.accent ?? "#1735BB",
    viewport: vp,
    dsf,
    duration,
    cursorStart,
    frames,
    steps,
    moves,
    clicks,
    navs,
  };
  writeFileSync(join(outDir, "timeline.json"), JSON.stringify(timeline, null, 1));
  return { slug, outDir, frames: frames.length, duration, steps: steps.length };
}

const { files, out } = parseArgs(process.argv.slice(2));
if (!files.length) {
  console.error("usage: node record.mjs <step-file.json> [more.json ...] [--out <dir>]");
  process.exit(1);
}
let failed = 0;
for (const f of files) {
  try {
    const r = await recordOne(f, out);
    console.log(`recorded ${r.slug}: ${r.steps} steps, ${r.duration.toFixed(1)}s, ${r.frames} frames -> ${r.outDir}`);
  } catch (err) {
    // Our own errors carry a number (2 = target not found, 3 = write refused); Node's carry a string like
    // "ENOENT", which process.exit rejects with a TypeError that hides the real message.
    failed = Number.isInteger(err.code) ? err.code : 1;
    console.error(`FAILED ${f}\n  ${err.message}`);
  }
}
process.exit(failed);
