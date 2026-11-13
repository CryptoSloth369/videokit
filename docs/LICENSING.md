# Licensing

What each part of videokit allows, for **monetized videos** (YouTube and similar) and for **mysticsloth**. This is
a reading of each project's license files, not legal advice. Each engine's terms are also in its
`engines/<id>/engine.yaml`, and the server enforces them.

## The two modes

| Mode | Set with | What it allows |
|---|---|---|
| `personal` (default) | `VIDEOKIT_MODE=personal` | Everything, for videos you make yourself, including monetized ones and videos you make for your own channel through mysticsloth |
| `service` | `VIDEOKIT_MODE=service` | Only material that may be built into a product other people use. Engines and libraries marked `personal_only` are hidden, and calls to them are refused |

Use `service` mode for any mysticsloth deployment where **other people** make videos.

## Per project

| Project | Monetized videos you make | Inside a service for other people | Rules the AI follows |
|---|---|---|---|
| How-to Video Kit (`engines/howto`) | Yes (MIT) | Yes | Renders with Remotion (see below) |
| [pixelfx](https://github.com/patch-gg/pixelfx) | Yes (MIT) | Yes | Keep `NOTICE.md` with shipped copies; do not use the Patch Pixel gallery font |
| [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | Yes: "films you make are yours, commercial films included" | **No** for the style guides (CC BY-NC 4.0) unless you buy a commercial license from the author. Code is MIT | Never reuse demo music, fonts, footage, the six demo narration tracks, or Clawd. Kept as a submodule, not copied |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | Yes (Apache-2.0) | Yes | Freesound effects limited to CC0 / CC BY with credits; the one stock track with no recorded source is excluded |
| [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) | Yes for the code (MIT) | Yes for the code | Clawd is Anthropic's character: use your own character in public videos |
| [awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) | Yes, as inspiration | **No**: the prompts are third-party posts | Personal mode only |
| [opus-video-prompts](https://github.com/joeseesun/opus-video-prompts) | Yes, as inspiration | **No**: the repo has no license | Downloaded on first use, never committed; personal mode only |
| three.js, react-three-rapier, react-postprocessing, librosa | Yes (MIT / Apache-2.0 / ISC) | Yes | Installed from npm / PyPI per project |

## Remotion

video-shotcraft and the how-to kit render with [Remotion](https://www.remotion.dev/license). It is free for
individuals and for companies of up to 3 people. A larger company needs a Remotion company license; check again
before mysticsloth renders for other users at scale.

## Voices, music, images and YouTube

- Images from `generate_image` come from Google Gemini under Google's terms (you may use what you generate,
  including commercially) and carry Google's invisible SynthID watermark.
- Narration uses Kokoro (offline, Apache-2.0 weights). Microsoft edge-tts is off by default: its terms for
  commercial use are unclear.
- Music and sound effects come only from sources whose license allows commercial use. Every render writes the
  credits it needs; paste them into the video description.
- YouTube can demonetize mass-produced, repetitive videos. Vary styles, structure and narration between videos.
