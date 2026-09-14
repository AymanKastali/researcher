# Mission: SQL Schema Migrations and How Alembic Implements Them

## Why

To be able to look at a migration and say what the database will do when it runs
— which lock it takes, whether it rewrites the table, and what it leaves behind
if it fails halfway — and to still be able to do it in a year. A migration is the
one piece of code that runs once, against production, with no dry run and often
no rollback. The target is being able to reconstruct *why* `ADD COLUMN ... DEFAULT
now()` is dangerous and `ADD COLUMN ... DEFAULT 0` is not, from the documented
mechanism, rather than recalling which one a checklist forbade.

## Success looks like

- Explaining why a one-second `ALTER TABLE` can take a whole site down, naming
  the queue behaviour that causes it, and saying honestly that PostgreSQL's
  manual never states the rule.
- Stating what `NOT VALID` actually removes — the scan, not the lock — and
  therefore which of the two safe-constraint steps still needs a
  `lock_timeout` around it.
- Reciting the zero-downtime `SET NOT NULL` sequence from memory, and naming
  the sentence on the `ALTER TABLE` page that makes each step legal.
- Saying what a merge revision *is* in Alembic — a `down_revision` that is a
  tuple of length ≥ 2 — rather than describing what merges are for.
- Explaining why autogenerate can never detect a column rename, from the shape
  of the algorithm rather than from the documentation's list.
- Naming the one compare-and-swap that is the whole of Alembic's concurrency
  control, where it sits relative to the DDL, and why that ordering makes it
  safe on PostgreSQL and unsafe on MySQL.
- Separating a documented guarantee from a line of source code from a
  practitioner pattern, and refusing to cite PostgreSQL for a rule PostgreSQL
  does not state.

## Constraints

- Long-term retention is the goal, so lessons carry retrieval practice and are
  written to be spaced over days rather than read in one sitting.
- Built in a single pass rather than dripped out. The spacing lives in the study
  advice, not in the delivery schedule.
- Every claim is traceable to a quoted primary source or a labelled
  source-code reference at a named version. Nothing is asserted on recall.
- Alembic has not been used before, so the tool is introduced from zero at
  lesson 9 rather than assumed. The database mechanics come first because they
  are what the tool is a tool *for*.
- The versions taught are **PostgreSQL 16**, **Alembic 1.14.1** and
  **SQLAlchemy 2.0.36**. Where a feature is newer, the release that introduced
  it is named.

## Out of scope

- Benchmarks and timings. No primary source publishes how long a rewrite takes
  on a table of a given size, so no figure is quoted, invented, or implied.
- Other engines in their own right. MySQL and SQLite appear only where the
  contrast decides what is safe, or where they document something PostgreSQL
  does not.
- Deployment platform mechanics — Kubernetes init containers, Helm hooks, CI
  pipeline design. Lesson 16 establishes that none of it has a first-party
  source, and stops there.
- Other migration tools. Flyway, Liquibase, Django and Rails migrations are not
  compared; the mechanism is the subject, and Alembic is the worked example.
