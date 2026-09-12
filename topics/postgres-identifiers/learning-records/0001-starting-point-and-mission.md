# Starting point: an assumed floor, not an established one

The mission was stated in three words — "i want to learn it" — with no schema in
hand, no deliverable, and no stated prior knowledge. When asked for a starting
point on PostgreSQL internals, the learner declined to give one and asked for the
research document to be turned into lessons directly.

`MISSION.md` was therefore written around **durable understanding** rather than a
deliverable, taking its shape from the research document's own scope statement:
choosing an identifier strategy from evidence rather than folklore, and still
being able to do it in a year. That is a storage-strength goal, so every lesson
carries retrieval practice and the set is written to be spaced over days.

**The floor is an assumption and is recorded here as one.** Lessons 2–5 build the
B-tree page model from scratch, assuming comfortable SQL and no exposure to
pages, fillfactor, splits, or HOT. No evidence supports that assumption — it was
chosen because it is the safe direction to be wrong in: a reader who already
knows the internals loses ten minutes, while a reader who does not would lose the
entire arithmetic argument that lessons 3 through 14 rest on.

**Implications.** Nothing may be taught as "you'll recognise this from X" —
there is no established X. The first genuine evidence of the learner's level will
come from how lessons 2 and 3 land; if the page arithmetic is trivial, compress
lessons 2 and 5 and supersede this record. Because there is no deliverable to
build toward, the topic is judged on whether the reasoning can be reconstructed
from memory rather than on whether a schema ships — so the five reference
documents carry more weight than usual, since they are what actually gets
revisited.
