# videokit

One MCP server that lets any AI chat make videos with several code-to-video engines. The AI writes the
animation as code, an engine renders it in headless Chrome, and ffmpeg encodes the MP4. Rendering runs in the
background; the AI checks on it and looks at a contact sheet of the result before it calls the video done.

> Status: step 2 of 3. Engines: **lemo-opuscar** (99 film styles), **video-shotcraft** (product promos),
> **claude-animation-base** (character animation), **howto** (app tutorials), **pixelfx** (pixel art effects).
> Plus prompt search, narration, beat detection, mixing, sound effects, image generation and credits.
> Packaging as a Claude Code plugin comes next.

## Layout

| Path | What |
|---|---|
| `server/` | The MCP server (Python). Engine tools: `check_environment`, `list_engines`, `get_guide`, `list_styles`, `setup_engine`, `scaffold`, `render`, `job_status`, `list_jobs`, `look`. Media tools: `narrate`, `beats`, `mux_audio`, `sound_effects`, `generate_image`, `write_credits`. Ideas: `search_prompts`, `get_prompt` |
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
`VIDEOKIT_HOME` (jobs and caches, default `~/.videokit`), `VIDEOKIT_FFMPEG_DIR`, `VIDEOKIT_CHROME`,
`GEMINI_API_KEY` (for `generate_image`; not needed where a network proxy injects it).

First use of an engine: `setup_engine('lemo-opuscar')` installs its packages; the other engines install on their
first render. `narrate` downloads the Kokoro voice model (about 350 MB) on first use.

## Test

```bash
cd server && uv run pytest -q
```

The tests connect a real MCP client to the server and render real videos (about a minute).
