# Design System

Every human-facing page in this repo — lessons, reference sheets, and the
contents page — is styled from **one shared set of assets at the repo root**.
There is no per-topic stylesheet, and there must never be a second copy.

```text
/
├── assets/
│   ├── lesson.css           ← the stylesheet every page links
│   ├── quiz.js              ← the one-attempt quiz widget
│   ├── hljs-dark-2026.css   ← code-block token colours
│   └── highlight.min.js     ← vendored highlight.js (offline)
├── index.html               → assets/lesson.css
└── topics/<topic>/
    ├── lessons/*.html       → ../../../assets/…
    └── reference/*.html     → ../../../assets/…
```

Hoisted to the root on 2026-09-11, at Ayman's request, from two byte-identical
copies under `topics/*/assets/`. The copies existed so each topic stayed
self-contained; the cost was that every fix had to be applied twice. One copy
is now the single source of truth: **fix the stylesheet once and every page
changes.** If a page needs a look the shared stylesheet cannot give it, add a
class to `lesson.css` — do not inline styles into the page, and do not start a
second stylesheet.

Pages are opened from disk as often as from GitHub Pages, so the paths above
are relative and nothing is loaded from a CDN.

## Page boilerplate

Lessons and reference sheets sit three levels down, so every asset path is
`../../../assets/…`. The contents page is at the root, so it uses `assets/…`.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lesson NN · Title</title>
<link rel="stylesheet" href="../../../assets/lesson.css">
<link rel="stylesheet" href="../../../assets/hljs-dark-2026.css">
<script src="../../../assets/quiz.js"></script>
</head>
<body>
<article class="page">
  …
</article>

<script src="../../../assets/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
</body>
</html>
```

Drop the two highlight.js lines only on a page with no code blocks.

## The rules the stylesheet encodes

These are Ayman's stated preferences, not house taste. Changing one is a
decision to raise with him, not a refactor.

- **Dark theme, always.** Stated 2026-09-10 as a project-wide rule.
  `lesson.css` is dark-only — no `prefers-color-scheme` switch, no light
  palette. The sole exception is the `@media print` block, which flips to
  ink-on-white so reference sheets stay printable.
- **Mobile responsive, always.** Stated 2026-09-10. Every page must read well
  on a phone. Two things to remember when authoring: the viewport meta tag in
  `<head>`, and `class="stacked"` on two-column text tables. Breakpoints live
  in the RESPONSIVE section of `lesson.css` (≤1100px sidenotes rejoin the flow,
  ≤640px phone, ≤380px small phone). **Fix responsiveness in the stylesheet,
  never in the page.**
- **The palette is verified, not chosen by eye.** Ground is off-black
  (`#16171b`) to limit halation; body text sits at 12.6:1 rather than the
  available 21:1, because maximum contrast is the uncomfortable end. Accents
  are lightened Okabe–Ito colour-universal hues. Three semantic colours with
  fixed meanings — amber = signal, green = affirmed, orange = cost — so the
  code is learned once. Colour is never the sole carrier of meaning: quiz
  results also get ✓/✗ glyphs. **If you change a colour, re-run the contrast
  check** and confirm body text stays in the 10–15:1 band, text ≥4.5:1,
  clickable borders ≥3:1.
- **Code blocks use highlight.js with Ayman's own editor colours.** Settled
  2026-09-10 after two wrong turns: a hand-rolled tokeniser was rejected ("do
  not use tricks"), then hand-written `<span>` tagging was rejected in favour
  of the standard library. Write plain, unmarked code inside
  `<pre><code class="language-python">`.
    - The library is **vendored, not loaded from a CDN.** Pages are opened from
      disk and must work offline.
    - Colours are VS Code's **Dark 2026** (the 1.135 default; no
      `workbench.colorTheme` is set, so the product default applies), lifted
      from `theme-defaults/themes/2026-dark.json`. Confirmed with Ayman
      2026-09-10 over the classic Dark Modern palette.
    - **Code tokens only.** The page keeps its own verified palette and the
      code block keeps `--code-bg`. Do not let the editor theme leak outward.
    - Anything hand-marked inside a code block is destroyed by
      `highlightAll()`, which rewrites the block from its text. Point at a line
      from the `.caption` beneath it instead.
- **Illustrative code is Python.** SQL, DDL, HTTP and config stay in their own
  languages. Verbatim excerpts quoted from a real source keep the source's
  language.

## Adding a component

Reuse is the default. Before authoring a page, read `assets/` and build from
what is there. Anything a second page could reuse belongs in `assets/` — never
inline in a lesson. `quiz.js` is the model: one file, linked by every lesson,
no per-lesson variants.

The contents index (`index.html`) is the one page that is navigation rather than
prose, so it carries `class="page index"` and opts out of the reading measure.
Its pieces — `.index-stats`, `.course` / `.course-head` / `.course-meta` /
`.course-blurb`, and the `.deck` of `.card`s with the `.card-ref` and
`.card-out` variants — live in the CONTENTS INDEX section of `lesson.css`. A
new topic is a new `<section class="course">`; nothing new needs writing.

## Before you finish

- Every asset path resolves from the page's own directory (open the file from
  disk and check, or run a link sweep).
- No `prefers-color-scheme` anywhere.
- Two-column text tables carry `class="stacked"`.
- `.nojekyll` still exists at the root — without it GitHub Pages runs the files
  through Jekyll.
