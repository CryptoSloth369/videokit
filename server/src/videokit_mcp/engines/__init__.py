"""Engine registry. Each engine has engines/<id>/engine.yaml (metadata + license) and, when it can render, an
adapter class here. VIDEOKIT_MODE=service hides every engine whose license says personal_only."""

from __future__ import annotations

from functools import cache

from .. import config
from .base import Engine, EngineError, Meta
from .animation import Animation
from .howto import HowTo
from .lemo import Lemo
from .pixelfx import PixelFX
from .shotcraft import Shotcraft

ADAPTERS: dict[str, type[Engine]] = {"howto": HowTo, "pixelfx": PixelFX, "lemo-opuscar": Lemo,
                                      "video-shotcraft": Shotcraft, "claude-animation-base": Animation}


@cache
def _all() -> dict[str, Engine]:
    found: dict[str, Engine] = {}
    for y in sorted(config.ENGINES_DIR.glob("*/engine.yaml")):
        meta = Meta.load(y)
        cls = ADAPTERS.get(meta.id)
        if cls:
            found[meta.id] = cls(meta)
    return found


def allowed(e: Engine) -> bool:
    return config.mode() == "personal" or e.meta.license.service_mode == "allowed"


def available() -> list[Engine]:
    return [e for e in _all().values() if allowed(e)]


def get(engine_id: str) -> Engine:
    e = _all().get(engine_id)
    if e is None:
        raise EngineError(f"unknown engine {engine_id!r}; engines: {[x.meta.id for x in available()]}")
    if not allowed(e):
        raise EngineError(f"{engine_id} is for personal use only and is turned off in service mode "
                          f"(license: {e.meta.license.docs}). See docs/LICENSING.md.")
    return e


__all__ = ["Engine", "EngineError", "available", "get"]
