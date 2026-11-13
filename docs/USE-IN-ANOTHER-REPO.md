# Use videokit in another repository

To have videokit in every Claude Code chat on another repository (for example mysticsloth), add this file to
that repository as `.claude/settings.json`, or merge the two keys into the one it already has:

```json
{
  "extraKnownMarketplaces": {
    "videokit": {
      "source": { "source": "github", "repo": "CryptoSloth369/videokit" }
    }
  },
  "enabledPlugins": {
    "videokit@videokit": true
  }
}
```

Commit it. The next chat on that repository offers to install the videokit plugin; accept once, and from then
on the videokit tools and skill are there in every chat on it. This installs from videokit's default branch
(`main`).

## What the machine needs

The plugin runs the server with `uv`, and the engines need Node.js 20+, ffmpeg (7+ for lemo-opuscar's own audio
step) and Chrome or Chromium. Upstream engines download on first use (`setup_engine`), the voice model on the
first `narrate`.

In a Claude Code cloud session, the session's environment provides these. Claude cloud containers already have
uv, Node and Chromium; for ffmpeg 7+, add this line to the environment's setup script (it runs from the folder
holding the checkouts):

```bash
mkdir -p ~/.videokit/bin && curl -fsSL https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz | tar xJ -C /tmp && cp /tmp/ffmpeg-n8.1-*/bin/ffmpeg /tmp/ffmpeg-n8.1-*/bin/ffprobe ~/.videokit/bin/ || true
```

## Why not just a `.mcp.json`

A server in a repository's `.mcp.json` must be approved by you before Claude Code starts it, and a repository
cannot approve its own servers (a cloned repository must not be able to grant itself tools). The plugin route
asks once, when you install it. Inside the videokit repository itself, its `.mcp.json` asks once: approve
`videokit` when Claude Code offers it.
