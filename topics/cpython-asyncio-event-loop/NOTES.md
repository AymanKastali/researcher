# Notes

Working notes and stated preferences for this topic.

## Learner preferences

- **Sources over assertion.** Every substantive claim carries a quotation with
  attribution, and the two evidence markers — **[guaranteed]** and
  **[impl detail]** — are kept visibly distinct on the page, never merged into
  one confident voice.
- **Batch, don't drip.** The whole topic is built in one pass. Spacing is advice
  inside the lessons, not a delivery schedule.
- **Dark only, mobile first.** Every page is read at phone width before it ships.
  The wide ASCII figures in lessons 2, 8 and 13 are the ones that need checking
  there — each is inside a `.figure-body` so it scrolls in its own container.

## On code in this topic

The repo rule is that illustrative code is Python and quoted excerpts keep their
original language. This topic has a wrinkle that a later session would otherwise
read as a violation, because **the primary source is itself Python**.

- **Quoted CPython source** sits in a `.code` block whose `.code-meta` names the
  language and **never** carries `.code-illustrative`, followed immediately by a
  `p.small-print` giving `file:line-range — function()` and a link to the line
  range on GitHub at tag `v3.13.11`. If it has an attribution line under it, it
  is a quotation.
- **Code written for a lesson** carries `.code-illustrative` with the words
  "Written for this lesson", exactly as elsewhere in the repo. There are only
  four such blocks in the whole topic (lessons 3, 7, 12 and 13), and every one of
  them is a *reproduction* of something stated in prose — never a claim in its
  own right.
- **C appears only inside quotations**, from `Modules/_asynciomodule.c`, and is
  never used to illustrate anything. The `.code-language` reads `C` so it cannot
  be mistaken for the Python around it.
- **The ASCII figures are drawn for the lessons** and are marked as such in their
  `figcaption`. They are diagrams, not code, and sit in `figure` /
  `.figure-body`.

## Where this topic came from

Built from `docs/research/cpython-asyncio-event-loop.md` in this repo — a
3,710-line reading of the machinery whose every citation was diffed against the
upstream tag before being written down. The lessons add no claims to that
document; they sequence it for learning and quote the same primary sources
directly. Its §7 (documentation/source disagreements) and §9 (what could not be
verified) become lesson 15 and a reference document rather than being quietly
dropped, because the list of things the sources refuse to say is the most
transferable part of the research.

**One number in the research document was not carried over as fact.** Every
measurement it reports is reproduced here labelled as a single-machine
measurement made for that document, never as a benchmark. Where a reader expects
a performance figure and finds a mechanism instead, that is deliberate.

## Teaching decisions made

- **The loop before the coroutine.** Lessons 1–6 never mention `await`. The
  alternative ordering — start from `async def` because that is what the reader
  already knows — produces fluency without storage strength: the reader recognises
  the words and cannot reconstruct the mechanism. Starting from `_run_once` means
  that by the time `_asyncio_future_blocking` appears in lesson 7, every
  destination it hands control to has already been built.
- **Lesson 3 is the hinge and is deliberately short.** The `ntodo` snapshot is
  four lines of code that explain fairness, thread safety, cancelled-handle
  behaviour and the documented `stop()` semantics at once. Giving it its own
  lesson rather than a section inside a longer one is the sequencing decision
  most likely to make the argument stick.
- **Lesson 7 is the second hinge, and comes before the round trip it enables.**
  The protocol is taught cold, on its own, and only then applied in lesson 8. The
  reverse order — trace the round trip, then explain the flag — was tried on
  paper and reads as magic followed by an explanation of the magic.
- **`sock_recv`, not a transport, is the traced path.** It is the shortest
  complete path from `await` to `epoll_wait` and back that fits in one lesson. The
  transport path is then shown as a *contrast* in the same lesson, because the
  single most surprising thing about it — no Future anywhere in the read path — is
  only visible against the `sock_recv` trace.
- **The `call_soon` cross-thread failure is taught as a latency, not a crash.**
  "It's not thread-safe" is the kind of thing a reader already believes and
  cannot act on. The measured 2.8-second stall, and the reason it is *unbounded*,
  is the version that changes behaviour.
- **The evidence markers are taught, not just used.** Lesson 15 makes the
  **[guaranteed]** / **[impl detail]** distinction the object of study. Without
  it the topic teaches conclusions; with it the topic teaches how to check them,
  which is the part that survives Python 3.15.

