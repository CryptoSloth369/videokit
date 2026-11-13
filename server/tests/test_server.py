"""End-to-end: a real MCP client talks to the server in-process and renders real videos.
Run from server/:  uv run pytest -q          (the howto test starts the example app itself)"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import anyio
import pytest
from mcp import Client

from videokit_mcp import config, engines
from videokit_mcp.server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def data(result) -> object:
    """The tool's return value: structured content, or the JSON text block(s)."""
    assert not result.is_error, result.content[0].text if result.content else result
    texts = [c.text for c in result.content if c.type == "text"]
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
    return [json.loads(t) for t in texts] if len(texts) > 1 else json.loads(texts[0])


async def wait(client: Client, job_id: str, timeout: float = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = data(await client.call_tool("job_status", {"job_id": job_id, "log_lines": 40}))
        if s["status"] not in ("queued", "running"):
            return s
        await anyio.sleep(2)
    raise TimeoutError(job_id)


async def test_discovery():
    async with Client(mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert {"list_engines", "get_guide", "list_styles", "scaffold", "render", "job_status", "look"} <= names
        env = data(await c.call_tool("check_environment", {}))
        assert env["mode"] == "personal" and env["node"] and env["chrome"]
        eng = {e["id"]: e for e in data(await c.call_tool("list_engines", {}))}
        assert {"howto", "pixelfx"} <= set(eng)
        g = data(await c.call_tool("get_guide", {"engine": "howto", "topic": "steps", "max_chars": 500}))
        assert len(g["text"]) == 500 and g["next_offset"] == 500
        fx = data(await c.call_tool("list_styles", {"engine": "pixelfx", "query": "campfire"}))
        assert any(i["id"] == "fire/campfire" for i in fx["items"])


async def test_errors_are_readable():
    async with Client(mcp) as c:
        r = await c.call_tool("get_guide", {"engine": "nope"})
        assert r.is_error and "unknown engine" in r.content[0].text
        r = await c.call_tool("render", {"engine": "pixelfx", "options": {}})
        assert r.is_error and "effects is required" in r.content[0].text


async def test_pixelfx_render_and_look(tmp_path: Path):
    async with Client(mcp) as c:
        job = data(await c.call_tool("render", {"engine": "pixelfx", "project_dir": str(tmp_path),
                                                "options": {"effects": ["fire/campfire"], "scale": 4}}))
        s = await wait(c, job["id"])
        assert s["status"] == "succeeded", s
        mp4 = [o for o in s["outputs"] if o.endswith(".mp4")]
        assert mp4
        r = await c.call_tool("look", {"path": mp4[0], "frames": 4})
        assert not r.is_error and any(x.type == "image" for x in r.content)


async def test_pixelfx_scaffold_workspace(tmp_path: Path):
    ws = tmp_path / "fx"
    async with Client(mcp) as c:
        out = data(await c.call_tool("scaffold", {"engine": "pixelfx", "project_dir": str(ws)}))
        assert (ws / "tools" / "render.mjs").exists() and (ws / "src" / "fx").is_dir()
        assert out["project_dir"] == str(ws)


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


async def test_howto_example(tmp_path: Path):
    """Scaffold a project, point it at the kit's example app, render one tutorial and the help page."""
    src = config.REPO / "engines" / "howto"
    assert _port_free(4173), "port 4173 busy"
    app = subprocess.Popen([config.node(), str(src / "example" / "serve.mjs")], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    try:
        async with Client(mcp) as c:
            data(await c.call_tool("scaffold", {"engine": "howto", "project_dir": str(tmp_path)}))
            # the example step file already targets the example app; give it its real slug
            (tmp_path / "example-step.json").rename(tmp_path / "find-a-customer.json")
            packet = json.loads((tmp_path / "packet.json").read_text())
            packet["groups"][0]["videos"] = [{"slug": "find-a-customer", "keywords": "search"}]
            (tmp_path / "packet.json").write_text(json.dumps(packet))
            job = data(await c.call_tool("render", {"engine": "howto", "project_dir": str(tmp_path)}))
            s = await wait(c, job["id"])
            assert s["status"] == "succeeded", s
            assert any(o.endswith("find-a-customer.mp4") for o in s["outputs"])
            assert any(o.endswith("index.html") for o in s["outputs"])
    finally:
        app.terminate()


async def test_service_mode_hides_personal_only(monkeypatch):
    monkeypatch.setenv("VIDEOKIT_MODE", "service")
    personal = [e for e in engines._all().values() if e.meta.license.service_mode == "personal_only"]
    async with Client(mcp) as c:
        ids = {e["id"] for e in data(await c.call_tool("list_engines", {}))}
        assert not ids & {e.meta.id for e in personal}
        for e in personal:
            r = await c.call_tool("get_guide", {"engine": e.meta.id})
            assert r.is_error and "personal use only" in r.content[0].text


def test_vendor_lock_matches_submodules():
    """vendor.lock.json (used by plugin installs) must pin the same commits as the git submodules."""
    from videokit_mcp import vendor
    r = subprocess.run(["git", "submodule", "status"], cwd=config.REPO, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        pytest.skip("not a git checkout with submodules")
    pins = {Path(p).name: c.lstrip("-+ U") for c, p, *_ in (line.split() for line in r.stdout.splitlines())}
    assert {k: v["commit"] for k, v in vendor.lock().items()} == pins
