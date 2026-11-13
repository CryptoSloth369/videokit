"""Lemo-Opuscar: 99 film styles. The library's own AGENTS.md drives the work; this adapter installs it, finds
styles, creates the project folder and runs the library's render and check tools as background jobs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config, jobs
from .base import Engine, EngineError

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class Lemo(Engine):
    has_style_guides = True

    @property
    def lib(self) -> Path:
        return self.meta.source

    def installed(self) -> tuple[bool, str]:
        ok, missing = super().installed()
        if not ok:
            return ok, missing
        if not (self.lib / "node_modules" / "playwright-core").exists() or not (self.lib / ".venv" / "bin").exists():
            return False, "dependencies not installed: call setup_engine('lemo-opuscar')"
        return True, ""

    def setup(self) -> jobs.Job:
        sh = "/bin/sh"
        env = {"LEMO_OPUSCAR_HOME": str(self.lib)}
        venv_py = str(self.lib / ".venv" / "bin" / "python")
        return jobs.start(self.meta.id, "install lemo-opuscar (core tier)", [
            *self.fetch_steps(),
            jobs.Step("library setup: npm packages, Python core tier",
                      [sh, "plugin/skills/lemo-opuscar/scripts/setup.sh", "deps"], cwd=str(self.lib), env=env),
            # tools/subset.py writes .woff2, which needs brotli; upstream's requirements.txt leaves it out
            jobs.Step("add brotli (woff2 fonts)", [venv_py, "-m", "pip", "install", "-q", "brotli"]
                      if not _has_uv() else ["uv", "pip", "install", "-q", "--python", venv_py, "brotli"],
                      cwd=str(self.lib)),
        ], notes=["ffmpeg 7+ must be on PATH for the mux step (videokit puts ~/.videokit/bin first)."])

    # -- styles ------------------------------------------------------------------------------------------------
    def _styles(self) -> list[dict]:
        self.require()
        out = []
        for f in sorted((self.lib / "styles").glob("*/style.json")):
            if f.parent.name.startswith("_"):
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "slug": d["slug"], "name": d.get("en"), "name_cn": d.get("cn"), "category": d.get("category_en"),
                "demo_film": d.get("film"), "demo_seconds": d.get("dur"), "line": d.get("line"),
                "good_for": d.get("uses", []), "needs": d.get("needs", []),
            })
        return out

    def styles(self, query: str) -> list[dict]:
        words = [w.lower() for w in query.split()]
        items = self._styles()
        if not words:
            return items

        def hay(s: dict) -> str:
            return " ".join(str(v) for v in s.values()).lower()

        scored = [(sum(w in hay(s) for w in words), s) for s in items]
        return [s for n, s in sorted(scored, key=lambda x: -x[0]) if n]

    def style_guide(self, slug: str) -> str:
        if not _SLUG.match(slug) or not (self.lib / "styles" / slug / "STYLE.md").exists():
            raise EngineError(f"no style {slug!r}; find one with list_styles('lemo-opuscar', '<words>')")
        return (self.lib / "styles" / slug / "STYLE.md").read_text(encoding="utf-8")

    # -- project -----------------------------------------------------------------------------------------------
    def scaffold(self, project_dir: Path, style: str, options: dict) -> dict:
        if style:
            self.style_guide(style)  # validates the slug
        if not _SLUG.match(project_dir.name):
            raise EngineError("the project folder name must be lowercase letters, digits and hyphens (no # or ?)")
        project_dir.mkdir(parents=True, exist_ok=True)
        note = project_dir / "VIDEOKIT.json"
        if not note.exists():
            note.write_text(json.dumps({"engine": "lemo-opuscar", "style": style or None, "lib": str(self.lib)},
                                       indent=2) + "\n")
        needs = next((s["needs"] for s in self._styles() if s["slug"] == style), []) if style else []
        return {
            "project_dir": str(project_dir), "lib": str(self.lib), "style": style or None,
            "style_guide": f"get_guide('lemo-opuscar', 'style/{style}')" if style else None,
            "demo_source": str(self.lib / "styles" / style / "demo") if style else None,
            "needs_image_generator": "image-generation" in needs,
            "next": [
                "Read get_guide('lemo-opuscar', 'videokit'), then 'agents', and follow the library's workflow.",
                "The film is <project_dir>/index.html following the page contract in get_guide(..., 'tools').",
                "Check frames with render(..., {action: 'stills', times: [...]}) and look() before a full video.",
            ],
        }

    def render(self, project_dir: Path | None, options: dict) -> jobs.Job:
        ok, missing = self.installed()
        if not ok:
            raise EngineError(missing)
        if project_dir is None:
            raise EngineError("project_dir is required (the folder holding the film's index.html)")
        action = options.get("action", "video")
        node, lib, pd = config.node(), str(self.lib), str(project_dir)
        page_needed = action in ("stills", "video", "events", "readcheck")
        if page_needed and not (project_dir / "index.html").exists():
            raise EngineError(f"{project_dir}/index.html does not exist yet")
        size = ["--size", options["size"]] if options.get("size") else []
        out: list[str] = []
        if action == "stills":
            times = [str(t) for t in options.get("times") or []]
            if not times and not options.get("range"):
                raise EngineError("stills need times: [seconds, ...] or range: 'a:b:step'")
            argv = [node, "core/render/still.mjs", pd, *times, *size, "--out", str(project_dir / "stills")]
            if options.get("range"):
                argv += ["--range", str(options["range"])]
            out_glob = (project_dir / "stills", "*.jpg")
        elif action == "video":
            target = project_dir / "out" / options.get("name", "video.mp4")
            argv = [node, "core/render/video.mjs", pd, "--fps", str(options.get("fps", 24)),
                    "--workers", str(options.get("workers", 3)), *size, "--out", str(target)]
            out = [str(target)]
            out_glob = None
        elif action == "events":
            argv, out_glob = [node, "core/render/events.mjs", pd], None
            out = [str(project_dir / "events.json")]
        elif action == "readcheck":
            argv, out_glob = [node, "core/render/readcheck.mjs", pd, *size], None
        elif action == "mux":
            video = Path(options.get("video") or project_dir / "out" / "video.mp4")
            audio = Path(options.get("audio") or project_dir / "mix.wav")
            final = Path(options.get("out") or project_dir / "out" / "final.mp4")
            for p in (video, audio):
                if not p.exists():
                    raise EngineError(f"not found: {p}")
            if (config.ffmpeg_major() or 0) < 7:
                raise EngineError("mux needs ffmpeg 7+ (see check_environment)")
            argv = ["/bin/sh", "core/render/mux.sh", str(video), str(audio), str(final),
                    str(options.get("fps", 24)), str(options.get("grain", 2))]
            out, out_glob = [str(final)], None
        elif action == "build":
            if not (project_dir / "build.sh").exists():
                raise EngineError(f"{project_dir}/build.sh does not exist")
            argv, out_glob = ["/bin/sh", str(project_dir / "build.sh")], (project_dir, "**/*.mp4")
        else:
            raise EngineError("action must be one of stills, video, events, readcheck, mux, build")

        def outputs() -> list[str]:
            found = [o for o in out if Path(o).exists()]
            if out_glob:
                found += sorted(str(p) for p in out_glob[0].glob(out_glob[1]))
            return found

        notes = [] if config.has_gpu() else [
            "No GPU here: 3D, CRT and shader styles render in software and are slow; 2D styles are fine."]
        return jobs.start(self.meta.id, f"lemo-opuscar {action}: {project_dir.name}",
                          [jobs.Step(action, argv, cwd=lib, env={"LIB": lib})], outputs, notes=notes)


def _has_uv() -> bool:
    import shutil
    return shutil.which("uv") is not None
