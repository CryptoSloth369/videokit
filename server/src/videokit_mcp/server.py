"""videokit MCP server: one set of tools over several code-to-video engines."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image

from . import config, engines, jobs, media
from .engines import EngineError

INSTRUCTIONS = """\
videokit makes videos by writing code: you (the AI) write the animation, an engine renders it in headless Chrome,
ffmpeg encodes the MP4. Nothing here is a text-to-video model.

Workflow:
1. list_engines -> pick the engine that fits (each lists what it is good for and its license terms).
2. get_guide(engine) and FOLLOW it: the guides hold the hard-won rules that make the videos good.
3. list_styles(engine, query) where the engine has styles/effects.
4. setup_engine(engine) once if list_engines says it is not ready.
5. scaffold(engine, project_dir) to create a project, then write or edit its code.
6. render(engine, project_dir, options) -> returns a job id at once; poll job_status(job_id) every 20-60 s.
7. look(path) at the result (videos become a contact sheet) and fix what you see before calling it done.

Licensing is enforced by the server: in service mode, personal-only material is hidden. Respect each engine's
license.notes (for example: no third-party characters or unlicensed music in monetized videos).
"""

mcp = MCPServer("videokit", instructions=INSTRUCTIONS, version="0.1.0")


def _path(p: str) -> Path:
    if not p:
        raise EngineError("a path is required")
    return Path(os.path.expanduser(p)).resolve()


@mcp.tool()
def check_environment() -> dict[str, Any]:
    """Report the run mode and which programs the engines need were found (Node, Python, ffmpeg, Chrome, GPU)."""
    def ver(cmd: list[str]) -> str | None:
        import subprocess
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip().split("\n")[0]
        except Exception:
            return None
    ff = config.ffmpeg_dir()
    return {
        "mode": config.mode(), "repo": str(config.REPO), "home": str(config.HOME), "os": platform.platform(),
        "node": ver([config.node(), "--version"]) if config.node() else None,
        "python": ver([config.python(), "--version"]),
        "ffmpeg": {"dir": ff, "major_version": config.ffmpeg_major() if ff else None},
        "chrome": config.chrome(), "chrome_headless_shell": config.chrome(headless_shell=True),
        "gpu": config.has_gpu(),
        "warnings": [w for w in [
            None if config.node() else "Node.js 20+ is missing",
            None if ff else "ffmpeg is missing",
            "ffmpeg is older than 7: lemo-opuscar's audio master step will refuse it"
            if ff and (config.ffmpeg_major() or 0) < 7 else None,
            None if config.chrome() else "No Chrome/Chromium found: set VIDEOKIT_CHROME",
            None if config.has_gpu() else "No GPU: 3D, shader and watercolour-brush styles render slowly",
        ] if w],
    }


@mcp.tool()
def list_engines() -> list[dict[str, Any]]:
    """Every engine available in the current mode: what it is good for, whether it is ready, and its license terms."""
    return [e.info() for e in engines.available()]


@mcp.tool()
def get_guide(engine: str, topic: str = "", offset: int = 0, max_chars: int = 40000) -> dict[str, Any]:
    """Read an engine's guide (its rules and workflow). Omit topic for the main guide; list_engines shows the topics.
    Long guides come in pages: call again with offset=next_offset."""
    text = engines.get(engine).guide(topic)
    chunk = text[offset:offset + max_chars]
    nxt = offset + len(chunk)
    return {"engine": engine, "topic": topic or "main", "text": chunk, "total_chars": len(text),
            "next_offset": nxt if nxt < len(text) else None}


@mcp.tool()
def list_styles(engine: str, query: str = "", limit: int = 60) -> dict[str, Any]:
    """Search an engine's styles or effects by words (empty query lists everything, up to limit)."""
    items = engines.get(engine).styles(query)
    return {"engine": engine, "count": len(items), "items": items[:limit]}


@mcp.tool()
def setup_engine(engine: str) -> dict[str, Any]:
    """Install an engine's dependencies (npm/pip). Starts a job; poll job_status."""
    return engines.get(engine).setup().summary()


@mcp.tool()
def scaffold(engine: str, project_dir: str, style: str = "", options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a new project folder for an engine (optionally in a style), ready for you to write the video's code."""
    return engines.get(engine).scaffold(_path(project_dir), style, options or {})


@mcp.tool()
def render(engine: str, project_dir: str = "", options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render a project to video in the background. Returns a job at once; poll job_status(job_id).
    Engine options: howto {steps?: [step files], base_url?, packet?: bool};
    pixelfx {effects: [ids], acted?: bool, formats?: [mp4|gif|sheet], scale?, bg?, seed?, fps?, loops?, opts?}."""
    pd = _path(project_dir) if project_dir else None
    return engines.get(engine).render(pd, options or {}).summary()


@mcp.tool()
def job_status(job_id: str, log_lines: int = 25) -> dict[str, Any]:
    """Status of a background job (queued, running, succeeded, failed, lost), its outputs and the end of its log."""
    try:
        return jobs.get(job_id).summary(log_lines)
    except KeyError as e:
        raise EngineError(str(e)) from None


@mcp.tool()
def list_jobs(limit: int = 10) -> list[dict[str, Any]]:
    """The most recent jobs, newest first."""
    return [j.summary() for j in jobs.recent(limit)]


@mcp.tool(structured_output=False)
def look(path: str, frames: int = 8, cols: int = 4, width: int = 480) -> list[Any]:
    """See a result. A video becomes a contact sheet of `frames` evenly spaced, time-stamped frames plus its
    duration, size and audio; an image is returned as is (downscaled if huge). Always look before you finish."""
    p = _path(path)
    if not p.exists():
        raise EngineError(f"not found: {p}")
    ext = p.suffix.lower()
    if ext in media.VIDEO_EXT:
        sheet, info = media.contact_sheet(p, frames, cols, width)
        return [Image(path=sheet), {"video": str(p), "contact_sheet": str(sheet), **info}]
    if ext in media.IMAGE_EXT:
        return [Image(path=media.fit_image(p)), {"image": str(p)}]
    raise EngineError(f"look() takes a video ({', '.join(sorted(media.VIDEO_EXT))}) or an image")


def main() -> None:
    config.mode()  # fail fast on a bad VIDEOKIT_MODE
    for d in (config.HOME, config.JOBS_DIR, config.OUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    mcp.run()
