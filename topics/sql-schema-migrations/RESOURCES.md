# SQL Schema Migration Resources

Sources for this topic, split by weight. A vendor's own manual is normative for
that vendor's behaviour; source code is evidence about one released version and
carries no promise; practitioner writing is argument and experience and is
labelled as such, here and on every page that quotes it.

Every entry below was fetched and read while writing
`docs/research/sql-schema-migrations.md`, and the entries marked **re-verified**
were fetched again on 14 September 2026 while building these lessons, because
they carry the load-bearing quotations.

## Knowledge

### PostgreSQL 16 — the primary authority for §1–2

The version taught. Cite the reference page rather than the tutorial: where they
differ, the tutorial is the looser one.

- [`ALTER TABLE`](https://www.postgresql.org/docs/16/sql-altertable.html)
  **Re-verified.** The single most important page in this topic. Use for: the
  Description rule that `ACCESS EXCLUSIVE` is acquired unless explicitly noted
  and that multiple subcommands take the strictest lock; the non-volatile
  `DEFAULT` fast path; `ADD FOREIGN KEY` taking only `SHARE ROW EXCLUSIVE`, on
  both tables; the `NOT VALID` / `VALIDATE CONSTRAINT` rationale; `SET NOT NULL`
  skipping its scan when a valid `CHECK` proves it; and the Note blessing
  `ADD table_constraint_using_index`.
- [`CREATE INDEX`](https://www.postgresql.org/docs/16/sql-createindex.html)
  **Re-verified.** Use for: everything about `CONCURRENTLY` — the two scans, the
  wait for predating transactions, the invalid index left by a failure, the
  unique index that goes on enforcing while being ignored, one concurrent build
  per table, and the `psql \d` … `INVALID` detection route.
- [13.3. Explicit Locking](https://www.postgresql.org/docs/16/explicit-locking.html)
  **Re-verified.** Use for: the definition that the only real difference between
  lock modes is what they conflict with; the "names are historical" note; the
  three modes that matter; the Tip that only `ACCESS EXCLUSIVE` blocks a
  `SELECT`; locks being held to end of transaction; indefinite waiting; and
  §13.3.5 on advisory locks, session versus transaction level.
- [`ALTER TYPE`](https://www.postgresql.org/docs/16/sql-altertype.html) and
  [the PostgreSQL 11 version of the same page](https://www.postgresql.org/docs/11/sql-altertype.html)
  Use for: dating the relaxation of the `ADD VALUE` restriction. The pair is the
  evidence; one page alone cannot show a change.
- [`BEGIN`](https://www.postgresql.org/docs/16/sql-begin.html) and
  [3.4. Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)
  Use for: what a transaction block is, and the implicit `BEGIN`/`COMMIT` around
  every statement. Note what neither page says — see `GLOSSARY.md` on
  transactional DDL.
- [13.6. MVCC Caveats](https://www.postgresql.org/docs/16/mvcc-caveats.html)
  Use for: the table-rewriting forms of `ALTER TABLE` not being MVCC-safe, and
  why that is usually but not always invisible.
- [20.11. Client Connection Defaults](https://www.postgresql.org/docs/16/runtime-config-client.html)
  Use for: `lock_timeout`, the per-attempt scoping that is easy to miss, the
  warning about setting it above `statement_timeout`, and
  `idle_in_transaction_session_timeout`.
- [9.27. System Administration Functions](https://www.postgresql.org/docs/16/functions-admin.html)
  Use for: `pg_advisory_xact_lock` and `pg_try_advisory_xact_lock` definitions.
- [53.26. `pg_index`](https://www.postgresql.org/docs/16/catalog-pg-index.html)
  Use for: `indisvalid`, and its explicit warning that uniqueness is not
  guaranteed either.
- [55.75. `pg_locks`](https://www.postgresql.org/docs/16/view-pg-locks.html)
  Use for: the circumstantial evidence that lock wait queues exist — including
  the "holding **or waiting for**" clause — which is as close as PostgreSQL gets
  to documenting the convoy.
- [55.2.2. Protocol flow](https://www.postgresql.org/docs/16/protocol-flow.html)
  Use for: the only documented description of the failed-transaction state.

### MySQL 8.0 — used for contrast, and for one thing PostgreSQL will not say

- [15.1.1 Atomic DDL](https://dev.mysql.com/doc/refman/8.0/en/atomic-ddl.html)
  Use for: the definition of atomic DDL and, more importantly, the Note directly
  beneath it stating that atomic DDL is *not* transactional DDL. The clearest
  statement of the distinction anywhere.
- [17.12.2 Online DDL Performance and Concurrency](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html)
  **Re-verified.** Use for: the only first-party sentence in any vendor manual
  stating that a pending exclusive metadata lock blocks subsequent transactions,
  plus its three-session worked example. This is the source for the convoy,
  cited by analogy and labelled as such.
- [17.12.1 Online DDL Operations](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html)
  Use for: the per-operation matrix, and the footnote that `INPLACE` foreign-key
  creation requires `foreign_key_checks` disabled.
- [15.1.9 `ALTER TABLE`](https://dev.mysql.com/doc/refman/8.0/en/alter-table.html)
  Use for: `ALGORITHM` and `LOCK` as assertions that fail loudly — the facility
  PostgreSQL has no statement-level equivalent of.
- [15.3.3 Statements That Cause an Implicit Commit](https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html)
  Use for: the `CREATE TEMPORARY TABLE` carve-out that violates atomicity.

### SQLite — why batch mode exists at all

- [ALTER TABLE](https://www.sqlite.org/lang_altertable.html)
  **Re-verified.** Use for: §1's list of the four supported alterations; §4's
  `ADD COLUMN` restrictions on expression defaults and stored generated columns;
  §8's twelve-step procedure and the Caution explaining why renaming first
  corrupts references; §9's explanation that SQLite stores the schema as the
  original text of the `CREATE` statements. §9 is the answer to "why is SQLite's
  `ALTER TABLE` like this", and it is the engine's own answer.
- [Python issue 10740](http://bugs.python.org/issue10740)
  Cited only because Alembic's own source comment cites it, to explain why
  SQLite is marked non-transactional despite supporting transactional DDL.

### Alembic — documentation, with a caveat that applies to all of it

There is **no published Alembic 1.14 documentation**.
`https://alembic.sqlalchemy.org/en/rel_1_14/` is not published and
`/en/release-1.14.0/` returns HTTP 404. Every documentation quotation in this
topic is therefore from the current published docs, checked against 1.14.1
source. Where the two disagree, the lessons prefer the source and say so.

- [Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
  **Re-verified.** Use for: orientation only — what a revision file is, how
  `down_revision` chains them, and the `alembic_version` table being created on
  first run. Lesson 9's backbone.
- [Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
  Use for: the published "can detect" / "can not detect" lists. Read it against
  lesson 12, which shows both lists are wrong for 1.14.1 in opposite directions.
- [Working with Branches](https://alembic.sqlalchemy.org/en/latest/branches.html)
  Use for: branch labels, `heads` versus `head`, and the `<branchname>@head`
  addressing syntax.
- [Generating SQL Scripts ("Offline Mode")](https://alembic.sqlalchemy.org/en/latest/offline.html)
  Use for: the stated purpose of `--sql`, the one-paragraph statement of its
  limitations, and the `start:end` syntax being offline-only.
- [Running "Batch" Migrations](https://alembic.sqlalchemy.org/en/latest/batch.html)
  Use for: `recreate="auto"`, the foreign-key warning, `copy_from` for offline
  batch, and the candid admission that nothing is automated for dependent
  foreign keys.
- [Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
  Use for: the at-head deploy gate. Note that `--check-heads` arrived in 1.17.1
  and is not available on the version taught.

### Alembic and SQLAlchemy source, read on disk

- **Alembic 1.14.1** and **SQLAlchemy 2.0.36**, installed with
  `uv pip install --target ./alembic-src "alembic==1.14.1" "SQLAlchemy==2.0.36"`
  and read as files. Version established by
  `alembic/__init__.py`: `__version__ = "1.14.1"`.
  Every `file.py:NNN` citation in lessons 10–16 refers to that tree, and each
  was re-checked on 14 September 2026 before being quoted.
  Use for: everything the documentation does not state, which in this topic is
  most of the mechanism.

### First-party, but not documentation

Statements by Alembic's author on the project's own trackers. Authoritative
about *intent*, carrying no versioned guarantee. Quoted in lesson 16 and
labelled there every time.

- [Issue #633 — "Is multiple alembic upgrades ok to run concurrent?"](https://github.com/sqlalchemy/alembic/issues/633)
  Use for: "the UPDATE is performed using a standard compare and swap
  technique", and the maintainer declining to support the concurrent use case.
- [Discussion #1438](https://github.com/sqlalchemy/alembic/discussions/1438)
  Use for: the clearest first-party statement that the migrating process should
  be separate from the request-serving one — which is the *only* support the
  "migrate as a separate step" practice has anywhere.

### Practitioner writing

Argued from experience rather than normative. Used only where no vendor source
exists, and never quoted as though it were one.

- [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html)
  Danilo Sato, martinfowler.com, 13 May 2014. Use for: the name and canonical
  description of expand/contract, the three phases in the author's own words,
  the database-refactoring application, and the warning about skipping the
  contract phase. Credited by Sato to Joshua Kerievsky's 2006 work. **No vendor
  manual documents this pattern** — see lesson 8.
- [PgBouncer — Features](https://www.pgbouncer.org/features.html)
  First-party for PgBouncer, not for PostgreSQL. Use for: session-level advisory
  locks being listed `Never` under transaction pooling, which is the concrete
  reason to prefer `pg_advisory_xact_lock`. The PostgreSQL manual does not
  discuss pooling at all.

## Wisdom (Communities)

- [pgsql-general mailing list](https://www.postgresql.org/list/pgsql-general/)
  The project's own list, archived publicly and readable without subscribing.
  Use for: asking whether a specific `ALTER TABLE` will rewrite, which is
  exactly the kind of question the manual answers in general and not in
  particular. The archive search is the better first move.
- [PostgreSQL Slack and other community channels](https://www.postgresql.org/community/)
  Linked from the project's own community page rather than assumed — the list of
  what is official changes. Use for: fast, low-stakes questions.
- [sqlalchemy/alembic Discussions](https://github.com/sqlalchemy/alembic/discussions)
  Where the maintainer actually answers. Use for: Alembic behaviour questions.
  Reading the archive is worth more than posting: discussion #1438 in the list
  above is a better answer than most blog posts on the same question.

No preference for or against joining communities has been stated. Record one
here if it is.

## Gaps

Areas the mission touches where the public record is thin. These are gaps in the
sources, not omissions from this workspace, and lesson 17 makes them the object
of study rather than hiding them.

- **PostgreSQL never states that DDL is transactional.** The property is
  established negatively, by the enumeration of statements that cannot run
  inside a transaction block. Sound, but an inference.
- **PostgreSQL never documents the lock-queue convoy** — the single most
  consequential operational fact in the topic. MySQL documents its equivalent;
  the lessons cite MySQL and say plainly that it is an analogy.
- **PostgreSQL 16 does not say whether `ADD COLUMN` with an identity or
  generated-stored specification rewrites the table.** The rewrite discussion
  covers volatile defaults and type changes and stops.
- **Expand/contract has no vendor owner.** Its primitives are all documented;
  the pattern is not.
- **No Alembic 1.14 documentation exists online.** Five specific
  documentation/source disagreements are recorded in lesson 17.
- **No first-party source describes deploying migrations** — not init
  containers, not Job ordering, not Helm hooks. One maintainer comment on a
  discussion tracker is the entire evidential basis for the standard practice.
- **No primary source publishes timings.** How long a rewrite takes on a table
  of a given size is not documented by anyone, so no number appears anywhere in
  this topic.
