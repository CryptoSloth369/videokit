# Start here (written for your AI agent)

This file is for an AI coding agent, such as Claude Code. Someone downloaded this folder and handed it to you. Your
job is to set up their how-to video tool on their own computer, prove it works on the bundled example, and then help
them write step files for their own app.

The tool: a JSON step file lists what to click and one caption line for each step. `record.mjs` plays it in headless
Chrome against demo data. `render_modal.py` (cloud) or `render_local.py` (this computer) renders a video with a
cursor, click ripple, highlight ring, zoom, and "Step N of M" captions. `build_packet.mjs` collects the videos into a
help-center page. Read `README.md` first for the full step-file format and `docs/WRITING-STEPS.md` before writing
any step file.

## How to work with the person

- Ask before installing anything or signing in to anything. Do each phase below, show them the result, then move on.
- Use plain words. They are comfortable in a terminal but are not video editors.
- Edit files with your edit tool, not shell one-liners that rewrite files in place.
- Never print or open a `.env` file. If you need to know which keys exist, list the names only.

## Phase 1: check the machine

1. `node --version` must be 20 or newer. `python --version` (or `python3`) must be 3.10 or newer.
2. `ffmpeg -version` must work. If not, help them install it (winget, brew, or apt) before going on.
3. Ask which renderer they want. **Modal** is faster (about a minute per video) and needs an account at modal.com plus
   `pip install modal` and `modal token new`. **Local** needs nothing extra but takes a few minutes per video. They
   can switch later; the outputs are identical.

## Phase 2: install

```bash
npm install
npx playwright install chromium
cd render && npm install && cd ..        # needed for local rendering; harmless for Modal
```

## Phase 3: run the example end to end

Use a free port. Check what is listening first, and pick another (`PORT=5000`) if 4173 is taken; then set
`HOWTO_BASE=http://127.0.0.1:<port>` for the record step.

1. Start `node example/serve.mjs` in the background.
2. `node record.mjs example/howto/find-a-customer.json example/howto/add-a-customer.json`
   It runs headless. No window may open. Expect "recorded find-a-customer: 4 steps" and the same for the other.
3. Render both: `python render_local.py --captures <cap1>,<cap2>` or
   `modal run render_modal.py --captures <cap1>,<cap2>`, where the capture folders are
   `example/howto/out/<slug>/capture`. On Windows set `PYTHONIOENCODING=utf-8` before `modal run`.
4. Open a few `example/howto/out/<slug>/review/*.jpg` stills together with the person. Read the captions against
   the stills.
5. `node build_packet.mjs example/howto/packet.json`, then have them open `example/howto/out/packet/index.html`.
6. Stop the server.

If a step exits with code 2, a target was not found: open `failed-step-N.png` beside the capture. Exit code 3 means a
step tried to write; see the rules below. Do not work around either.

## Phase 4: their own app

1. Ask what the app is, how it runs locally, and whether a demo copy with invented data exists. If it does not, help
   build one before recording anything. **Stop if the app holds health information or other sensitive personal data:
   do not record it, even with a login of their own.** Only recording copies with invented data are allowed.
2. Create a folder for their videos (for example `my-app/howto/`). Copy `example/howto/howto.config.mjs` into it and
   fill in `app`, `baseUrl`, `accent`, and `hideCss`. If the app needs a login, add `signIn` that sets a cookie for a
   **dedicated demo login**. Never use or reset a real person's account.
3. Run `node snap.mjs <config> <outdir> <paths...>` on the main screens and grep the `.txt` files for button, link,
   heading, and textbox names. Never guess names.
4. Agree a list of tasks with them: real questions their users ask first, then the app's main screens. One task per
   video, 3 to 7 steps, under about 45 seconds.
5. Write one step file per task, record it, render it, review it, fix it. Then write `packet.json` and build the page.
   Make sure `out/` is in the `.gitignore` of whatever repo the folder lives in before the first render: renders are
   tens of megabytes.

## Hard rules for step files

- **Read-only is enforced by the recorder.** It aborts every request that is not GET, HEAD, or OPTIONS and exits 3
  naming it. A flow that saves ends on a `hover` over its final button, never a click. Exit 3 on a step that only opens
  or fills something means that control autosaves: end the video before it. List a POST route in `readsOverPost` only
  after reading its code and seeing it never writes.
- **A missing button is exit 2 plus a screenshot** (`failed-step-N.png`). Read the screenshot, fix the target, and
  re-record that file only.
- **Demo data only.** Typed values are short and plainly invented ("Sam Example", "sam@example.com"). If real names
  show up on screen even on a demo copy, list them in `replaceText` in the config so the browser swaps them before
  anything is filmed.
- **Never record an app holding health or other sensitive personal data.** Never type into a password or PIN field;
  `look` at it and say what goes there.
- **Headless always.** Never launch a visible browser window.
- **Captions say only what the screen shows.** Plain words, the screen's own names and capitalization, one
  instruction per step, imperative for actions and plain statements for `look` steps. Read every review still and
  check every caption against it; remove claims about order or counts you did not verify.
- Target things the way a person would find them: `role` + `name`, then `label`, `placeholder`, `text`, and `css` last.
  Give a click that opens a new view a `waitFor`.
- Do not hold a flow open with waits. End on the result.
- No em dashes in captions. Use the Oxford comma.

## When something fails

| Symptom | Likely cause |
|---|---|
| `ffmpeg` not found | Install it and reopen the terminal so PATH updates |
| `Run npm install inside render first` | `cd render && npm install` |
| Modal asks for a token | `modal token new`, then retry |
| Modal prints garbled characters on Windows | `PYTHONIOENCODING=utf-8` |
| Record exits 2 | Target not found; open the screenshot |
| Record exits 3 | A step tried to write; end on a hover |
| Playwright cannot find Chrome | `npx playwright install chromium` |

When the person is happy, tell them how to rerun a video after their app changes: record the same step file again,
render it again, rebuild the page.
