# Starting point: the database is the subject, the tool is new

The learner's stated position at the start of this topic: the mission is
**durable understanding** rather than a migration that needs shipping; **Alembic
has never been used**; and the two halves of the research document should be
weighted **evenly, with the database mechanics first**.

That combination is unusual and it decides the lesson order. Because there is no
deliverable, the lessons are judged on whether the mechanism can be
reconstructed from memory rather than on whether a migration ships — a
storage-strength goal, so lessons carry retrieval practice and are written to be
spaced. Because Alembic is genuinely new, nothing may be taught as "you will
recognise this from your migration files": lesson 9 has to establish what a
revision, a `down_revision` and `alembic_version` *are* before lesson 10 can
explain where the version write sits. And because the database comes first,
lessons 1–8 never mention the tool at all.

**Implications.** The expensive material — the revision graph, the autogenerate
comparators, the operation dispatch chain — sits behind an orientation lesson
that the research document did not need and therefore did not contain. Lesson 9
is the one lesson in this topic built mostly from the Alembic Tutorial rather
than from the research; it was sourced separately and its quotations were fetched
and verified for that purpose.

**Not yet established.** PostgreSQL depth is assumed rather than evidenced:
lessons 1–5 assume comfort with transactions and no prior knowledge of lock
modes. Nothing has been confirmed by evidence yet, so this record states the
assumption *as* an assumption, and lesson 1 is the one to compress if it turns
out to be pitched low.
