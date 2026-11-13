"""Pixel art effects as code (244 ready-made). Renders MP4/GIF previews, acted-out clips and sprite sheets."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from .. import config, jobs
from .base import Engine, EngineError

_LINE = re.compile(r"^(?P<id>[\w-]+/[\w-]+)\s+(?P<play>loop|once)\s+(?P<dur>[\d.]+)s\s+(?P<size>\d+x\d+)\s+"
                   r"(?P<actor>actor\s+)?(?P<desc>.*)$")
_ID = re.compile(r"^[\w-]+(/[\w*-]+)?$")


class PixelFX(Engine):
    def _root(self, project_dir: Path | None) -> Path:
        """A user workspace (made by scaffold, holds their own effects) or the pinned upstream checkout."""
        if project_dir and (project_dir / "tools" / "render.mjs").exists():
            return project_dir
        return self.meta.source

    def styles(self, query: str) -> list[dict]:
        self.require()
        node = config.node()
        if not node:
            raise EngineError("node (18+) is needed")
        import subprocess
        words = [w for w in query.split() if w]
        r = subprocess.run([node, "tools/list.mjs", *words], cwd=self.meta.source, capture_output=True, text=True,
                           timeout=60)
        out = []
        for line in r.stdout.splitlines():
            if m := _LINE.match(line.strip()):
                out.append({"id": m["id"], "plays": m["play"], "seconds": float(m["dur"]), "size": m["size"],
                            "acted": bool(m["actor"]), "description": m["desc"].strip()})
        return out

    def scaffold(self, project_dir: Path, style: str, options: dict) -> dict:
        self.require()
        """Copy the library into a workspace where new effects can be made (tools/new.mjs) without touching
        the pinned upstream copy. No npm install needed: the tools use plain Node."""
        if (project_dir / "tools" / "render.mjs").exists():
            return {"project_dir": str(project_dir), "created": [], "note": "already a pixelfx workspace"}
        if project_dir.exists() and any(project_dir.iterdir()):
            raise EngineError(f"{project_dir} is not empty; give a new folder for the pixelfx workspace")
        src = self.meta.source
        project_dir.mkdir(parents=True, exist_ok=True)
        for part in ("src", "tools", "skills", "package.json", "LICENSE", "NOTICE.md", "docs/CATALOG.md"):
            s, d = src / part, project_dir / part
            if s.is_dir():
                shutil.copytree(s, d)
            elif s.exists():
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(s, d)
        made = {"project_dir": str(project_dir),
                "next": ["Read get_guide('pixelfx', 'skill') for the draft, render, look, refine loop.",
                         "New effect: run `node tools/new.mjs <category>/<name>` inside the workspace, edit "
                         "src/fx/<category>/<name>.js, then render('pixelfx', project_dir, {effects: [...]})."]}
        return made

    def render(self, project_dir: Path | None, options: dict) -> jobs.Job:
        self.require()
        node = config.node()
        if not node:
            raise EngineError("node (18+) is needed")
        effects = options.get("effects") or ([options["effect"]] if options.get("effect") else [])
        if not effects:
            raise EngineError("options.effects is required, e.g. {'effects': ['fire/campfire']} (see list_styles)")
        for e in effects:
            if not _ID.match(e):
                raise EngineError(f"bad effect id {e!r}: use <category>/<name>, a category, or a pattern like 'fire/*'")
        root = self._root(project_dir)
        out = (project_dir / "out") if project_dir else config.OUT_DIR / "pixelfx" / time.strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True, exist_ok=True)
        acted = bool(options.get("acted"))
        fmts = options.get("formats") or ["mp4"]
        bad = set(fmts) - {"mp4", "gif", "sheet"}
        if bad:
            raise EngineError(f"unknown formats {bad}; use mp4, gif, sheet")
        common: list[str] = []
        for k in ("bg", "seed", "fps", "scale", "loops"):
            if options.get(k) is not None:
                common += [f"--{k}", str(options[k])]
        if options.get("opts"):
            import json
            common += ["--opts", json.dumps(options["opts"])]
        plan = []
        if acted:
            for e in effects:
                if "*" in e or "/" not in e:
                    raise EngineError("acted renders take exact ids like 'melee/sword-slash'")
                flag = "--sheet" if fmts == ["sheet"] else "--mp4"
                ext = "png" if flag == "--sheet" else "mp4"
                plan.append(jobs.Step(f"act {e}", [node, "tools/act.mjs", e, flag, "--out",
                                                   str(out / f"{e.replace('/', '-')}-act.{ext}"), *common], cwd=str(root)))
        else:
            plan.append(jobs.Step(f"render {' '.join(effects)}",
                                  [node, "tools/render.mjs", *effects, *[f"--{f}" for f in fmts], "--out", str(out),
                                   *common], cwd=str(root)))

        def outputs() -> list[str]:
            return sorted(str(p) for p in out.rglob("*") if p.suffix in (".mp4", ".gif", ".png", ".json")
                          and p.stat().st_mtime > start_time)

        start_time = time.time() - 1
        return jobs.start(self.meta.id, f"pixelfx: {', '.join(effects)}", plan, outputs, notes=[
            "contact.png files are contact sheets: look at them (contact_sheet / your image tool) before using an effect.",
        ])
