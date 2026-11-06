# How-to Video Kit

By Nick Rougeau · redwaterrev.com, where we help local businesses adopt AI and custom software.

This is the tool we use to make short how-to videos of a web app without screen recording. You write a small
JSON file that lists what to click and one line of caption for each step. A script plays it in headless Chrome
against demo data. A renderer turns that into a finished video: the app in a frame, a cursor that glides to each
target, a click ripple, a highlight ring, a gentle zoom, and a "Step 2 of 5" caption under the app. Text only, no
voice. A last script collects the videos into a small help-center page: an index with search, written steps with
a screenshot each, and the video loading only when someone presses Play.

When your app changes, run the recorder again. If a button was renamed or moved, the run stops and saves a
screenshot of what it saw, so you know exactly which video needs fixing instead of shipping a stale one.

**Working with an AI agent?** Open this folder in Claude Code and say: *"Read START-HERE-FOR-YOUR-AI.md and set up
my how-to video tool."* It will install everything, run the example, and then help you write step files for your own
app.

## What you need

| You need | Why |
|---|---|
| Node.js 20 or newer | Runs the recorder and the page builder |
| Chrome | Playwright installs its own copy with `npx playwright install chromium` |
| Python 3.10 or newer | Runs the render scripts |
| ffmpeg on your PATH | Cuts the review stills and the small web copy of each video |
| **One of:** a Modal account, or just your own computer | Rendering. Modal (modal.com, pay as you go, about a minute and a few cents per video) is fast. Local rendering needs nothing extra but takes a few minutes per video |

## Run the example (about 15 minutes the first time)

The `example/` folder has a tiny fake app (a customer list with a search box, a status filter, and an add form),
two step files, and a `packet.json`. Every record in it is invented.

```bash
npm install                                   # recorder dependencies
npx playwright install chromium               # Chrome for the recorder, once

# 1. Serve the example app (leave this running; use a second terminal for the rest)
node example/serve.mjs                        # http://127.0.0.1:4173, or PORT=5000 node example/serve.mjs

# 2. Record. Headless: no browser window opens. A few seconds per step.
node record.mjs example/howto/find-a-customer.json example/howto/add-a-customer.json
#    -> example/howto/out/<slug>/capture/

# 3a. Render on your own computer
cd render && npm install && cd ..             # once
python render_local.py --captures example/howto/out/find-a-customer/capture
# 3b. Or render on Modal (sign in once with `modal token new`)
pip install modal
modal run render_modal.py --captures example/howto/out/find-a-customer/capture
#    -> example/howto/out/find-a-customer/find-a-customer.mp4  (the video)
#       .../review/*.jpg  (one still per step, to check it without playing it)
#       .../web/          (small MP4, poster, step screenshots, howto.json)

# 4. Build the help page once every video in packet.json is rendered
node build_packet.mjs example/howto/packet.json
#    -> example/howto/out/packet/index.html   (open it in a browser)
```

Pass several capture folders separated by commas to render more than one video in a single call. On Windows, set
`PYTHONIOENCODING=utf-8` before `modal run`.

The add-a-customer video ends with a `hover` on **Save customer**, not a click. That is on purpose: see "Read-only"
below.

## Point it at your own app

1. Run your app locally (or a demo copy) with **invented data only**. See "Rules" below.
2. Make a folder for your videos, for example `my-app/howto/`. Copy `example/howto/howto.config.mjs` into it and
   change `app` (the name in your app's header), `baseUrl`, `accent` (your brand color), and `hideCss` (hide
   feedback widgets and chat bubbles). The comments in that file explain every setting.
3. Write one step file per task. Start from `example/howto/find-a-customer.json`. Read `docs/WRITING-STEPS.md` for how
   to find each target and how to word the captions.
4. Record, render, review the stills, then build the page with a `packet.json` like the one in the example.

If your app needs a login, add a `signIn` function to the config that sets a cookie for a **dedicated demo login**,
never a real person's account.

## A step file