## Sourcing decisions worth recording

- **Every Python-level citation is line-exact against tag `v3.13.11`**, because
  the research document diffed each file byte-for-byte against the upstream tag
  before quoting it. Lessons therefore link to GitHub *line ranges*, not to file
  tops. When 3.14 is taught, every one of those anchors needs re-checking — a line
  number is the most fragile citation in this repo.
- **`Modules/_asynciomodule.c` is not shipped with a binary install.** Its
  citations come from the fetched tag file (3777 lines), which is why they are
  attributed differently from the `Lib/asyncio/` ones.
- **The test suite is cited as evidence of intent.** `test__run_once_schedule_handle`
  and `test__run_once_cancelled_event_cleanup` are quoted not to teach testing but
  because a behaviour a test pins is meaningfully different from a behaviour that
  merely happens — even when neither is documented.
- **PEP 3156 is quoted for design intent and then contradicted twice**, in
  lesson 15. Both contradictions are argued with both texts on the page. The PEP
  is not treated as wrong; it is treated as a 2012 document that the code has
  outgrown in two specific places.
- **A citation's text names the quoted lines; its link may span the enclosing
  definition.** Ten small-print citations link a wider range than the `file:a-b`
  label beside them — always the whole function or class the quote came from, and
  the link text is that symbol's name. This is deliberate, not drift. The label is
  the quote; the link is the context.

## The verification pass, and how to repeat it

Every quoted block and every line reference was re-checked against the upstream
tag after the topic was written, by fetching the raw files at `v3.13.11` and
diffing. Worth repeating verbatim whenever a citation changes:

- **75 quoted code blocks matched their cited line ranges byte-for-byte.** Two
  did not and were corrected: `_asynciomodule.c:288-297` → `288-298`, and
  `tasks.py:703-721` → `703-720` (721 is blank; the `sleep` body ends at 720).
- **171 distinct `file:line` references were bounds-checked** and spot-checked
  against the symbol each claims. None were out of range.
- **15 documentation excerpts were matched against the `.rst` sources** at the
  same tag. All 15 are accurate.
- **Three counted claims were wrong and were fixed.** `run_forever` is ten lines,
  not nine; `Handle._run` is eighteen, not fifteen (two places). "Eighty lines"
  for the 82-line `_run_once` was left as the deliberate round nickname it is.
- **One reference-sheet quote had silently dropped a comment line.** The
  `timeout` block in `reference/run-once.html` is now verbatim. A quote in this
  topic is never condensed — if it needs shortening, it stops being a quote.

## On the reference documents

Every `h2` in `reference/` carries a kebab-case `id`, and lessons deep-link to
the section that compresses them rather than to the page top. Every lesson links
at least one reference document, chosen because that page genuinely holds the
lesson's compressed form — not as boilerplate. If a heading is renamed, the
lesson links pointing at its old anchor break silently: grep `reference/*.html#`
across `lessons/` after any heading change.

## Open questions for a future session

- **The mission was inferred, not stated.** The request was to turn the research
  document into lessons; no starting point, deliverable or prior-knowledge floor
  was given. `MISSION.md` therefore takes its shape from the research document's
  own scope statement, and learning record 0001 records that as an assumption.
  If a real debugging problem or a real service appears, revise the mission and
  write a learning record — the lesson order would probably change, with lesson
  13 (threads) moving much earlier.
- **The assumed floor is fluent `async`/`await` and no internals.** If the reader
  already knows the `_ready`/`_scheduled` split, lessons 1 and 2 compress into
  one. Nothing has confirmed the floor by evidence yet.
- **CPython 3.13.11 is the version taught.** When 3.14 is read, the version ledger
  (lesson 14) and every line citation need re-checking. `_run_once` was
  byte-identical between `v3.13.0` and `v3.13.11`, which is the kind of stability
  that makes a line citation feel safer than it is.
- **Nothing here was checked against a free-threaded build.** Lesson 14's
  free-threading section is read from `#ifdef` branches and PEP 703. If a
  `python3.13t` becomes available, that section is the first thing to test.
- **`ProactorEventLoop` is absent from the whole topic.** If Windows ever
  matters, that is a second topic, not an addition to this one — and by the repo's
  own rule it would have to re-teach the loop from scratch rather than link here.
