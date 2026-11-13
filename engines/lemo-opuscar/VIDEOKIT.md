# Lemo-Opuscar through videokit

Lemo-Opuscar is a library of 99 film styles. Each style has a `STYLE.md` with the rules an AI follows to make a
short film in that look, entirely in code: one `index.html` page that draws any frame on request, plus audio.
The library's own guides are the authority. Read them in this order with `get_guide('lemo-opuscar', <topic>)`:

1. `agents`: the workflow (start, style choice, one round of questions, treatment, production, delivery).
2. `style/<slug>`: the chosen style's `STYLE.md` (find slugs with `list_styles('lemo-opuscar', '<words>')`).
3. `director` and `technique`, when the workflow sends you there.

## What changes when you use it through videokit

The guides were written for the library's own Claude Code skill ("skill mode"). Read them with these swaps:

| The guides say | Through videokit |
|---|---|
| `sh setup.sh` / `setup.sh deps` | `setup_engine('lemo-opuscar')` (core tier). For narration or the pluck synth: `setup_engine` options are not needed; use videokit's `narrate` tool, or ask the user before installing the voice/music tiers |
| `$LIB` | The `lib` path that `scaffold` returns. Run library tools from there with the project's absolute path |
| `films/<name>/` | The `project_dir` you gave `scaffold` |
| `setup.sh demo <slug>` | Not needed: the demo source is already at `<lib>/styles/<slug>/demo/` (read it after your TREATMENT.md, as the guides say; never render or copy its story) |
| Image generator (styles marked ✦) | videokit's `generate_image` tool (Gemini). Tell the user how many images and of what before generating |
| `node core/render/video.mjs` etc. | `render('lemo-opuscar', project_dir, {action: ...})`, which runs the same tools as a background job |

`render` actions: `stills` (`times: [1.5, 3]`), `video` (`fps`, `workers`), `events`, `readcheck`, `mux`
(`audio: <wav>`, `grain`), `build` (runs the project's own `build.sh`).

## Licensing (enforced: this engine is hidden in service mode)

- Films you make are yours, commercial films included, with no credit needed.
- The guides and style prompts are CC BY-NC 4.0: use them to make your films; do not copy them into anything you
  distribute or sell.
- Never reuse a demo's story, music, fonts, footage, photographs or narration, nor Clawd (Anthropic's character).
  Third-party assets you add keep their own licenses: credit them with `write_credits`.
