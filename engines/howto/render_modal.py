"""
howto-video renderer on Modal: capture folder(s) in, finished MP4(s) out.

    modal run render_modal.py --captures <capture dir>[,<capture dir>...]

A capture dir is what record.mjs writes (frames/ + timeline.json). Each one is uploaded to a Modal
volume, rendered with the Remotion project in ./render on an 8-CPU container, and written back
beside the capture (see howto_common.py for the outputs).

It runs in whichever Modal workspace your `modal` CLI is signed in to (`modal token new`, or
`modal profile list`). Optional environment variables:
    HOWTO_MODAL_APP      Modal app name            (default: howto-video-render)
    HOWTO_MODAL_VOLUME   Modal volume for captures (default: howto-video-captures; created if missing)
No Modal account? Use render_local.py instead: same outputs, rendered on your own computer.

On Windows, set PYTHONIOENCODING=utf-8 first (Modal prints characters the default console cannot).
"""
import json
import os
import pathlib
import shutil
import subprocess
import time

import modal

from howto_common import TITLE_SEC, make_outputs, write_results

HERE = pathlib.Path(__file__).parent
RENDER = HERE / "render"

app = modal.App(os.environ.get("HOWTO_MODAL_APP", "howto-video-render"))
vol = modal.Volume.from_name(os.environ.get("HOWTO_MODAL_VOLUME", "howto-video-captures"), create_if_missing=True)

# Chrome headless shell needs these on Debian (Remotion's Linux dependency list), plus Inter for
# the captions and ffmpeg for the review stills.
image = (
    modal.Image.from_registry("node:22-bookworm-slim", add_python="3.12")
    .apt_install(
        "libnss3", "libdbus-1-3", "libatk1.0-0", "libgbm-dev", "libasound2", "libxrandr2",
        "libxkbcommon-dev", "libxfixes3", "libxcomposite1", "libxdamage1", "libatk-bridge2.0-0",
        "libpango-1.0-0", "libcairo2", "libcups2", "fonts-inter", "ffmpeg",
    )
    .add_local_file(RENDER / "package.json", "/app/package.json", copy=True)
    .add_local_file(RENDER / "package-lock.json", "/app/package-lock.json", copy=True)
    .run_commands("cd /app && npm ci --no-audit --no-fund", "cd /app && npx remotion browser ensure")
    .add_local_dir(RENDER, "/app", copy=True, ignore=["node_modules", "node_modules/**", "out/**", "public/capture/**"])
    .add_local_python_source("howto_common")
)


@app.function(image=image, cpu=8.0, memory=8192, timeout=1800, volumes={"/captures": vol})
def render(job: str) -> dict:
    vol.reload()
    src = pathlib.Path("/captures") / job
    timeline = json.loads((src / "timeline.json").read_text())
    pub = pathlib.Path("/app/public/capture") / job
    pub.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, pub)

    props = pathlib.Path("/tmp/props.json")
    props.write_text(json.dumps({"timeline": timeline, "base": f"capture/{job}", "titleSec": TITLE_SEC}))
    out = pathlib.Path("/tmp/out.mp4")
    t0 = time.time()
    subprocess.run(
        ["npx", "remotion", "render", "src/index.ts", "HowTo", str(out),
         f"--props={props}", "--concurrency=8", "--codec=h264", "--crf=18", "--log=warn"],
        cwd="/app", check=True,
    )
    secs = time.time() - t0
    res = make_outputs(out, timeline, pathlib.Path("/tmp/work"))
    shutil.rmtree(src, ignore_errors=True)
    vol.commit()
    return {**res, "render_seconds": round(secs, 1)}


@app.local_entrypoint()
def main(captures: str):
    caps = [pathlib.Path(c.strip()).resolve() for c in captures.split(",") if c.strip()]
    jobs = []
    stamp = int(time.time())
    with vol.batch_upload(force=True) as batch:
        for cap in caps:
            slug = json.loads((cap / "timeline.json").read_text())["slug"]
            job = f"{slug}-{stamp}"
            batch.put_directory(str(cap), f"/{job}")
            jobs.append((job, cap))
    # Drain map() fully before writing (zip() over its generator left it open: noisy asyncio errors).
    results = list(render.map([j for j, _ in jobs]))
    for (job, cap), res in zip(jobs, results):
        write_results(cap, res)
