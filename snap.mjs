// ARIA snapshot + screenshot of app pages, signed in the way an app's howto.config.mjs says. Read-only helper for
// writing step files: grep the .txt files for `button "`, `link "`, `heading "`, `textbox "`, `combobox`.
//
//   node snap.mjs <howto.config.mjs> <outdir> <path> [more paths ...]
//
// Writes <name>.txt (URL + ARIA snapshot) and <name>.png (1440x900) per path. Like record.mjs, it refuses every
// request but GET/HEAD/OPTIONS unless the config lists its path in readsOverPost. On Git Bash set
// MSYS_NO_PATHCONV=1 first, or paths like /t/... get mangled.
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";

const [configPath, outDir, ...paths] = process.argv.slice(2);
if (!configPath || !outDir || !paths.length) {
  console.error("usage: node snap.mjs <howto.config.mjs> <outdir> <path> [more paths ...]");
  process.exit(1);
}
const cfg = (await import(pathToFileURL(resolve(configPath)).href)).default;
const baseUrl = cfg.baseUrl;
const appOrigin = new URL(baseUrl).origin;
// Same rules as record.mjs's allowList: exact paths, `*` = one segment, `**` = the rest. Plus Next's dev overlay.
function allowList(entries) {
  const exact = new Set(entries.filter((p) => !p.includes("*")));
  const esc = (s) => s.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  const pats = entries
    .filter((p) => p.includes("*"))
    .map((p) => new RegExp(`^${p.split("**").map((part) => part.split("*").map(esc).join("[^/]+")).join(".*")}$`));
  return { has: (path) => exact.has(path) || pats.some((re) => re.test(path)) };
}
const readsOverPost = allowList([...(cfg.readsOverPost ?? []), "/__nextjs_original-stack-frames"]);
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: cfg.viewport ?? { width: 1440, height: 900 } });
const blocked = [];
await context.route("**/*", (route) => {
  const req = route.request();
  const method = req.method();
  if (method === "GET" || method === "HEAD" || method === "OPTIONS") return route.continue();
  const u = new URL(req.url());
  if (u.origin === appOrigin && readsOverPost.has(u.pathname)) return route.continue();
  blocked.push(`${method} ${u.pathname}`);
  return route.abort("blockedbyclient");
});
if (cfg.signIn) await cfg.signIn(context, { baseUrl });
const page = await context.newPage();
for (const p of paths) {
  await page.goto(baseUrl + p, { waitUntil: "load" });
  await page.waitForTimeout(1200);
  const name = p.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, (id) => id.slice(0, 8)).replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "root";
  const snap = await page.locator("body").ariaSnapshot();
  writeFileSync(join(outDir, `${name}.txt`), `URL ${page.url()}\n\n${snap}`);
  await page.screenshot({ path: join(outDir, `${name}.png`) });
  console.log(name, snap.split("\n").length, "lines");
}
console.log("refused writes:", blocked.length ? blocked : "none");
await browser.close();
