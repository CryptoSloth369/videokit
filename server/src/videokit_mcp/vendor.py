"""Upstream repos the engines use. In a git checkout they are submodules under vendor/. A plugin install copies the
repo without submodules, so then each one is fetched at the exact commit in vendor.lock.json into
~/.videokit/vendor/<name> the first time it is needed."""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import cache
from pathlib import Path

from . import config


@cache
def lock() -> dict[str, dict]:
    return json.loads((config.REPO / "vendor.lock.json").read_text())


def path(name: str) -> Path:
    """Where `name` lives: the submodule if it is checked out, else the per-user copy (fetched or not)."""
    sub = config.VENDOR_DIR / name
    if sub.is_dir() and any(p.name != ".git" for p in sub.iterdir()):
        return sub
    return config.HOME / "vendor" / name


def present(name: str) -> bool:
    p = path(name)
    return p.is_dir() and any(p.iterdir())


def fetch_argv(name: str) -> list[list[str]]:
    """Commands that fetch `name` at its pinned commit into ~/.videokit/vendor/<name> (shallow, one commit)."""
    entry = lock()[name]
    dest = config.HOME / "vendor" / name
    git = shutil.which("git") or "git"
    return [
        [git, "init", "-q", str(dest)],
        [git, "-C", str(dest), "fetch", "-q", "--depth", "1", entry["url"], entry["commit"]],
        [git, "-C", str(dest), "checkout", "-q", "FETCH_HEAD"],
    ]


def fetch_now(name: str, timeout: int = 300) -> Path:
    if present(name):
        return path(name)
    dest = config.HOME / "vendor" / name
    shutil.rmtree(dest, ignore_errors=True)
    for argv in fetch_argv(name):
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"could not fetch {name}: {r.stderr.strip()[:300]}")
    return dest
