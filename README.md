# videokit

One MCP server that lets any AI chat make videos with several code-to-video engines. The AI writes the
animation as code, an engine renders it in headless Chrome, and ffmpeg encodes the MP4. Rendering runs in the
background; the AI checks on it and looks at a contact sheet of the result before it calls the video done.

> Status: step 1 of 3. Working engines: **howto** (app tutorials) and **pixelfx** (pixel art effects).
> lemo-opuscar, video-shotcraft, ClaudeAnimationBase, prompt search, beat detection and narration come next.

## Layout

| Path | What |
|---|---|
| `server/` | The MCP server (Python). Tools: `check_environment`, `list_engines`, `get_guide`, `list_styles`, `setup_engine`, `scaffold`, `render`, `job_status`, `list_jobs`, `look` |
| `engines/<id>/engine.yaml` | Each engine's description, guides, requirements and license terms |
| `engines/howto/` | The How-to Video Kit itself |
| `vendor/` | Upstream engines as pinned git submodules (their code and licenses stay theirs) |
| `docs/LICENSING.md` | What may be used for monetized videos and inside a service |

## Run it

Needs Node 20+, Python 3.10+, [uv](https://docs.astral.sh/uv/), ffmpeg 7+ and Chrome or Chromium.

```bash
git clone --recurse-submodules --shallow-submodules <this repo>
cd videokit/server && uv sync
```

Add it to an MCP client (Claude Code shown; other clients take the same command):

```bash
claude mcp add videokit -- uv run --quiet --directory /path/to/videokit/server videokit-mcp
```

Settings (environment variables): `VIDEOKIT_MODE` (`personal` or `service`, see `docs/LICENSING.md`),
`VIDEOKIT_HOME` (jobs and caches, default `~/.videokit`), `VIDEOKIT_FFMPEG_DIR`, `VIDEOKIT_CHROME`.

## Test

```bash
cd server && uv run pytest -q
```

The tests connect a real MCP client to the server and render real videos (about a minute).
