# Claude Animation Base through videokit

A starter kit for hand-drawn-looking character animation in p5.js and p5.brush: one character with views,
emotions, mouths and dances, a shot timeline, a camera, transitions and a brush-painted medium. Read
`get_guide('claude-animation-base', 'guide')` (ANIMATION_GUIDE.md) first and follow it: storyboard first, build
shot by shot, check contact sheets, then render.

## What changes when you use it through videokit

| The guide says | Through videokit |
|---|---|
| Clone it and work in it | `scaffold('claude-animation-base', project_dir)` copies the kit, installs nothing yet, and makes its Google Font local |
| `node render.mjs --sheet/--strip/--stills ...` | Run them yourself in project_dir (they are quick), or `render(..., {action: 'sheet', times: [...]})`; then `look()` at the image |
| `node render.mjs --clip --out=out/video.mp4` | `render('claude-animation-base', project_dir)`: renders frames in parallel, then encodes; adds `--soft-gl` automatically on a machine with no GPU |

## No GPU (cloud sessions)

p5.brush's watercolour `fill` (bleed, texture) costs seconds per frame in software graphics: a 10 s video can take
two hours. On a machine without a GPU (`check_environment` says `gpu: false`), the kit's own author recommends
replacing watercolour fills with something cheaper: use `wash` colour and ink lines for backgrounds too, keep
`bleed` and `tex` off, and say in your summary that the full watercolour look needs a GPU machine.

## The character and licensing

The kit's character, Clawd (`src/clawd.js`), is Anthropic's: its design and name are not licensed for reuse.
Use it for private tests only. For any video that will be published or monetized, design your own character
(the guide shows how to swap it) and do not use Clawd's look or name. The code is MIT.
