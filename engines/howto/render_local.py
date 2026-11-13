"""
howto-video renderer on your own computer (no Modal account needed).

    python render_local.py --captures <capture dir>[,<capture dir>...]

Same outputs as render_modal.py (see howto_common.py). Slower: expect a few minutes per video on a
laptop. Needs on PATH: Node 20+, ffmpeg, and `npm install` run once inside ./render (the first
render also downloads Remotion's own headless Chrome, about 100 MB; if that download fails it uses the Chromium
from `npx playwright install chromium`, or any Chrome you name in HOWTO_BROWSER). Captions use the Inter font if
it is installed and fall back to the system sans-serif if not.

Set HOWTO_CONCURRENCY to cap how many frames render in parallel (default: half your CPU cores).
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

from howto_common import TITLE_SEC, make_outputs, write_results

HERE = pathlib.Path(__file__).resolve().parent
RENDER = HERE / "render"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", required=True, help="capture dir(s), comma separated")
    args = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not on PATH. Install it first (https://ffmpeg.org/download.html).")
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        sys.exit("npx is not on PATH. Install Node 20 or newer.")
    if not (RENDER / "node_modules").exists():
        sys.exit(f"Run `npm install` inside {RENDER} first.")
    # Remotion draws frames in its own headless Chrome; fetch it once (a no-op when already there). If the download
    # fails, use the Chromium that `npx playwright install chromium` already put on this machine. You can also point
    # HOWTO_BROWSER at any Chrome or Chromium executable.
    browser = os.environ.get("HOWTO_BROWSER")
    if not browser and subprocess.run([npx, "remotion", "browser", "ensure"], cwd=RENDER).returncode != 0:
        node = shutil.which("node") or shutil.which("node.exe")
        probe = subprocess.run(
            [node, "-e", "import('playwright').then(p=>console.log(p.chromium.executablePath()))"],
            cwd=HERE, capture_output=True, text=True,
        )
        browser = probe.stdout.strip() or None
        if not browser or not pathlib.Path(browser).exists():
            sys.exit("Remotion could not download its browser and no Playwright Chromium was found. "
                     "Run `npx playwright install chromium`, or set HOWTO_BROWSER to a Chrome executable.")
        print(f"Remotion's browser download failed; using Playwright's Chromium: {browser}")
    conc = os.environ.get("HOWTO_CONCURRENCY") or str(max(1, (os.cpu_count() or 2) // 2))

    for c in [c.strip() for c in args.captures.split(",") if c.strip()]:
        cap = pathlib.Path(c).resolve()
        timeline = json.loads((cap / "timeline.json").read_text())
        job = f"local-{timeline['slug']}"
        pub = RENDER / "public" / "capture" / job
        shutil.rmtree(pub, ignore_errors=True)
        pub.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cap, pub)
        work = pathlib.Path(tempfile.mkdtemp(prefix="howto-render-"))
        try:
            props = work / "props.json"
            props.write_text(json.dumps({"timeline": timeline, "base": f"capture/{job}", "titleSec": TITLE_SEC}))
            out = work / "out.mp4"
            t0 = time.time()
            subprocess.run(
                [npx, "remotion", "render", "src/index.ts", "HowTo", str(out),
                 f"--props={props}", f"--concurrency={conc}", "--codec=h264", "--crf=18", "--log=warn"]
                + ([f"--browser-executable={browser}"] if browser else []),
                cwd=RENDER, check=True,
            )
            secs = time.time() - t0
            res = make_outputs(out, timeline, work / "w")
            write_results(cap, {**res, "render_seconds": round(secs, 1)})
        finally:
            shutil.rmtree(pub, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