```json
{
  "title": "Find a customer",
  "subtitle": "Customers",
  "start": "/",
  "steps": [
    { "say": "Click the Search customers box and type a name.", "do": "type",
      "target": { "placeholder": "Search customers" }, "value": "Robin" },
    { "say": "Click Save customer to add them.", "do": "hover",
      "target": { "role": "button", "name": "Save customer" } }
  ]
}
```

- `say`: the caption. Plain words, the same names the screen uses. One instruction per step.
- `do`: `click`, `type` (+ `value`), `select` (+ `value`), `press` (+ `key`), `scroll` (+ `dy`), `goto` (+ `url`),
  `upload` (+ `file`, or `files`, relative to the step file, invented data only), `look` or `hover` (point at it
  without clicking), or leave it out for a text-only step.
- `target`: how a person would find it: `role` + `name`, `label`, `placeholder`, `text`, `testId`, or `css` as a last
  resort. `within` (a CSS selector) scopes it and `nth` picks one of several matches. Optional `show` frames a
  wider box than the target.
- `waitFor`: a target to wait for after the action (the heading of the page a click opens).
- Timing: `read` (ms between the highlight landing and the cursor moving, default 450), `hold` (ms after the
  action, stretched automatically so a long caption can be read), `timeout` (ms to find the target).
- `zoom`: `false` keeps the view wide, a number forces that zoom. The default is up to 1.4x on small targets.

## Rules the tool enforces, and rules you keep

**Read-only is enforced by the recorder.** It aborts every request that is not GET, HEAD, or OPTIONS before the request
leaves the browser, and stops with **exit code 3** naming the request. Nothing is saved. To film a flow that saves,
end the video with `hover` on the final button and never click it. If a step that only opens or fills something
exits 3, that control autosaves: end the video before it. A route that only reads over POST can be listed in the
config's `readsOverPost` after you have read its code.

**Exit code 2 means a target was not found.** The recorder saves `failed-step-N.png` next to the capture. Open it, fix
the step's target, and record that file again.

**Demo data only.** Record a demo copy of your app with invented people and businesses. **Never record an app that
holds health information or other sensitive personal data**, and never a live customer database. If a few real names
leak into menus even on demo data, list them under `replaceText` in the config and the browser swaps them for
invented ones before anything is filmed.

**Headless always.** The recorder never opens a visible window.

**Captions say only what the screen shows.** Check every caption against the review stills before you share a video.

## Files

| File | What |
|---|---|
| `record.mjs` | Plays a step file in headless Chrome, saves screencast frames, sharp stills, and `timeline.json` |
| `snap.mjs` | Saves an accessibility snapshot and screenshot of your app's pages, for finding step targets |
| `render/` | The Remotion project that draws the video (`src/HowTo.tsx`; camera and cursor maths in `src/timeline.ts`). `npm run studio` inside it previews the composition |
| `render_modal.py` | Renders on Modal (env vars `HOWTO_MODAL_APP`, `HOWTO_MODAL_VOLUME` are optional) |
| `render_local.py` | Renders on your own computer (env var `HOWTO_CONCURRENCY` is optional) |
| `howto_common.py` | The review stills, web copy, and step screenshots both renderers share |
| `build_packet.mjs` | Builds the help-center page from `packet.json` and each video's `web/howto.json` |
| `example/` | A fake app, two step files, a config, and a `packet.json` to learn on |
| `docs/WRITING-STEPS.md` | How to write step files that record on the first try |

## The help page

`packet.json` nests categories as deep as your app needs. A group holds `videos`, child `groups`, or both, and `dir`
is inherited. Optional top-level keys: `tagline`, `brand` (two letters for the badge), `accent` (hex color), `note`
(a banner for drafts). `keywords` on a video are extra search words people might type that no caption says. The
output folder is plain static files: host it anywhere, or open `index.html` from disk. Links into the page are
`#/t/<slug>`, `#/t/<slug>/<step>`, and `#/c/<category id>`.

## License

MIT. Use it, change it, sell what you build with it. See `LICENSE`.
