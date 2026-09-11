# researcher

## Agent skills

### Issue tracker

Issues live as GitHub issues in `AymanKastali/researcher`, driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label named after itself. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Teaching workspaces

This repo hosts many teaching workspaces, one per subject. Read `CONTEXT.md` for
the vocabulary and `docs/adr/` before changing how pages are built.

### The workspace is a topic directory, never the repo root

`/teach` treats the current directory as its workspace. Here, a workspace is
`topics/<topic-slug>/` and nothing else. If you are at the repo root, do not
write `MISSION.md`, `lessons/`, `reference/`, `learning-records/` or `NOTES.md`
there — change into the topic directory first, or create it.

Topic slugs are kebab-case, so the directory name, its URL, and the lesson
filenames inside it all use one casing.

A workspace holds exactly what `/teach` documents, plus a markdown glossary:

```
topics/<topic-slug>/
├── MISSION.md  RESOURCES.md  NOTES.md  GLOSSARY.md  index.html
├── lessons/0001-<dash-case-name>.html
├── reference/<name>.html
├── learning-records/0001-<dash-case-name>.md
└── assets/                (only widgets this one topic needs)
```

Lesson and learning-record numbers are scoped to the workspace and restart at
`0001` in each. One mission per workspace: a second subject means a second
directory.

### Each topic is a source of truth

A topic is written to be referred back to, so its content has to be right, not
merely plausible.

- **Ground every substantive claim in a primary source** — the specification,
  the official documentation for a named version, the original paper, or a
  recognised textbook. Never teach from parametric knowledge.
- **Definitions come from a textbook or a specification**, quoted rather than
  paraphrased, in a `.definition` block with the edition, chapter, or section
  recorded. Where authorities disagree, say so and cite both.
- **Practices come from the same standard of source.** "This is how it is done"
  needs an attributable owner.
- Record every source used in `RESOURCES.md` with enough detail to find it
  again: title, author, edition or version, year, and a link.
- Quote with `.excerpt`, attributed and linked. A claim's support has to be
  visible on the page, not just in the agent's reasoning.
- If a claim cannot be sourced, either leave it out or mark it plainly as
  uncertain. A confident sentence with nothing behind it is the one failure this
  repo cannot absorb.
- Verify before writing. Search, read the source, quote what it says.

### Content rules

- **No cross-topic references.** No lesson, reference document, glossary, or
  learning record may link to or mention another topic. A concept needed twice is
  taught in full in both places. The root `index.html` is the only exception, and
  it is navigation, not content.
- **No runnable project inside a topic.** A topic is a document set, not
  software. Ground claims in sources rather than in code you could run.
- **Illustrative code is Python**, and is marked as written for the lesson with
  `.code-illustrative` so it can never be mistaken for a quotation. Quoted source
  excerpts keep their original language.
- Every lesson ends with the primary source to read next and the reminder that
  the agent is the learner's teacher.

### Pages

Every page links the shared presentation layer in root `assets/` with relative
paths, so it works over Pages and opened as `file://`:

| Page | Prefix |
| --- | --- |
| `topics/<slug>/lessons/*.html`, `topics/<slug>/reference/*.html` | `../../../assets/` |
| `topics/<slug>/index.html` | `../../assets/` |
| root `index.html` | `assets/` |

Never use a root-absolute path: Pages serves this repo under `/researcher/`.

A page's boilerplate is a viewport meta tag, `lesson.css`, and — only if it
contains code or a quiz — `highlight-theme.css`, `highlight.min.js` with a
`hljs.highlightAll()` call, and `quiz.js`.

- **Dark only.** No light palette, no `prefers-color-scheme` block, no theme
  toggle, no `@media print`. Reference documents are screen-only by design.
- **Mobile responsive is a requirement.** Read every page at phone width before
  shipping it. Code blocks (`.code`), tables (`.table-wrap`) and wide figures
  (`.figure-body`) each scroll inside their own container; the page body never
  scrolls sideways.
- **Compose from the classes in `assets/lesson.css`**:
  - Shell and type: `.page`, `.lead`, `.small-print`, `a.citation`
  - Lesson masthead: `.lesson-header` / `.lesson-number` / `.lesson-mission`
  - Any other page's masthead: `.page-header` / `.page-eyebrow` / `.page-blurb`
    — the `.lesson-*` names are for lessons only
  - Sourcing: `.excerpt` with a `figcaption`; `.definition` / `.term` /
    `.attribution`
  - Code: `.code` / `.code-meta` / `.code-language` / `.code-illustrative`
  - Asides: `.aside.note` / `.aside.warning` / `.aside.insight`
  - Figures and tables: `figure` / `.figure-body`, `.table-wrap` (add
    `wrapped` when cells hold sentences rather than labels)
  - Quizzes: `.quiz` / `.quiz-question` / `.quiz-answers` / `.quiz-answer` /
    `.quiz-explanation`
  - Indexes: `.index-list` / `.index-number` / `.index-title` /
    `.index-summary`, `.empty-state`
  - Lesson footer: `.lesson-footer` / `.primary-source` / `.ask-teacher` /
    `.lesson-nav`
- New styling that a second lesson could reuse goes in `assets/lesson.css`, never
  inline in a lesson. A widget only one topic needs goes in that topic's own
  `assets/`.
- **Quiz answers must be the same length** in words and, where possible,
  characters. Mark the right one with `data-correct`. The stylesheet keeps the
  boxes equal width; do not let the text undo it.
- Colour code with the vendored `highlight.js` only — never a hand-written
  tokeniser and never hand-tagged spans in markup.

### Adding a topic means updating the front door

Root `index.html` lists the topics and is maintained by hand. Creating a
workspace is not finished until the front door links to its `index.html`.

### Checking pages

```
uv run python scripts/check-asset-paths.py
```

Every local `href` and `src` in every HTML file must resolve to a file on disk,
and none may be root-absolute. Run it after adding or moving any page. It is the
only automated check in this repo; everything else is verified by reading the
page in a browser at desktop and phone width.
