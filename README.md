# videokit

One MCP server that lets an AI chat make videos with five code-to-video engines. The AI writes the animation as
code, an engine renders it in headless Chrome, and ffmpeg encodes the MP4. Renders run in the background; the AI
checks on them and looks at a contact sheet of the result before it calls a video done.

| Engine | Makes |
|---|---|
| **lemo-opuscar** | Short narrated films in 99 styles: explainers, stories, launches, music videos |
| **video-shotcraft** | Cinematic product promos from screenshots of a real web app |
| **claude-animation-base** | Hand-drawn character animation |
| **howto** | Tutorials of a web app, with cursor, step captions and a help page |
| **pixelfx** | Pixel art effects, acted-out clips and sprite sheets |

Plus `narrate` (offline voice), `beats` (cut to music), `sound_effects` (licensed SFX), `mux_audio` (mix and
master to -14 LUFS), `generate_image` (Gemini), `write_credits` (for the video description), and `search_prompts`
(~770 prompts that made good code-made videos). What may be used for monetized videos, and inside a service for
other people, is in [docs/LICENSING.md](docs/LICENSING.md).

## What you need

| | |
|---|---|
| Node.js 20+ | Every engine renders with it |
| Python 3.11+ and [uv](https://docs.astral.sh/uv/) | Runs the server |
| ffmpeg 7+ (with ffprobe) | macOS: `brew install ffmpeg`. Windows: `winget install Gyan.FFmpeg`. Ubuntu 24.04 ships 6.1: use a static build and set `VIDEOKIT_FFMPEG_DIR` to its folder |
| Chrome or Chromium | Found automatically; set `VIDEOKIT_CHROME` if not |
| git | Downloads the upstream engines on first use |
| A GPU (optional) | Any built-in GPU is enough. Without one, 3D, shader and watercolour styles are slow |

Developed and tested on Linux. macOS should work as is; on Windows, lemo-opuscar's scripts need Git Bash.

## Install

### Claude Code (plugin)

```text
/plugin marketplace add CryptoSloth369/videokit
```

```text
/plugin install videokit@videokit
```

The repository is private, so the machine needs git access to it (the same access you use to clone it). Restart
Claude Code, then ask for a video. The plugin adds the MCP server and a `videokit` skill that tells Claude when
and how to use it.

### Any other MCP client (Claude Desktop, Cursor, VS Code, Windsurf, ...)

```bash
git clone --recurse-submodules --shallow-submodules https://github.com/CryptoSloth369/videokit.git
```

```bash
cd videokit/server && uv sync
```

Then add the server to the client's MCP settings (the file and key differ by client; the command is the same):

```json
{
  "mcpServers": {
    "videokit": {
      "command": "uv",
      "args": ["run", "--quiet", "--directory", "/absolute/path/to/videokit/server", "videokit-mcp"],
      "env": { "VIDEOKIT_MODE": "personal" }
    }
  }
}
```

For Claude Code without the plugin:

```bash
claude mcp add videokit -- uv run --quiet --directory /absolute/path/to/videokit/server videokit-mcp
```

The engines' guides were written for Claude and give the best results with it; other models can use every tool.

### Claude Code on the web (cloud sessions)

The repository's `.mcp.json` registers the server when a session opens this repository; approve `videokit`
once when Claude Code asks (a repository cannot pre-approve its own servers). To use videokit from chats on
another repository, see [docs/USE-IN-ANOTHER-REPO.md](docs/USE-IN-ANOTHER-REPO.md). The environment's
setup script should run `bash videokit/scripts/cloud-setup.sh` (it installs the server, the engines' packages and
ffmpeg 8.1), guarded so a branch without the script still starts:
`if [ -f videokit/scripts/cloud-setup.sh ]; then bash videokit/scripts/cloud-setup.sh; fi`. The "Mystic Sloth"
environment already has this. Freesound refuses requests from
cloud networks, so `sound_effects` works only from your own computer; everything else works in the cloud.

## First use

- `check_environment` shows what was found and what is missing.
- `setup_engine('<engine>')` downloads an engine at its pinned commit (when it is not a git submodule here) and,
  for lemo-opuscar, installs its packages. The other engines install their packages on their first render.
- `narrate` downloads the Kokoro voice model (about 350 MB) on its first use.

## Settings

| Variable | Default | |
|---|---|---|
| `VIDEOKIT_MODE` | `personal` | `service` hides everything that may not be offered to other people (see `docs/LICENSING.md`) |
| `VIDEOKIT_HOME` | `~/.videokit` | Jobs, caches, downloaded engines and tools |
| `VIDEOKIT_FFMPEG_DIR` | `~/.videokit/bin`, then `PATH` | Folder holding ffmpeg and ffprobe 7+ |
| `VIDEOKIT_CHROME` | found automatically | Chrome or Chromium executable |
| `GEMINI_API_KEY` | | For `generate_image`. Not needed where a network proxy adds the key |

## mysticsloth and other platforms

For a web platform, run the server over HTTP on the same machine as the platform's backend, in service mode:

```bash
VIDEOKIT_MODE=service uv run --directory /path/to/videokit/server videokit-mcp --http --port 8765
```

The backend connects to `http://127.0.0.1:8765/mcp` with any MCP client library. The HTTP server has no login of
its own: keep it bound to 127.0.0.1 and never expose the port to the internet; the platform authenticates its
users and decides who may render. Renders take minutes of CPU each, so queue them on the platform side. Check the
Remotion license before rendering for other people at scale (`docs/LICENSING.md`).

## Layout

| Path | What |
|---|---|
| `server/` | The MCP server (Python) and its tests |
| `engines/<id>/engine.yaml` | Each engine's description, guides, requirements and license terms; `VIDEOKIT.md` beside it tells the AI how the engine's own guides map onto videokit |
| `engines/howto/` | The How-to Video Kit itself |
| `vendor/` + `vendor.lock.json` | Upstream engines as pinned git submodules; fetched at the same commits into `~/.videokit/vendor` when the submodules are absent (plugin installs) |
| `.claude-plugin/`, `.mcp.json`, `skills/` | The Claude Code plugin |
| `docs/LICENSING.md` | Licensing per engine and mode |

To update an upstream engine: move its submodule to the new commit, test, and update `vendor.lock.json`
(`server/tests` checks that the two match).

## Test

```bash
cd server && uv run pytest -q
```

The tests connect a real MCP client to the server and render real videos with every engine. The first run takes
about 15 minutes (packages, the voice model, software-rendered animation); `-k "not animation"` skips the slowest.
