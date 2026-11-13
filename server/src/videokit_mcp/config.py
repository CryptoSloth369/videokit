"""Paths, run mode and the external programs the engines need (Chrome, ffmpeg, Node, Python)."""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
from functools import cache
from pathlib import Path

# server/src/videokit_mcp/config.py -> repo root is three levels above the package
REPO = Path(os.environ.get("VIDEOKIT_REPO") or Path(__file__).resolve().parents[3])
ENGINES_DIR = REPO / "engines"
VENDOR_DIR = REPO / "vendor"

# Per-user state: jobs, caches, downloaded tools. Never inside the repo.
HOME = Path(os.environ.get("VIDEOKIT_HOME") or Path.home() / ".videokit")
BIN_DIR = HOME / "bin"
JOBS_DIR = HOME / "jobs"
CACHE_DIR = HOME / "cache"
OUT_DIR = HOME / "out"

MODES = ("personal", "service")


def mode() -> str:
    """`personal` (default): everything you may use for your own videos.
    `service`: only what may be offered to other people inside a commercial product."""
    m = os.environ.get("VIDEOKIT_MODE", "personal").strip().lower()
    if m not in MODES:
        raise ValueError(f"VIDEOKIT_MODE must be one of {MODES}, got {m!r}")
    return m


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if p and Path(p).is_file() and os.access(p, os.X_OK):
            return p
    return None


@cache
def ffmpeg_dir() -> str | None:
    """Directory holding ffmpeg + ffprobe. Prefers VIDEOKIT_FFMPEG_DIR, then ~/.videokit/bin, then PATH."""
    for d in (os.environ.get("VIDEOKIT_FFMPEG_DIR"), str(BIN_DIR)):
        if d and _first_existing([str(Path(d) / "ffmpeg")]) and _first_existing([str(Path(d) / "ffprobe")]):
            return d
    found = shutil.which("ffmpeg")
    return str(Path(found).parent) if found and shutil.which("ffprobe") else None


def ffmpeg() -> str:
    d = ffmpeg_dir()
    if not d:
        raise RuntimeError("ffmpeg and ffprobe were not found. Install ffmpeg 7 or newer, or set VIDEOKIT_FFMPEG_DIR.")
    return str(Path(d) / "ffmpeg")


def ffprobe() -> str:
    return str(Path(ffmpeg()).with_name("ffprobe"))


@cache
def ffmpeg_major() -> int | None:
    try:
        line = subprocess.run([ffmpeg(), "-version"], capture_output=True, text=True, timeout=20).stdout.split("\n")[0]
        ver = line.split()[2].lstrip("n")
        return int(ver.split(".")[0])
    except Exception:
        return None


def _chrome_candidates(headless_shell: bool) -> list[str]:
    c: list[str] = []
    pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    if headless_shell:
        c += sorted(glob.glob(f"{pw}/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"), reverse=True)
    c += sorted(glob.glob(f"{pw}/chromium-*/chrome-linux64/chrome"), reverse=True)
    c += sorted(glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")), reverse=True)
    if platform.system() == "Darwin":
        c += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    elif platform.system() == "Windows":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                c.append(str(Path(base) / "Google/Chrome/Application/chrome.exe"))
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if w := shutil.which(name):
            c.append(w)
    return c


@cache
def chrome(headless_shell: bool = False) -> str | None:
    """A Chrome/Chromium executable. `headless_shell=True` prefers chrome-headless-shell (what Remotion wants).
    VIDEOKIT_CHROME always wins."""
    return _first_existing([os.environ.get("VIDEOKIT_CHROME", "")] + _chrome_candidates(headless_shell))


def node() -> str | None:
    return shutil.which("node")


def npm() -> str | None:
    return shutil.which("npm")


def python() -> str:
    """A Python 3.10+ for the engines' own scripts (not this server's venv)."""
    for name in ("python3.13", "python3.12", "python3.11", "python3", "python"):
        if w := shutil.which(name):
            return w
    raise RuntimeError("Python 3.10 or newer is needed.")


def has_gpu() -> bool:
    """Rough check: macOS always has a usable GPU for Chrome; on Linux look for an NVIDIA or DRI device."""
    if platform.system() in ("Darwin", "Windows"):
        return True
    return bool(shutil.which("nvidia-smi")) or bool(glob.glob("/dev/dri/renderD*"))


def job_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for engine subprocesses: our ffmpeg first on PATH, our Chrome advertised to tools that read it."""
    env = dict(os.environ)
    if d := ffmpeg_dir():
        env["PATH"] = d + os.pathsep + env.get("PATH", "")
    if c := chrome():
        env.setdefault("CHROME_PATH", c)
    env.update(extra or {})
    return env
