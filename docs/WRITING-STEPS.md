# Writing step files

The field list is in `README.md` ("A step file"). This file is how to write steps that record on the first try and
read well.

## Find each target the way a person would

- Prefer `{ "role": "button", "name": "Generate report" }`. Add `"exact": true` when another element contains the
  same words (a "Reports" link next to a "Reports overview" heading).
- Then `label` (form fields), `placeholder` (search boxes), `text` (plain text you point at), `testId`, and `css`
  last. `within` (a CSS selector) scopes any of them; `nth` picks one of several matches.
- Get the real names from the app's source (button text, `aria-label`, headings) or from an accessibility snapshot
  of the running page. The helper does it for you, read-only:

  ```bash
  node snap.mjs <your howto.config.mjs> snaps / /customers/add
  ```

  It writes `<name>.txt` (the snapshot) and `<name>.png` for each path. Grep the text files for `button "`,
  `link "`, `heading "`, and `textbox "`. On Git Bash for Windows, set `MSYS_NO_PATHCONV=1` first, or paths that
  start with `/` get mangled.

- Lessons from recording many apps: a textbox with no name can match two fields, so add `nth`. A control can rename
  itself mid-video (a zoom readout stops being "100%" after zooming), so target the name it has at that step. A text
  match can hit two elements, so add `exact` or `within`. A placeholder you target is swapped too if it holds a
  `replaceText` name, so target the swapped wording.

## One step, one thing

- `click` for anything that changes the view. Give a click that loads a new page or panel a `waitFor` (a heading on
  the new view), or the next step may look for its target on the old one.
- `type` with `value` for search boxes. Keep it short; it types at 75 ms a character.
- `select` with `value` for a dropdown.
- `look` points at a result without touching it: a report option, a status, a count.
- `hover` on the last button of a flow that would save or download. Never click those. The recorder refuses writes
  anyway (exit 3).
- `upload` with `file` for a file picker (invented data only, kept next to your step files).
- To close a dialog, prefer `press` with `key: "Escape"`. Clicking Cancel can leave an empty highlight box where the
  dialog had been.
- `scroll` with `dy` (about 1100 px is one screen), then a `look` at the heading you scrolled to.
- `goto` only to reset to a known page. A person cannot type your URLs, so do not teach with it.

## Camera and timing

- Zoom is automatic, up to 1.4x on small targets. Use `"zoom": false` on wide tables and full-page results, or a
  number to force it.
- When the caption describes something bigger than or next to the target, highlight that thing with `show` (a second
  target), or point at it with a `look` step. A step that says "the top right shows its progress" zoomed onto a box
  that cut off the progress it described, and had to be retargeted.
- `read` is the pause between the highlight landing and the cursor moving. Leave it at the default (450 ms). Long
  waits there feel like the video is stuck. The reading time is added after the action (`hold`, stretched
  automatically for long captions).

## Captions

- Imperative for actions ("Click Customers at the top of the page."), plain statements for `look` steps ("The list
  shrinks to the customers that match.").
- Use the exact words on the screen, in the same capitalization, so people can match them.
- Say only what is visibly true on the demo data. If a list's order or a count has not been checked, leave it out.
  Look at every review still and check each caption against it.
- End the video on the result: the report, the filtered list, the record that was found.
- One task per video, 3 to 7 steps, under about 45 seconds. Title the video with the task in plain words.

## Start URL and data

- `start` is a path on your demo app. Pick records whose demo data shows the feature well: a search that returns one
  clear match, a filter that leaves a short list.
- Re-record after any change to the screens in a video. The run fails on a moved button, which is the point.

## Reviewing a render

Open every `review/*.jpg` (the title card and one still per step showing the step's result) and, for click steps,
`web/steps/NN.jpg` (the moment before the click). Check that the zoom shows what the caption names, nothing it names
is cut off, the highlight is on the right thing, and the caption is true for what is on screen. After a fix to names or
titles only, edit `capture/timeline.json` and render again; there is no need to record again.

## Many videos at once

Write the list of tasks under your app's menu names, then give each helper agent a batch of about five. Give them one
shared brief: the environment, the rules above, the review checklist, and a table to report back (slug, title,
steps, seconds, ends on a hover, notes). Run the app yourself and tell them not to touch it. Record one file at a
time per agent and render each batch in one call.
