"""
Shared by render_modal.py (cloud render) and render_local.py (render on your own machine).

Both turn one capture folder (what record.mjs writes) into the same outputs:
    <slug>/<slug>.mp4      the video (1920x1080, H.264, CRF 18: the master)
    <slug>/review/*.jpg    one still per step (plus the title card) to check it without playing it
    <slug>/web/            what a tutorial page serves: <slug>.mp4 (CRF 26, faststart, a fraction of the
                           master's size), poster.jpg, steps/NN.jpg (the app only, cropped at each step)
                           and howto.json (title, steps, step start times, files)
Needs ffmpeg on PATH wherever this runs (Modal's image installs it; locally you install it).
"""
import json
import pathlib
import shutil
import subprocess

TITLE_SEC = 2.4
# Where HowTo.tsx draws the app inside the 1920x1080 frame (FRAME there): the step crops use it.
APP_CROP = "crop=1440:900:240:22"


def make_outputs(out: pathlib.Path, timeline: dict, work: pathlib.Path) -> dict:
    """Cut stills, the web copy, the poster and the step crops from the finished master MP4."""
    work.mkdir(parents=True, exist_ok=True)

    def grab(at: float, jpg: pathlib.Path, vf: str | None = None, q: int = 3) -> bytes:
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at:.2f}", "-i", str(out), "-frames:v", "1"]
        subprocess.run(cmd + (["-vf", vf] if vf else []) + ["-q:v", str(q), str(jpg)], check=True)
        return jpg.read_bytes()

    # One still per step, just before the step ends (its result and caption both on screen).
    marks = [("00-title", 1.2)] + [
        (f"{s['i'] + 1:02d}-step", TITLE_SEC + max(s["t0"] + 0.4, s["t1"] - 0.35)) for s in timeline["steps"]
    ]
    stills = {name: grab(at, work / f"{name}.jpg") for name, at in marks}

    # Web copy. Screen recordings are mostly still pictures, so CRF 26 looks the same as the master
    # on a phone at a fraction of the bytes; faststart lets it play before it finishes downloading.
    web = work / "web.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(out), "-c:v", "libx264", "-preset", "slow", "-crf", "26",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(web)],
        check=True,
    )
    poster = grab(1.2, work / "poster.jpg", "scale=1280:-2", 4)

    # The tutorial page's screenshot for a step. A click step shows the moment just before the click
    # (cursor on the button, ring at full strength, page not changed yet): the reader needs to see
    # WHERE to click, and the end-of-step still above already shows the next page. Other steps use
    # the review mark.
    def guide_at(s, review_at):
        click = next((c for c in timeline.get("clicks", []) if s["t0"] <= c["t"] <= s["t1"]), None)
        return TITLE_SEC + click["t"] - 0.12 if click else review_at

    steps = {
        f"{s['i'] + 1:02d}": grab(guide_at(s, at), work / f"crop-{s['i']}.jpg", f"{APP_CROP},scale=960:-2", 4)
        for s, (_, at) in zip(timeline["steps"], marks[1:])
    }
    meta = {
        "slug": timeline["slug"],
        "title": timeline["title"],
        "subtitle": timeline.get("subtitle"),
        "app": timeline.get("app"),
        "seconds": round(TITLE_SEC + timeline["duration"] + 0.2, 2),
        "video": f"{timeline['slug']}.mp4",
        "poster": "poster.jpg",
        "steps": [
            {"n": s["i"] + 1, "text": s["text"], "at": round(TITLE_SEC + s["t0"], 2), "image": f"steps/{s['i'] + 1:02d}.jpg"}
            for s in timeline["steps"]
        ],
    }
    return {"slug": timeline["slug"], "mp4": out.read_bytes(), "stills": stills,
            "web": {"mp4": web.read_bytes(), "poster": poster, "steps": steps, "meta": meta}}


def write_results(cap: pathlib.Path, res: dict) -> None:
    """Write a render result beside its capture folder: <slug>.mp4, review/, web/."""
    mp4 = cap.parent / f"{res['slug']}.mp4"
    mp4.write_bytes(res["mp4"])
    review = cap.parent / "review"
    shutil.rmtree(review, ignore_errors=True)
    review.mkdir()
    for name, data in res["stills"].items():
        (review / f"{name}.jpg").write_bytes(data)
    web = cap.parent / "web"
    shutil.rmtree(web, ignore_errors=True)
    (web / "steps").mkdir(parents=True)
    w = res["web"]
    (web / w["meta"]["video"]).write_bytes(w["mp4"])
    (web / "poster.jpg").write_bytes(w["poster"])
    for n, data in w["steps"].items():
        (web / "steps" / f"{n}.jpg").write_bytes(data)
    meta = {**w["meta"], "bytes": len(w["mp4"])}
    (web / "howto.json").write_text(json.dumps(meta, indent=2) + "\n")
    secs = res.get("render_seconds")
    print(f"{res['slug']}: {mp4} ({len(res['mp4']) / 1e6:.1f} MB master, {len(w['mp4']) / 1e6:.1f} MB web"
          + (f", rendered in {secs}s)" if secs else ")"))
