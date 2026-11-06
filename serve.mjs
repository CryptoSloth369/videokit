// Tiny static server for the example app. No dependencies.
//   node example/serve.mjs            serves example/app on http://127.0.0.1:4173
//   PORT=5000 node example/serve.mjs  pick another port (then set HOWTO_BASE to match when recording)
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "app");
const PORT = Number(process.env.PORT ?? 4173);
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json" };

createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  // A form that posts is answered with the same page: the recorder refuses the write before it gets here.
  let path = normalize(decodeURIComponent(url.pathname)).replace(/^([/\\])+/, "");
  if (path === "" || path.endsWith("/") || path.endsWith("\\")) path = join(path, "index.html");
  if (!extname(path)) path += ".html";
  try {
    const data = await readFile(join(ROOT, path));
    res.writeHead(200, { "content-type": TYPES[extname(path)] ?? "application/octet-stream" });
    res.end(data);
  } catch {
    res.writeHead(404, { "content-type": "text/plain" });
    res.end("Not found");
  }
}).listen(PORT, "127.0.0.1", () => console.log(`Example app on http://127.0.0.1:${PORT}  (Ctrl+C to stop)`));
