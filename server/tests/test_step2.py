"""Step 2: the lemo-opuscar, video-shotcraft and claude-animation-base engines, prompts, sound and images.
Real renders and real downloads: the first run takes several minutes (Kokoro model ~350 MB, npm installs)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from mcp import Client

from videokit_mcp import config, vendor
from videokit_mcp.server import mcp

from test_server import data, wait

pytestmark = pytest.mark.anyio

TINY_FILM = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#111}</style>
</head><body><canvas id="c" width="1920" height="1080"></canvas><script>
const c = document.getElementById('c').getContext('2d');
window.DUR = 2;
window.render = (t) => {
  c.fillStyle = '#123'; c.fillRect(0, 0, 1920, 1080);
  c.fillStyle = '#f5a'; c.beginPath(); c.arc(200 + t * 700, 540, 120, 0, 7); c.fill();
  c.fillStyle = '#fff'; c.font = '80px sans-serif'; c.fillText('videokit test ' + t.toFixed(2), 120, 160);
};
window.TEXTS = (t) => [{id: 'title', text: 'videokit test', x0: 120, y0: 90, x1: 900, y1: 180, pass: true}];
window.READY = true;
</script></body></html>"""


@pytest.fixture
def anyio_backend():
    return "asyncio"


def tone(path: Path, seconds: float = 2.0) -> Path:
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", "-ar", "48000", str(path)], check=True)
    return path


async def test_all_engines_listed():
    async with Client(mcp) as c:
        ids = {e["id"] for e in data(await c.call_tool("list_engines", {}))}
        assert ids == {"howto", "pixelfx", "lemo-opuscar", "video-shotcraft", "claude-animation-base"}


async def test_service_mode_blocks_personal_material(monkeypatch):
    monkeypatch.setenv("VIDEOKIT_MODE", "service")
    async with Client(mcp) as c:
        ids = {e["id"] for e in data(await c.call_tool("list_engines", {}))}
        assert "lemo-opuscar" not in ids and "video-shotcraft" in ids
        for tool, args in (("get_guide", {"engine": "lemo-opuscar"}), ("search_prompts", {"query": "x"}),
                           ("render", {"engine": "lemo-opuscar", "project_dir": "/tmp/x"})):
            r = await c.call_tool(tool, args)
            assert r.is_error and "personal use only" in r.content[0].text, tool


async def test_lemo_film_end_to_end(tmp_path: Path):
    film = tmp_path / "test-film"
    async with Client(mcp) as c:
        styles = data(await c.call_tool("list_styles", {"engine": "lemo-opuscar", "query": "chalkboard"}))
        assert styles["items"][0]["slug"] == "chalkboard"
        g = data(await c.call_tool("get_guide", {"engine": "lemo-opuscar", "topic": "style/chalkboard",
                                                  "max_chars": 200}))
        assert g["total_chars"] > 1000
        s = data(await c.call_tool("scaffold", {"engine": "lemo-opuscar", "project_dir": str(film),
                                                "style": "chalkboard"}))
        assert s["lib"].endswith("vendor/lemo-opuscar") and not s["needs_image_generator"]
        (film / "index.html").write_text(TINY_FILM)
        st = await wait(c, data(await c.call_tool("render", {"engine": "lemo-opuscar", "project_dir": str(film),
                                                             "options": {"action": "stills", "times": [0.5, 1.5]}}))["id"])
        assert st["status"] == "succeeded" and len(st["outputs"]) == 2, st
        v = await wait(c, data(await c.call_tool("render", {"engine": "lemo-opuscar", "project_dir": str(film),
                                                            "options": {"action": "video", "workers": 2}}))["id"])
        assert v["status"] == "succeeded", v
        rc = await wait(c, data(await c.call_tool("render", {"engine": "lemo-opuscar", "project_dir": str(film),
                                                             "options": {"action": "readcheck"}}))["id"])
        assert rc["status"] == "succeeded", rc
        tone(film / "mix.wav")
        m = await wait(c, data(await c.call_tool("render", {"engine": "lemo-opuscar", "project_dir": str(film),
                                                            "options": {"action": "mux"}}))["id"])
        assert m["status"] == "succeeded", m
        info = (await c.call_tool("look", {"path": m["outputs"][0], "frames": 4})).content
        meta = json.loads(next(x.text for x in info if x.type == "text"))
        assert meta["has_audio"] and abs(meta["seconds"] - 2) < 0.2


