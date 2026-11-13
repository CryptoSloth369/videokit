"""video-shotcraft: product promos with Remotion from real page captures and 124 shot cards."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .. import config, jobs
from .base import Engine, EngineError

UNVERIFIED_SFX = ("keyboard.mp3", "riser-cine.mp3", "sparkle.mp3", "whoosh-big.mp3", "pop.mp3")
BANNED_BGM = ("bgm-tech-house.mp3",)
_CARD = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class Shotcraft(Engine):
    has_style_guides = True

    def _cards(self) -> list[dict]:
        lib = json.loads((self.meta.source / "gallery" / "api" / "library.json").read_text(encoding="utf-8"))
        return [{"name": c["name"], "summary": c.get("summary"), "use": c.get("use"), "duration": c.get("duration"),
                 "energy": c.get("energy"), "styles": [s.get("key") for s in c.get("styles", [])],
                 "doc": c.get("source")} for c in lib["cards"]]

    def styles(self, query: str) -> list[dict]:
        words = [w.lower() for w in query.split()]
        cards = self._cards()
        if not words:
            return cards
        scored = [(sum(w in json.dumps(c, ensure_ascii=False).lower() for w in words), c) for c in cards]
        return [c for n, c in sorted(scored, key=lambda x: -x[0]) if n]

    def style_guide(self, slug: str) -> str:
        card = next((c for c in self._cards() if c["name"] == slug), None) if _CARD.match(slug) else None
        if not card or not card["doc"]:
            raise EngineError(f"no shot card {slug!r}; search with list_styles('video-shotcraft', '<words>')")
        return (self.meta.source / card["doc"]).read_text(encoding="utf-8")

    def scaffold(self, project_dir: Path, style: str, options: dict) -> dict:
        if project_dir.exists() and any(project_dir.iterdir()):
            raise EngineError(f"{project_dir} is not empty; give a new folder for the promo project")
        src = self.meta.source
        shutil.copytree(src / "template", project_dir, ignore=shutil.ignore_patterns("node_modules", "out"))
        (project_dir / "scripts").mkdir(exist_ok=True)
        shutil.copyfile(src / "assets" / "scripts" / "capture-template.mjs", project_dir / "scripts" / "capture-template.mjs")
        (project_dir / "VIDEOKIT.json").write_text(json.dumps(
            {"engine": "video-shotcraft", "lib": str(src), "unverified_template_sfx": list(UNVERIFIED_SFX)},
            indent=2) + "\n")
        return {
            "project_dir": str(project_dir), "lib": str(src),
            "bgm_choices": sorted(p.name for p in (src / "assets" / "audio" / "bgm").glob("*.mp3")
                                  if p.name not in BANNED_BGM),
            "next": [
                "Read get_guide('video-shotcraft', 'videokit'), then 'skill', and pick a mode with the user.",
                "Capture the product's pages with scripts/capture-template.mjs (demo data only).",
                "render('video-shotcraft', project_dir) renders the composition; look() at the result.",
            ],
            "warning": "Replace the template's unverified sound effects before monetizing: " + ", ".join(UNVERIFIED_SFX),
        }

    def render(self, project_dir: Path | None, options: dict) -> jobs.Job:
        if project_dir is None or not (project_dir / "package.json").exists():
            raise EngineError("project_dir must be a promo project made by scaffold('video-shotcraft', ...)")
        npm, node = config.npm(), config.node()
        if not npm or not node:
            raise EngineError("Node.js 20+ with npm is needed")
        pkg = json.loads((project_dir / "package.json").read_text())
        comp = options.get("composition")
        if not comp:
            m = re.search(r"remotion render \S+ (\S+)", pkg.get("scripts", {}).get("render", ""))
            comp = m.group(1) if m else None
        if not comp or not re.match(r"^[A-Za-z0-9_-]+$", comp):
            raise EngineError("give options.composition (the <Composition id> in src/Root.tsx)")
        out = project_dir / "out" / options.get("name", f"{comp}.mp4")
        browser = config.chrome(headless_shell=True)
        argv = [str(project_dir / "node_modules" / ".bin" / "remotion"), "render", "src/index.ts", comp, str(out),
                f"--concurrency={options.get('concurrency', max(1, (_cpus() or 2)))}"]
        if browser:
            argv.append(f"--browser-executable={browser}")
        if options.get("props"):
            props = project_dir / "out" / "props.json"
            props.parent.mkdir(parents=True, exist_ok=True)
            props.write_text(json.dumps(options["props"]))
            argv.append(f"--props={props}")
        if options.get("frames"):
            argv.append(f"--frames={options['frames']}")
        plan = []
        if not (project_dir / "node_modules" / "remotion").exists():
            plan.append(jobs.Step("npm ci", [npm, "ci", "--no-audit", "--no-fund"], cwd=str(project_dir)))
        plan.append(jobs.Step(f"remotion render {comp}", argv, cwd=str(project_dir)))
        notes = []
        left = [n for n in UNVERIFIED_SFX if (project_dir / "public" / "audio" / n).exists()]
        if left:
            notes.append("Unverified template sound effects still in public/audio (replace before monetizing): "
                         + ", ".join(left))
        return jobs.start(self.meta.id, f"shotcraft render {comp}", plan,
                          lambda: [str(out)] if out.exists() else [], notes=notes)


def _cpus() -> int | None:
    import os
    return os.cpu_count()
