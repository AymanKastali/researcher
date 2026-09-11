# Topic Independence

**Every topic under `topics/` is self-contained. A topic must not refer to,
link to, or assume any other topic in this repo.**

Stated by Ayman on 2026-09-11: *"each topic is totally independent of the
others, do not refer to any other topic from a topic."*

## What this forbids

Inside `topics/<topic>/` — lessons, reference sheets, `MISSION.md`,
`RESOURCES.md`, `NOTES.md`, learning records — none of the following:

- A link to a page in another topic (`../../<other-topic>/…`).
- Naming another topic or its lessons: *"the outbox course"*, *"as Lesson 03 of
  X showed"*, *"the other course"*.
- Assuming the reader has done another topic: *"the two failures you already
  know"*, *"you have seen this table before"*.
- A quiz question drawn from another topic, including interleaved warm-ups.
- `MISSION.md` listing another topic as prior knowledge, or as the reason
  something is out of scope.

## What this permits

- **Naming a general pattern and teaching it in place.** If a topic genuinely
  needs the transactional outbox, say what it is in a sentence or two, where it
  is used. The rule is against pointing elsewhere, not against the concept.
- **Two topics covering the same ground.** Duplication between topics is the
  intended cost. Do not factor a shared explanation out into a common page.
- **The shared `assets/` at the repo root.** Styling is not content — see
  `docs/agents/design-system.md`.
- **The contents page (`index.html`).** It sits at the root, above the topics,
  and is the one place that may list them all.

## What it costs, so nobody re-derives it

Interleaving — mixing retrieval questions from two confusable mechanisms — is
the strongest format the teaching skill has, and it is now unavailable across
topics. The substitute inside a topic is spacing: each lesson's warm-up draws on
earlier lessons in the same topic. Worth knowing this was traded away
deliberately, not overlooked.

## When a topic needs something another topic has

Teach it again, in this topic, scoped to what this topic needs. A three-sentence
definition in the right place beats a link that sends the reader somewhere else
mid-lesson. If that feels wasteful, it is the rule working as intended.