async def test_shotcraft_scaffold_and_render(tmp_path: Path):
    proj = tmp_path / "promo"
    async with Client(mcp) as c:
        cards = data(await c.call_tool("list_styles", {"engine": "video-shotcraft", "query": "logo"}))
        assert cards["count"] > 0
        name = cards["items"][0]["name"]
        assert len(data(await c.call_tool("get_guide", {"engine": "video-shotcraft", "topic": f"style/{name}",
                                                        "max_chars": 100}))["text"]) == 100
        s = data(await c.call_tool("scaffold", {"engine": "video-shotcraft", "project_dir": str(proj)}))
        assert "bgm-tech-house.mp3" not in s["bgm_choices"] and "warning" in s
        job = data(await c.call_tool("render", {"engine": "video-shotcraft", "project_dir": str(proj),
                                                "options": {"frames": "0-44"}}))
        r = await wait(c, job["id"], timeout=1200)
        assert r["status"] == "succeeded", r
        assert any("Unverified" in n for n in r["notes"])


async def test_animation_scaffold_and_short_render(tmp_path: Path):
    proj = tmp_path / "anim"
    async with Client(mcp) as c:
        s = data(await c.call_tool("scaffold", {"engine": "claude-animation-base", "project_dir": str(proj)}))
        assert s["fonts_made_local"] == ["Permanent Marker"], s
        assert "fonts.googleapis.com" not in (proj / "studio.html").read_text()
        job = data(await c.call_tool("render", {"engine": "claude-animation-base", "project_dir": str(proj),
                                                "options": {"range": "0:0.25"}}))
        r = await wait(c, job["id"], timeout=1500)
        assert r["status"] == "succeeded", r
        assert r["outputs"] and r["outputs"][0].endswith("video.mp4")


async def test_prompts():
    async with Client(mcp) as c:
        res = data(await c.call_tool("search_prompts", {"query": "recipe", "category": "explainer"}))
        assert res["count"] > 0 and not res["problems"], res["problems"]
        full = data(await c.call_tool("get_prompt", {"prompt_id": res["results"][0]["id"]}))
        assert len(full["prompt"]) > 20 and full["use_note"]
        cn = data(await c.call_tool("search_prompts", {"source": "opus-cn", "limit": 50}))
        assert cn["count"] >= 18


async def test_sound_tools(tmp_path: Path):
    bgm = vendor.path("video-shotcraft") / "assets" / "audio" / "bgm" / "cat-walk.mp3"
    async with Client(mcp) as c:
        b = data(await c.call_tool("beats", {"audio_path": str(bgm)}))
        assert 125 < b["tempo_bpm"] < 133 and b["beat_count"] > 50
        job = data(await c.call_tool("narrate", {"out_dir": str(tmp_path / "vo"), "lines": [
            {"id": "1", "text": "This video was made entirely in code."},
            {"id": "2", "text": "Every frame is drawn by a program.", "voice": "bm_george", "lang": "en-gb"}]}))
        n = await wait(c, job["id"], timeout=1500)
        assert n["status"] == "succeeded", n
        durations = json.loads((tmp_path / "vo" / "durations.json").read_text())
        assert len(durations) == 2 and all(d > 1 for d in durations.values())
        video = tmp_path / "v.mp4"
        subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=6",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
        out = data(await c.call_tool("mux_audio", {"video": str(video), "out": str(tmp_path / "final.mp4"), "tracks": [
            {"path": str(tmp_path / "vo" / "001.wav"), "start": 0.5},
            {"path": str(bgm), "volume": 0.2}]}))
        assert abs(out["seconds"] - 6) < 0.1
        cr = data(await c.call_tool("write_credits", {"project_dir": str(tmp_path), "items": [
            {"what": "music", "title": "Cat Walk", "author": "Arulo", "license": "Mixkit Stock Music Free License"}]}))
        assert (tmp_path / "CREDITS.md").exists() and "Cat Walk" in (tmp_path / "CREDITS.md").read_text()


async def test_sound_effects_search_reports_clearly():
    """Freesound may refuse cloud networks: either it works or the error says what to do."""
    async with Client(mcp) as c:
        r = await c.call_tool("sound_effects", {"action": "search", "query": "soft whoosh", "max_duration": 2})
        if r.is_error:
            assert "Freesound" in r.content[0].text or "freesound" in r.content[0].text
        else:
            assert data(r)["action"] == "search"


async def test_generate_image(tmp_path: Path):
    async with Client(mcp) as c:
        r = await c.call_tool("generate_image", {"prompt": "A flat vector icon of a film clapperboard, orange on cream",
                                                 "out_dir": str(tmp_path), "name": "icon", "aspect": "1:1"})
        assert not r.is_error, r.content[0].text
        assert any(x.type == "image" for x in r.content) and list(tmp_path.glob("icon_*"))
