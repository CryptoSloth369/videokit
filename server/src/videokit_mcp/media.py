"""Looking at results: contact sheets of videos, and images sized for an AI to read."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from . import config

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def probe(path: Path) -> dict:
    r = subprocess.run([config.ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise ValueError(f"ffprobe could not read {path}: {r.stderr.strip()[:300]}")
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = v.get("avg_frame_rate", "0/1")
    num, den = (int(x) for x in fps.split("/")) if "/" in fps else (0, 1)
    return {"seconds": round(float(d.get("format", {}).get("duration", 0)), 3),
            "width": v.get("width"), "height": v.get("height"), "fps": round(num / den, 3) if den else None,
            "video_codec": v.get("codec_name"), "has_audio": a is not None,
            "audio_codec": a.get("codec_name") if a else None,
            "bytes": int(d.get("format", {}).get("size", 0))}


def contact_sheet(video: Path, frames: int, cols: int, width: int, out: Path | None = None) -> tuple[Path, dict]:
    info = probe(video)
    dur = info["seconds"] or 1
    frames = max(1, min(frames, 36))
    cols = max(1, min(cols, frames))
    rows = -(-frames // cols)
    out = out or Path(tempfile.mkdtemp(prefix="videokit-sheet-")) / f"{video.stem}-sheet.jpg"
    # Sample the middle of each of `frames` equal slices, with the time stamped on every tile.
    vf = (f"fps={frames}/{dur:.3f},scale={width}:-2,"
          f"drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,"
          f"tile={cols}x{rows}:padding=4:color=black")
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-ss", f"{dur / frames / 2:.3f}", "-i", str(video),
                        "-vf", vf, "-frames:v", "1", "-q:v", "4", str(out)], capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not out.exists():
        # drawtext needs a font build; retry without timestamps rather than fail
        vf = f"fps={frames}/{dur:.3f},scale={width}:-2,tile={cols}x{rows}:padding=4:color=black"
        r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-ss", f"{dur / frames / 2:.3f}", "-i", str(video),
                            "-vf", vf, "-frames:v", "1", "-q:v", "4", str(out)], capture_output=True, text=True,
                           timeout=300)
        if r.returncode != 0:
            raise ValueError(f"ffmpeg could not make a contact sheet: {r.stderr.strip()[:300]}")
    return out, info


def fit_image(path: Path, max_side: int = 1600) -> Path:
    """Large images cost the AI many tokens; downscale anything over max_side (pixel art scaled with nearest)."""
    r = subprocess.run([config.ffprobe(), "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=30)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
    except ValueError:
        return path
    if max(w, h) <= max_side:
        return path
    out = Path(tempfile.mkdtemp(prefix="videokit-img-")) / (path.stem + ".png")
    scale = f"scale='if(gt(iw,ih),{max_side},-2)':'if(gt(iw,ih),-2,{max_side})'"
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-i", str(path), "-vf", scale, "-frames:v", "1", str(out)],
                   check=True, timeout=60)
    return out
