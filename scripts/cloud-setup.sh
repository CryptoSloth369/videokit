#!/bin/bash
# Setup for a Claude Code cloud session on this repository. Run from the folder that holds the checkout
# (the environment's setup script does: bash videokit/scripts/cloud-setup.sh). Idempotent; a failed optional step
# only prints a warning so the session still starts.
set -u
cd "$(dirname "$0")/.." || exit 0
warn() { echo "videokit setup: $*" >&2; }

git submodule update --init --depth 1 || warn "submodules not fetched; engines download on first use instead"
(cd server && uv sync --quiet) || warn "uv sync failed"
(cd engines/howto && npm ci --no-audit --no-fund --silent && cd render && npm ci --no-audit --no-fund --silent) \
  || warn "how-to kit packages not installed"

# ffmpeg 7+ (Ubuntu 24.04 ships 6.1): a static build into ~/.videokit/bin, which the server uses first
if ! "$HOME/.videokit/bin/ffmpeg" -version >/dev/null 2>&1; then
  mkdir -p "$HOME/.videokit/bin" /tmp/vk-ffmpeg
  curl -fsSL https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz \
    | tar xJ -C /tmp/vk-ffmpeg \
    && cp /tmp/vk-ffmpeg/*/bin/ffmpeg /tmp/vk-ffmpeg/*/bin/ffprobe "$HOME/.videokit/bin/" \
    || warn "ffmpeg 7+ not installed; lemo-opuscar's mux step will refuse ffmpeg 6"
  rm -rf /tmp/vk-ffmpeg
fi

# lemo-opuscar core tier (npm, Python venv) + brotli, which its font tool needs
if [ -f vendor/lemo-opuscar/AGENTS.md ]; then
  LEMO_OPUSCAR_HOME="$PWD/vendor/lemo-opuscar" sh vendor/lemo-opuscar/plugin/skills/lemo-opuscar/scripts/setup.sh deps \
    && uv pip install --quiet --python vendor/lemo-opuscar/.venv/bin/python brotli \
    || warn "lemo-opuscar packages not installed; call setup_engine('lemo-opuscar')"
fi
exit 0
