# Starting point: the phrase, not the mechanism

The learner's stated prior knowledge on this topic is "roughly heard of the
idea" — the phrase *idempotency key* means "retrying is safe", with nothing
behind it. No prior exposure to the server-side implementation, the race at the
claim, or the vendor landscape.

The mission is deep backend fundamentals with no immediate deliverable:
long-term retention of the distributed-systems reasoning itself, from the 1983
RPC formulation forward. This is a storage-strength goal rather than a
fluency-strength one, so lessons carry retrieval practice and are written to be
spaced over days.

**Implications.** Lesson 1 can assume no HTTP-semantics background and has to
start at what "idempotent" means at all, including the algebraic origin. Nothing
may be taught as "you'll recognise this from X" — there is no X yet. Because
there is no deliverable to build toward, the lessons are judged on whether the
reasoning can be reconstructed from memory, not on whether an implementation
compiles — so the reference documents carry more weight than usual, since they
are what gets revisited.
