"""How-to videos of a web app: step files are played in headless Chrome, then rendered with Remotion."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import config, jobs
from .base import Engine, EngineError


class HowTo(Engine):
    def installed(self) -> tuple[bool, str]:
        src = self.meta.source
        if not (src / "node_modules" / "playwright").exists() or not (src / "render" / "node_modules" / "remotion").exists():
            return False, "dependencies not installed: call setup_engine('howto')"
        return True, ""

    def setup(self) -> jobs.Job:
        npm = config.npm()
        if not npm:
            raise EngineError("npm (Node.js 20+) is needed")
        src = self.meta.source
        return jobs.start(self.meta.id, "install how-to kit", [
            jobs.Step("npm ci (recorder)", [npm, "ci", "--no-audit", "--no-fund"], cwd=str(src)),
            jobs.Step("npm ci (renderer)", [npm, "ci", "--no-audit", "--no-fund"], cwd=str(src / "render")),
        ])

    def scaffold(self, project_dir: Path, style: str, options: dict) -> dict:
        """Create a folder of step files for one app: config, one example step file to copy, packet.json."""
        ex = self.meta.source / "example" / "howto"
        project_dir.mkdir(parents=True, exist_ok=True)
        made = []
        for name, target in (("howto.config.mjs", "howto.config.mjs"), ("find-a-customer.json", "example-step.json")):
            dst = project_dir / target
            if not dst.exists():
                shutil.copyfile(ex / name, dst)
                made.append(str(dst))
        packet = project_dir / "packet.json"
        if not packet.exists():
            app = options.get("app") or "My App"
            packet.write_text(json.dumps({
                "project": app, "tagline": "How-to videos and written steps",
                "groups": [{"name": app, "dir": ".", "videos": []}],
            }, indent=2) + "\n")
            made.append(str(packet))
        return {
            "project_dir": str(project_dir), "created": made,
            "next": [
                "Edit howto.config.mjs: app name, baseUrl of the app (it must be running), viewport, hideCss.",
                "Read get_guide('howto', 'steps'), then write one step file per task (copy example-step.json).",
                "Delete example-step.json, list your slugs in packet.json, then call render('howto', project_dir).",
            ],
        }

    def render(self, project_dir: Path | None, options: dict) -> jobs.Job:
        ok, missing = self.installed()
        if not ok:
            raise EngineError(missing)
        if project_dir is None or not (project_dir / "howto.config.mjs").exists():
            raise EngineError("project_dir must be a folder with howto.config.mjs (see scaffold('howto', ...))")
        steps = options.get("steps") or sorted(
            p.name for p in project_dir.glob("*.json") if p.name not in ("packet.json",) and not p.name.startswith("."))
        files = [project_dir / s for s in steps]
        for f in files:
            if not f.exists():
                raise EngineError(f"step file not found: {f}")
        if not files:
            raise EngineError(f"no step files (*.json) in {project_dir}")
        slugs = [json.loads(f.read_text()).get("slug") or f.stem for f in files]
        src, node = self.meta.source, config.node()
        if not node:
            raise EngineError("node (Node.js 20+) is needed")
        env = {"HOWTO_BROWSER": config.chrome(headless_shell=True) or ""}
        if options.get("base_url"):
            env["HOWTO_BASE"] = options["base_url"]
        captures = ",".join(str(project_dir / "out" / s / "capture") for s in slugs)
        plan = [
            jobs.Step("record in headless Chrome", [node, str(src / "record.mjs"), *map(str, files)], cwd=str(src), env=env),
            jobs.Step("render with Remotion", [config.python(), str(src / "render_local.py"), "--captures", captures],
                      cwd=str(src), env=env),
        ]
        packet = project_dir / "packet.json"
        notes = [
            "The app must be running at the config's baseUrl. Exit code 2 = a step target was not found "
            "(a failed-step-<n>.png is saved beside the capture); exit code 3 = a step tried to write data.",
            "Review stills are in out/<slug>/review/: check every caption against them before sharing.",
        ]
        if options.get("packet", True) and packet.exists():
            listed = _packet_slugs(json.loads(packet.read_text()), project_dir)
            missing = [s for s, d in listed if s not in slugs and not (d / "out" / s / "web" / "howto.json").exists()]
            if not listed:
                notes.append("Help page skipped: packet.json lists no videos yet. Add the slugs to build it.")
            elif missing:
                notes.append(f"Help page skipped: packet.json lists videos that are not rendered: {missing}.")
            else:
                plan.append(jobs.Step("build help page", [node, str(src / "build_packet.mjs"), str(packet)],
                                      cwd=str(src)))

        def outputs() -> list[str]:
            out = [str(project_dir / "out" / s / f"{s}.mp4") for s in slugs]
            if (project_dir / "out" / "packet" / "index.html").exists():
                out.append(str(project_dir / "out" / "packet" / "index.html"))
            return [o for o in out if Path(o).exists()]

        return jobs.start(self.meta.id, f"how-to videos: {', '.join(slugs)}", plan, outputs, notes=notes)


def _packet_slugs(node: dict, base: Path, inherited: str = ".") -> list[tuple[str, Path]]:
    """Every (slug, folder) a packet.json lists; `dir` is inherited by child groups, as build_packet.mjs does."""
    out: list[tuple[str, Path]] = []
    for g in node.get("groups", []):
        d = g.get("dir", inherited)
        for v in g.get("videos", []):
            out.append((v if isinstance(v, str) else v["slug"], (base / d).resolve()))
        out += _packet_slugs(g, base, d)
    return out
