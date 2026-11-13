---
name: videokit
description: Make a video with the videokit MCP tools - a short film in one of 99 styles, a product promo, a character animation, a how-to tutorial of a web app, pixel art effects, or a music video - including narration, music cut to the beat, sound effects, generated images and the credits for a YouTube description. Use when someone asks for a video, film, short, promo, explainer, animation, tutorial video or YouTube video, or asks what kinds of videos can be made.
---

# videokit

The videokit MCP server (tools named `list_engines`, `get_guide`, `render`, ...) makes videos by having you write
the animation as code; an engine renders it in headless Chrome and ffmpeg encodes it.

1. `check_environment`, then `list_engines`. Pick the engine that fits the request:
   - **lemo-opuscar**: a short narrated film in one of 99 styles (explainers, stories, launches, music videos).
   - **video-shotcraft**: a cinematic promo of a web product, from screenshots of the real app.
   - **claude-animation-base**: a hand-drawn character animation.
   - **howto**: a tutorial of a web app, with a cursor and step captions, plus a help page.
   - **pixelfx**: pixel art effects and sprite sheets.
   If the user has not decided what they want, offer two or three options with one line each.
2. Read the engine's guide with `get_guide(engine)` (start with the `videokit` topic where there is one) and follow
   it. The guides hold the rules that make the videos good; skipping them gives generic results.
3. `setup_engine` if `list_engines` says the engine is not ready. Renders are background jobs: poll `job_status`.
4. Check your own work with `look(path)` on stills and on the finished video before you show it.
5. Sound: `narrate`, `beats`, `sound_effects`, `mux_audio`. Finish with `write_credits` and give the user the
   description block it returns.

For ideas, `search_prompts` finds prompts that made good code-made videos (personal mode only).

Licensing is part of the job: respect each engine's `license.notes` (no third-party characters, brands or
unlicensed music in videos that will be published or monetized), and tell the user about any warning that
`write_credits` returns.
