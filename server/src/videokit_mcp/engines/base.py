"""What every engine adapter provides, and the license metadata read from engines/<id>/engine.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from mcp.server.mcpserver.exceptions import ToolError

from .. import config, jobs


class EngineError(ToolError):
    """A problem the AI should read and fix (bad argument, missing setup). Shown to it as the tool error."""


@dataclass
class License:
    code: str
    docs: str
    monetized_videos: bool          # may videos made with it be monetized (YouTube etc.)
    service_mode: str               # "allowed" or "personal_only" (hidden when VIDEOKIT_MODE=service)
    notes: list[str] = field(default_factory=list)


@dataclass
class Meta:
    id: str
    name: str
    summary: str
    good_for: list[str]
    source: Path                    # where the engine's own files live
    upstream: str
    license: License
    requires: list[str]
    guides: dict[str, str]          # topic -> path relative to source
    gpu_note: str = ""

    @classmethod
    def load(cls, yaml_path: Path) -> "Meta":
        d: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
        lic = d["license"]
        return cls(
            id=d["id"], name=d["name"], summary=d["summary"].strip(), good_for=d.get("good_for", []),
            source=(config.REPO / d["source"]).resolve(), upstream=d.get("upstream", ""),
            license=License(code=lic["code"], docs=lic.get("docs", lic["code"]),
                            monetized_videos=bool(lic["monetized_videos"]), service_mode=lic["service_mode"],
                            notes=lic.get("notes", [])),
            requires=d.get("requires", []), guides=d.get("guides", {}), gpu_note=d.get("gpu_note", ""),
        )


class Engine:
    """Subclasses implement the parts that differ. Paths given by the AI are resolved against the server's cwd."""

    meta: Meta

    def __init__(self, meta: Meta):
        self.meta = meta

    # -- discovery ---------------------------------------------------------------------------------------------
    def installed(self) -> tuple[bool, str]:
        """(ready, what is missing)."""
        if not self.meta.source.exists() or not any(self.meta.source.iterdir()):
            return False, f"{self.meta.source} is empty: run `git submodule update --init` in the videokit repo"
        return True, ""

    def guide(self, topic: str) -> str:
        if not topic:
            topic = next(iter(self.meta.guides))
        if topic.startswith("style/"):
            return self.style_guide(topic.removeprefix("style/"))
        if topic not in self.meta.guides:
            raise EngineError(f"unknown guide {topic!r} for {self.meta.id}; topics: {list(self.meta.guides)}"
                              + (" or style/<slug>" if self.has_style_guides else ""))
        rel = self.meta.guides[topic]
        # "@/x" is relative to the videokit repo (adapter notes); anything else to the engine's own source
        path = config.REPO / rel[2:] if rel.startswith("@/") else self.meta.source / rel
        return path.read_text(encoding="utf-8")

    has_style_guides = False

    def style_guide(self, slug: str) -> str:
        raise EngineError(f"{self.meta.id} has no per-style guides")

    def styles(self, query: str) -> list[dict]:
        return []

    # -- actions -----------------------------------------------------------------------------------------------
    def setup(self) -> jobs.Job:
        raise EngineError(f"{self.meta.id} needs no setup")

    def scaffold(self, project_dir: Path, style: str, options: dict) -> dict:
        raise EngineError(f"{self.meta.id} has no project template")

    def render(self, project_dir: Path | None, options: dict) -> jobs.Job:
        raise NotImplementedError

    # -- helpers -----------------------------------------------------------------------------------------------
    def info(self) -> dict:
        ok, missing = self.installed()
        m = self.meta
        return {
            "id": m.id, "name": m.name, "summary": m.summary, "good_for": m.good_for,
            "ready": ok, "missing": missing, "guides": list(m.guides), "requires": m.requires,
            "gpu_note": m.gpu_note, "upstream": m.upstream,
            "license": {"code": m.license.code, "docs": m.license.docs,
                        "monetized_videos": m.license.monetized_videos,
                        "service_mode": m.license.service_mode, "notes": m.license.notes},
        }
