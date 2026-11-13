"""Claude Animation Base: p5.js + p5.brush character animation, rendered by the kit's own render.mjs."""

from __future__ import annotations

import os
from pathlib import Path

from .. import config, fonts, jobs
from .base import Engine, EngineError


class Animation(Engine):
    def scaffold(self, project_dir: Path, style: str, options: dict) -> dict:
        if project_dir.exists() and any(project_dir.iterdir()):
            raise EngineError(f"{project_dir} is not empty; give a new folder for the animation project")
        fonts.copy_tree(self.meta.source, project_dir, skip=(".git", "node_modules", "out", "docs"))
        try:
            localized = fonts.localize(project_dir / "studio.html")
        except Exception as e:  # offline: the page still works where Chrome can reach Google Fonts
            localized, err = [], str(e)
        else:
            err = ""
        res = {
            "project_dir": str(project_dir), "fonts_made_local": localized,
            "next": ["Read get_guide('claude-animation-base', 'videokit'), then 'guide' (ANIMATION_GUIDE.md).",
                     "Write the scenes in src/scenes/, check with render(..., {action: 'sheet', times: [...]}).",
                     "render('claude-animation-base', project_dir) makes out/video.mp4."],
            "character_warning": "Clawd is Anthropic's character: design your own for any published video.",
        }
        if err:
            res["font_warning"] = f"could not make the Google Font local ({err}); renders need internet access"
        if not config.has_gpu():
            res["gpu_warning"] = ("No GPU on this machine: avoid p5.brush watercolour fills (bleed/tex); "
                                  "use wash colour and ink lines, or a 10 s video takes hours.")
        return res

    def render(self, project_dir: Path | None, options: dict) -> jobs.Job:
        if project_dir is None or not (project_dir / "render.mjs").exists():
            raise EngineError("project_dir must be a project made by scaffold('claude-animation-base', ...)")
        node, npm = config.node(), config.npm()
        if not node or not npm:
            raise EngineError("Node.js 20+ with npm is needed")
        chrome = config.chrome()
        common = [f"--chrome={chrome}"] if chrome else []
        if not config.has_gpu():
            common.append("--soft-gl")
        if options.get("fps"):
            common.append(f"--fps={int(options['fps'])}")
        rng = [f"--range={options['range']}"] if options.get("range") else []
        action = options.get("action", "video")
        plan = []
        if not (project_dir / "node_modules" / "p5.brush").exists():
            plan.append(jobs.Step("npm ci", [npm, "ci", "--no-audit", "--no-fund"], cwd=str(project_dir)))
        if action == "sheet":
            times = ",".join(str(t) for t in options.get("times") or [])
            if not times:
                raise EngineError("action 'sheet' needs times: [seconds, ...]")
            out = project_dir / "out" / "check" / options.get("name", "sheet.jpg")
            plan.append(jobs.Step("contact sheet", [node, "render.mjs", f"--sheet={times}", f"--out={out}", *common],
                                  cwd=str(project_dir)))
        elif action == "video":
            out = project_dir / "out" / options.get("name", "video.mp4")
            workers = int(options.get("workers") or max(1, (os.cpu_count() or 2)))
            audio = [f"--audio={options['audio']}"] if options.get("audio") else []
            if rng or options.get("fresh"):
                # encode joins every frame in out/frames: drop frames left by an earlier, different render
                import shutil
                plan.append(jobs.Step("clear old frames", func=lambda: shutil.rmtree(project_dir / "out" / "frames",
                                                                                     ignore_errors=True)))
            plan += [
                jobs.Step(f"frames ({workers} workers)", [node, "render.mjs", "--frames", f"--workers={workers}",
                                                          *rng, *common], cwd=str(project_dir)),
                jobs.Step("encode", [node, "render.mjs", "--encode", f"--out={out}", *audio, *common],
                          cwd=str(project_dir)),
            ]
        else:
            raise EngineError("action must be 'video' or 'sheet'")
        notes = [] if config.has_gpu() else [
            "Software graphics: watercolour fills take ~25 s per frame. Frames are resumable: a stopped job can be "
            "started again and keeps the frames already in out/frames."]
        return jobs.start(self.meta.id, f"animation {action}: {project_dir.name}", plan,
                          lambda: [str(out)] if out.exists() else [], notes=notes)
