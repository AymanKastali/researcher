# Teaching Standard

**Everything in this repo is output of the `mattpocock-skills:teach` skill.**
That skill is the specification; this file records how it maps onto this repo
and which of its rules are mechanically checkable.

Read the skill itself for the philosophy — it is the authority. When this file
and the skill disagree, the skill wins and this file is wrong and should be
fixed.

## One workspace per topic

The skill assumes a single teaching workspace at the current directory, with
one `MISSION.md` at its root: *"One mission per workspace. If the user wants to
learn two unrelated things, that is two workspaces."*

This repo holds several unrelated topics, so **each `topics/<topic>/` directory
is a complete workspace** and the repo root is just the shelf they sit on.

| Skill artefact | Lives at |
|---|---|
| `MISSION.md` | `topics/<topic>/MISSION.md` |
| `RESOURCES.md` | `topics/<topic>/RESOURCES.md` |
| `NOTES.md` | `topics/<topic>/NOTES.md` |
| `learning-records/` | `topics/<topic>/learning-records/` |
| `lessons/` | `topics/<topic>/lessons/` |
| `reference/` | `topics/<topic>/reference/` |
| `assets/` | `assets/` — **shared, at the repo root** |

Two deliberate divergences from the skill's layout:

- **`assets/` is hoisted to the root and shared.** The skill scopes components
  per workspace. One copy is the single source of truth here; see
  `docs/agents/design-system.md`.
- **Topics never reference each other**, which costs the skill's interleaving
  tool. See `docs/agents/topic-independence.md`.

`index.html` at the root is not a skill artefact. It is navigation across
workspaces and the one page allowed to name every topic.

## Every lesson, without exception

The skill's per-lesson requirements, as a checklist:

- **One tightly-scoped thing**, tied to the mission, in the zone of proximal
  development calculated from `learning-records/`.
- **A recommended primary source** — the single highest-trust resource found on
  the topic, drawn from `RESOURCES.md`, in a `Read this next` section.
- **Citations throughout.** Claims link to the source they came from. Never
  parametric knowledge; if no source covers it, the lesson says so.
- **Links to the neighbouring lessons and the reference document.** Every
  lesson carries `← Contents`, the previous and next lesson, the reference
  sheet, `Mission` and `Resources` in `<p class="nav-links">`. When a new
  lesson lands, the previous lesson's `Coming next` and nav bar must be updated
  to link to it — a lesson written as the last one goes stale the moment
  another arrives.
- **A reminder to ask the teacher.** The `.ask-teacher` paragraph. The agent in
  this workspace is the teacher; anything unclear is a question, not a dead
  end.
- **Retrieval practice with an immediate feedback loop** — a quiz, a recall
  card, or both. Reading is not practice.

## Quizzes

The skill: *"each answer should be exactly the same number of words (and
characters, if possible). Don't give the user any clues about the answer through
formatting."*

In practice that means four things, all of which `check-lessons.py` verifies:

1. **Every option in a question has the same word count.** Not approximately.
2. **Character counts stay within roughly ten of each other.** Word parity
   without char parity still leaves a visibly longer button.
3. **The correct answer is spread evenly across positions.** Answers clustered
   in the middle are the classic test-writing tell, and they are exploitable
   without knowing anything. Audit across the whole repo, not per lesson.
4. **Every option gets its own feedback**, and only the correct one reads as
   affirmative. A wrong answer should teach something specific, not just be
   wrong.

One carve-out, reasoned rather than convenient: **options that are code or SQL
are exempt from word parity** and held to character parity alone. Padding a
`SELECT` to hit a whitespace-token count makes the SQL less idiomatic, and
plausible SQL is the thing being tested. `check-lessons.py` still reports these
so the exemption stays a decision rather than a drift.

Other quiz mechanics, from `assets/quiz.js`: one attempt per question, on
purpose. Guessing until the button turns green is recognition, not recall.

## Fluency versus storage strength

Design for storage strength, which means desirable difficulty:

- **Retrieval practice** — recall from memory before checking. Every lesson.
- **Spacing** — later lessons open by reaching back to earlier ones. The
  outbox lessons mark these `Reaching back to Lesson NN`.
- **Interleaving** — unavailable across topics by Ayman's rule, so what remains
  is spacing within a topic. Recorded in `docs/agents/topic-independence.md`;
  do not quietly re-derive it as an oversight.

## Learning records

Write one when the user demonstrates genuine understanding, discloses prior
knowledge, corrects a misconception, or shifts the mission. Not for material
merely covered — coverage is not learning.

**Supersession is marked, never deleted.** When a later record contradicts an
earlier one, add a `**Status:**` line to the earlier record pointing at the
newer one. Partial corrections say so and stay `active`. The history of how
understanding changed is itself signal.

## Reference documents

Lessons are rarely revisited; reference documents are. They are the compressed
essence — the algorithm, the decision table, the glossary — designed for quick
lookup and for printing, which is why `lesson.css` carries a `@media print`
block.

A glossary is essential for any topic with its own nomenclature, and once it
exists **every lesson adheres to its terms**. Be opinionated: where the field
has several words for one concept, pick one and name the others as aliases, so
an interviewer's wording is recognisable.

## Wisdom

Knowledge comes from `RESOURCES.md`; skills come from the lessons; wisdom comes
from real practitioners. Each `RESOURCES.md` has a `Wisdom (Communities)`
section with curated candidates.

When a question turns on judgement rather than fact, answer it — then point at
a community. Do not propose them unprompted and repeatedly; if Ayman opts out,
record that in `RESOURCES.md` so future sessions stop asking.

## Known divergence, open for review

The skill says a lesson *"should be short, and completable very quickly"*
because working memory is small. The lessons here run 1,800–5,400 words, which
is 15–30 minutes of dense reading each — considerably longer than the skill
intends, traded deliberately for interview-depth on a single mechanism.

This is Ayman's call to keep or change, not a bug to fix quietly. If it changes,
the fix is to split lessons, not to thin them.

## Before you finish

```sh
uv run python docs/agents/check-lessons.py
```

It reports quiz word parity, character spread, answer-position balance,
feedback coverage, and the per-lesson requirements (primary source, ask-teacher,
neighbour links). A clean run is necessary, not sufficient — it cannot tell you
whether the lesson is in the zone of proximal development.
