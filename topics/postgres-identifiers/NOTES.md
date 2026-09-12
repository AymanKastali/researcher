# Notes

Working notes and stated preferences for this topic.

## Learner preferences

- **Sources over assertion.** Every substantive claim carries a quotation with
  attribution, and the three grades of evidence — documented guarantee, source
  code, derived arithmetic — are kept visibly distinct on the page, never merged
  into one confident voice.
- **Batch, don't drip.** The whole topic is built in one pass. Spacing is advice
  inside the lessons, not a delivery schedule.
- **Dark only, mobile first.** Every page is read at phone width before it ships.
  The arithmetic tables in lessons 2 and 3 are the ones that need checking there.

## On code in this topic

The repo rule is that illustrative code is Python and quoted excerpts keep their
original language. This topic has a wrinkle worth recording, because a later
session will otherwise think the rule was broken.

- **Python** is used for anything computed or demonstrated: the leaf-page
  arithmetic, the UUIDv7 bit decomposition, the entropy comparison, and the
  demonstration that an increment-by-one counter determines the next value. All
  of it carries `.code-illustrative`.
- **SQL is the subject matter, not illustration.** `BIGINT GENERATED ALWAYS AS
  IDENTITY` cannot be shown in Python. SQL appears in two forms and they are
  never mixed: quoted syntax and quoted examples sit in `.excerpt` with their
  source; schemas written for a lesson sit in `.code` marked both
  `SQL` and "Written for this lesson", so nothing authored here can be mistaken
  for something the manual says.
- **C and Scala appear only inside quotations** — `UUID_LEN`, `BTMaxItemSize`,
  `twepoch` — and are never used to illustrate anything.

## Where this topic came from

Built from `docs/research/postgres-identifier-strategies.md` in this repo — a
1,769-line study guide whose sources were fetched and read while writing it. The
lessons add no claims to that document; they sequence it for learning and quote
the same primary sources directly. Its §8, "What could not be verified", becomes
lesson 15 rather than being quietly dropped, because the list of things the
sources refuse to say is the most transferable part of the research.

## Teaching decisions made

- **The mechanics come before the candidates.** Lessons 2–5 build the page model
  before a single identifier format is named. The alternative ordering — compare
  the candidates, then explain why — produces fluency without storage strength,
  because the comparison table is memorable and the reasoning behind it is not.
  Anyone can recall "UUIDv7 is better than v4"; the mission is to reconstruct
  *why* from the split behaviour.
- **Lesson 3 is the hinge and is deliberately short.** The rightmost-page
  fastpath is the single most important fact in the topic and it is a
  source-code fact, not a documented one. Giving it a lesson of its own, rather
  than a section inside a longer lesson on storage, is the sequencing decision
  most likely to make the argument stick.
- **Lesson 4 exists to disarm imported advice.** "There is no clustered index" is
  one sentence, but it is the sentence that invalidates most of what is written
  about this subject, so it gets a lesson rather than an aside.
- **The ULID/RFC conflict (lesson 11) is taught as a finding, not a verdict.**
  Both specifications are individually reasonable; the problem only exists when
  you read them against each other. That is a skill worth transferring, and it
  is lost if the lesson just says "don't use ULID".
- **No benchmark numbers appear anywhere**, because no primary source publishes
  one. Where a reader expects a number and there is none, the lesson says so.
  This is the most likely place for a future session to quietly regress.
- **The evidence grades are taught, not just used.** Lesson 15 makes the grading
  itself the object of study. Without it the topic teaches conclusions; with it
  the topic teaches how to check them, which is the part that survives
  PostgreSQL 19.

## Sourcing checked beyond the research document

Three things were verified live while building the lessons rather than taken on
trust from `docs/research/postgres-identifier-strategies.md`:

- **The `pageinspect` validation now uses both examples the manual prints**, not
  one. `bt_multi_page_stats('pg_proc_oid_index', 5, 2)` gives 367 items and 808
  bytes free; `bt_page_stats('pg_cast_oid_index', 1)` gives 224 and 3668. The
  model predicts both to the byte, and the second page is only ~55% full, so it
  is not fitted to a single packed case. The research document cited only the
  first. This is a strengthening, not a correction.
- **Community resources were checked against the project's own community page**
  on 12 September 2026. An earlier draft of `RESOURCES.md` listed a Postgres
  Slack and Discord; neither is listed by the project, so both were removed
  rather than asserted. The IETF UUIDREV working group is **concluded**, so it is
  listed as an archive to read rather than a live community.
- **Two computed examples were run, not asserted.** The UUIDv7 decomposition in
  lesson 8 decodes to 2023-01-02 04:26:40.637+00, which is exactly the timestamp
  the `pg_uuidv7` README fed in to produce that prefix. The ULID successor in
  lesson 11 reproduces the ULID specification's own worked example. A first draft
  of the lesson 8 figure was wrong and was caught by running it.

## Open questions for a future session

- **The mission was stated tersely** — "i want to learn it", with no schema in
  hand and no stated starting point. `MISSION.md` was therefore written around
  durable understanding rather than a deliverable, following the research
  document's own scope. If a real schema decision appears, revise the mission and
  write a learning record: the lesson order would probably change, with the
  decision ladder (lesson 14) moving much earlier.
- **The starting point is assumed, not established.** Lessons 2–5 build the page
  model from scratch on the assumption of comfortable SQL and no internals. If
  that is too low, lessons 2 and 5 are the ones to compress. Nothing has been
  confirmed by evidence yet, so learning record 0001 records the assumption as an
  assumption.
- **PostgreSQL 18.6 is the version taught.** When 19 ships, the feature ledger in
  lesson 6 and the reference document built from it need re-checking — and so
  does every source-code citation, since a header file can change without a
  release note.
- **The `uuid_extract_timestamp()` introducing version was never established.**
  It is present in 18; the PG17 release notes were not fetched. Worth resolving
  before anyone relies on it against an older server.
