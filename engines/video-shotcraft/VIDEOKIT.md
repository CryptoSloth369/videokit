# video-shotcraft through videokit

Cinematic product promos from real page captures: 124 tuned shot recipes ("cards"), the Ink Press template, beat
sync and sound design, rendered with Remotion. Its guides are mostly in Chinese (the README is English); read them
as they are. Start with `get_guide('video-shotcraft', 'skill')`, which picks one of three modes (use the template
as is, free creation, or co-creation with the user) and points to the rest.

## What changes when you use it through videokit

| The guides say | Through videokit |
|---|---|
| Copy or work inside `template/` | `scaffold('video-shotcraft', project_dir)` copies the template (with `capture-template.mjs` in `scripts/`) and you work there |
| `npm install` / `npx remotion render ...` | `render('video-shotcraft', project_dir, {composition?, out?, props?})`: installs on first render, then renders with the Chrome already on this machine (Remotion's own Chrome download is not needed) |
| A shot card's doc / demo | `list_styles('video-shotcraft', '<words>')`, then `get_guide('video-shotcraft', 'style/<card-name>')`; demo source is in `<lib>/demos/` |
| `assets/scripts/sfx-source.py search/get` | `sound_effects(...)` (CC0 by default; `license: 'by'` also allows CC BY, which then needs credit) |
| BGM from `assets/audio/bgm/` | Allowed, except `bgm-tech-house.mp3` (no recorded source). Mixkit Stock Music Free License: commercial use, no credit |
| `publish/upload_post.py`, JianYing export | Not wrapped. Ask the user before publishing anywhere |

## Before a video is published

The template's own sound effects `keyboard.mp3`, `riser-cine.mp3`, `sparkle.mp3`, `whoosh-big.mp3` and `pop.mp3`
have no recorded source. Replace them with `sound_effects` results before a video is monetized. `write_credits`
lists any that are still in the project.

## Licensing

Code Apache-2.0: fine for monetized videos and inside a service. Remotion is free for individuals and companies of
up to 3 people. Capture only demo data, never a real customer's.
