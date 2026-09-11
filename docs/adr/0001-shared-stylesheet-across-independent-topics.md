# Shared presentation layer at the repo root, not inside each topic workspace

The `/teach` skill puts reusable components in `./assets/` **inside** the
workspace, which here would mean one copy of the stylesheet, highlighter, theme,
and quiz widget per topic. We put them in a single root `assets/` instead, linked
from each page with a relative path, because topics are independent in *content*
but must be identical in *appearance*: per-topic copies would diverge the moment
a fifth topic existed, and a design fix would have to be applied N times instead
of once — retroactively improving every lesson ever written is the whole point of
sharing it.

## Considered options

- **Assets inside each workspace**, as the skill specifies. A topic directory
  would then be fully self-contained. Rejected: N copies of one stylesheet is N
  chances to drift, and the learner's stated rule for this repo is that the only
  thing shared across topics is the design.
- **A build step** that copies shared assets into each workspace on publish.
  Rejected: machinery to keep duplicates in sync, when not duplicating them costs
  nothing.

## Consequences

- Every page hard-codes its depth to the root: `../../../assets/` from a lesson
  or reference document, `../../assets/` from a topic index, `assets/` from the
  front door. This is what makes the decision hard to reverse — it is written
  into every page ever produced.
- Because that depth is now a correctness property, `scripts/check-asset-paths.py`
  exists to assert every local link resolves. It is the repo's only automated
  check.
- **A topic directory copied out of this repo renders unstyled.** Accepted: the
  topics are read at the published site, not moved around.
- Paths are relative rather than root-absolute, so a page works identically
  opened as `file://` and served from a Pages project subpath.
