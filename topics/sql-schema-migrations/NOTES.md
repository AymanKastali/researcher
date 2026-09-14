# Notes

Working notes and stated preferences for this topic.

## Learner preferences

- **Sources over assertion.** Every substantive claim carries a quotation with
  attribution, and the grades of evidence — documented guarantee, source-code
  fact, maintainer statement, practitioner pattern — are kept visibly distinct
  on the page rather than merged into one confident voice.
- **Batch, don't drip.** The whole topic is built in one pass. Spacing is advice
  inside the lessons, not a delivery schedule.
- **Dark only, mobile first.** Every page is read at phone width before it
  ships. The lock/rewrite table in lesson 4 and the dispatch chain in lesson 13
  are the two that need checking there.

## Stated starting point

Answered at the start of the build: the mission is **durable understanding**
rather than a migration that needs shipping; Alembic has **never been used**;
weighting is **even, database first**. Recorded as learning record 0001, which is
where the consequences for lesson order are written down.

## On code in this topic

The repo rule is that illustrative code is Python and quoted excerpts keep their
original language. This topic strains that rule harder than the previous two, so
the resolution is recorded here.

- **SQL is the subject matter, not illustration.** `ALTER TABLE ... ADD
  CONSTRAINT ... NOT VALID` cannot be shown in Python. SQL appears in two forms
  and they are never mixed: syntax and examples quoted from a manual sit in
  `.excerpt` with their source; sequences written for a lesson sit in `.code`
  marked both `SQL` and "Written for this lesson".
- **Python appears where the subject genuinely is Python**: the revision file in
  lesson 9, the `env.py` advisory-lock sketch in lesson 16, and the small
  worked demonstrations. All of it carries `.code-illustrative`.
- **Alembic's own source is quoted, not illustrated.** Every source block in
  lessons 10–16 is a quotation from the installed 1.14.1 tree, carries its
  `file.py:NNN`, and sits in `.excerpt` or in a `.code` block whose meta line
  names the file rather than saying "written for this lesson". Nothing authored
  here is allowed to look like Alembic's code.

## Where this topic came from

Built from `docs/research/sql-schema-migrations.md` in this repo — a 2,048-line
study guide whose sources were fetched and read while writing it. The lessons
add no claims to that document; they sequence it for learning and quote the same
primary sources directly. Its §6, "What could not be verified", becomes lesson
17 rather than being quietly dropped, because the list of things the sources
refuse to say is the most transferable part of the research.

## Sourcing checked beyond the research document

The research document was **not** taken on trust. Before any lesson was written,
its load-bearing sources were re-fetched and re-read on 14 September 2026:

- **Five documentation pages were re-fetched and checked quotation by
  quotation** — PostgreSQL 16 `ALTER TABLE`, `CREATE INDEX` and 13.3 Explicit
  Locking; SQLite `ALTER TABLE`; the Alembic Tutorial. Every quotation the
  lessons use from those pages was confirmed verbatim. No corrections were
  needed.
- **Alembic 1.14.1 and SQLAlchemy 2.0.36 were installed and read on disk**, with
  `uv pip install --target`, exactly as the research document describes.
  `alembic/__init__.py` confirms `__version__ = "1.14.1"`. Every `file.py:NNN`
  citation used in a lesson was re-checked against that tree — the
  `run_migrations` block, the `begin_transaction` truth-table lines, the six
  dialect `transactional_ddl` values, `_update_version`'s rowcount guard,
  `is_merge_point`, `_calc_temp_name`, and the nine comparator registrations.
  All matched, to the line.
- **The two arguments from absence were reproduced, not quoted.**
  `grep -c CheckConstraint alembic/autogenerate/compare.py` returns **0**,
  confirming that CHECK-constraint autogenerate does not exist in 1.14.1 despite
  the published documentation listing it. The locking grep returns **35** hits
  and **0** after excluding the English word "block", confirming Alembic has no
  mutual exclusion of any kind. These two are the topic's most unusual claims
  and are the ones a future session is most likely to doubt; they were rerun so
  the lessons could state them flatly.

## Teaching decisions made

- **The database comes before the tool, and the tool is introduced from zero.**
  Lessons 1–8 never mention Alembic. Lesson 9 then starts at "what is a revision
  file", because the learner has never used it. The alternative — teach the tool
  and explain the database as needed — produces someone who can write a
  migration and cannot predict what it does.
- **Lesson 5 is the hinge and is deliberately short.** The convoy is the single
  most consequential operational fact in the topic, and it is the one
  PostgreSQL will not state. Giving it its own lesson, rather than an aside
  inside the lock lesson, is the sequencing decision most likely to make it
  stick — and it lets the sourcing problem be taught rather than papered over.
- **Lesson 3 teaches the conflict table before any operation is named.** "A lock
  mode is nothing but its conflict set" is one sentence, and every later lesson
  is unreadable without it.
- **`NOT VALID` gets a lesson, not a row in a table.** It is the one place where
  a reader reliably forms the wrong model — "it makes the operation cheap" — and
  the correction, that it removes the scan and not the lock, is exactly the kind
  of distinction this workspace exists to preserve.
- **Autogenerate's limits are taught as a proof, not a list.** Lesson 12 shows
  the three set operations in `_compare_columns` and lets the reader conclude
  that rename detection is impossible, rather than reciting the documentation's
  "can not detect" list — which is, in any case, wrong in both directions for
  1.14.1.
- **No timing numbers appear anywhere**, because no primary source publishes
  one. Where a reader expects "how long does a rewrite take", the lesson says
  that nobody documents it. This is the most likely place for a future session
  to quietly regress.
- **The evidence grades are taught, not just used.** Lesson 17 makes the grading
  itself the object of study. Without it the topic teaches conclusions; with it
  the topic teaches how to check them, which is the part that survives
  PostgreSQL 17 and Alembic 1.20.

## Open questions for a future session

- **Alembic 1.14.1 is pinned, and that pin is doing real work.** Five
  documentation/source disagreements in lesson 17 are version gaps rather than
  errors. If the learner ever runs a different version, lessons 10–16 need
  re-checking against that tree — every line number, and specifically: CHECK
  autogenerate (added 1.19.0, default-off since 1.19.2), the unnamed-CHECK batch
  warning (added 1.20), and `alembic current --check-heads` (added 1.17.1, and
  therefore taught as *unavailable*).
- **PostgreSQL 16 is the version taught, and 17 and 18 both exist.** Nothing in
  §1–2 was re-checked against a later release. The `ALTER TABLE` rewrite rules
  are the ones most worth re-reading when this is revisited.
- **The `ADD COLUMN` identity/generated-stored rewrite question is genuinely
  open.** PostgreSQL 16 does not state it either way, and the lesson 4 table
  marks the cell undocumented rather than guessing. A source that settles it
  would be worth adding.
- **No real schema is in hand.** The mission was answered as durable
  understanding with no migration pending. If a production change appears,
  revise `MISSION.md` and write a learning record: lessons 4, 6 and 8 would
  probably move much earlier, and a decision-procedure reference document would
  earn its place.
- **The learner's PostgreSQL depth is assumed from the neighbouring topic, not
  established here.** Lessons 1–5 assume comfort with transactions and no
  knowledge of lock modes. If that is too low, lesson 1 is the one to compress.
