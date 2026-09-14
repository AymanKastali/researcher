# SQL Schema Migration Glossary

The vocabulary of changing a schema safely: what the engine guarantees, the
physical work an `ALTER TABLE` does or avoids, the locks that decide who waits,
the tool's own model, and the grades of evidence this topic keeps apart. Where a
term has a quoted definition in a vendor manual, that quotation is the authority
and this entry is its compression.

## What the engine guarantees

**DDL**:
Data Definition Language — the statements that change the schema rather than the
rows: `CREATE`, `ALTER`, `DROP`. The distinction matters here only because
engines treat DDL and DML differently inside a transaction.
_Avoid_: Schema statement, structural query

**Transactional DDL**:
The property that DDL participates in a transaction block, so several schema
changes commit or roll back together. PostgreSQL has it; **PostgreSQL never says
so**, and the property is established by the enumeration of statements that
cannot run inside a transaction block.
_Avoid_: Rollback-able DDL, safe DDL, transactional schema

**Atomic DDL**:
MySQL 8.0's crash atomicity for **one** statement: dictionary update, engine
work and binary-log write "either committed […] or […] rolled back, even if the
server halts during the operation"
([15.1.1](https://dev.mysql.com/doc/refman/8.0/en/atomic-ddl.html)). Explicitly
*not* transactional DDL, in MySQL's own Note. InnoDB only.
_Avoid_: Transactional DDL (the manual's own warning), atomic migration

**Implicit commit**:
MySQL's behaviour whereby a DDL statement "implicitly end[s] any transaction that
is active in the current session, as if you had done a COMMIT before executing
the statement". The mechanical reason two MySQL DDL statements cannot be rolled
back together.
_Avoid_: Autocommit (means something different), silent commit

**Transaction block**:
What `BEGIN` opens: "all statements after a BEGIN command will be executed in a
single transaction until an explicit COMMIT or ROLLBACK is given"
([`BEGIN`](https://www.postgresql.org/docs/16/sql-begin.html)). Without one,
every statement gets its own implicit `BEGIN`/`COMMIT`.
_Avoid_: Transaction scope, the transaction

**MVCC-unsafe DDL**:
`TRUNCATE` and the table-rewriting forms of `ALTER TABLE`, which after committing
make the table "appear empty to concurrent transactions, if they are using a
snapshot taken before the DDL command committed"
([13.6](https://www.postgresql.org/docs/16/mvcc-caveats.html)).
_Avoid_: Unsafe DDL, non-transactional ALTER

## The physical work

**Table rewrite**:
Rewriting the entire table and all its indexes into new files. Triggered by a
volatile `DEFAULT` on `ADD COLUMN` and by a type change that is not binary
coercible. The expensive outcome, and the one that cannot be made safe by care.
_Avoid_: Table copy, full ALTER, repack

**Table scan**:
Reading every row to verify something, without rewriting. What `ADD CHECK` and
`SET NOT NULL` do. Cheaper than a rewrite and still long — and the thing
`NOT VALID` removes.
_Avoid_: Full scan, validation pass, check

**Metadata-only change**:
A change recorded in the catalog with no row touched at all. `ADD COLUMN` with
no default or a non-volatile one. Still takes `ACCESS EXCLUSIVE`, but holds it
briefly.
_Avoid_: Instant change, free change, cheap ALTER

**Non-volatile default**:
An `IMMUTABLE` or `STABLE` default expression, whose value is "evaluated at the
time of the statement and the result stored in the table's metadata"
([`ALTER TABLE`](https://www.postgresql.org/docs/16/sql-altertable.html)). The
criterion for the no-rewrite fast path — **broader than "a constant"**, which is
the tutorial's looser word. Arrived in PostgreSQL 11.
_Avoid_: Constant default, static default, literal default

**Binary coercible**:
The relation between two types that lets `ALTER COLUMN ... TYPE` skip the
rewrite, because the stored representation need not change.
_Avoid_: Compatible type, same-size type

**Invalid index**:
The index left behind when `CREATE INDEX CONCURRENTLY` fails: "ignored for
querying purposes […] however it will still consume update overhead"
([`CREATE INDEX`](https://www.postgresql.org/docs/16/sql-createindex.html)). If
unique, it also goes on rejecting duplicates. Reported by `psql \d` as `INVALID`
and by `pg_index.indisvalid` as false.
_Avoid_: Broken index, partial index (means something else), failed index

**Online DDL**:
MySQL's name for operations that permit concurrent DML, exposed as a five-column
matrix per operation. **"Online" does not mean lock-free**: `LOCK=NONE` governs
the execution phase, not the brief exclusive metadata lock at commit.
_Avoid_: Zero-downtime DDL, non-blocking ALTER

**`ALGORITHM` / `LOCK` clause**:
MySQL's statement-level **assertions**: naming one "requires the operation to use
the specified algorithm […] or fail with an error otherwise"
([15.1.9](https://dev.mysql.com/doc/refman/8.0/en/alter-table.html)). They turn a
silent downgrade into a loud failure. PostgreSQL has no equivalent.
_Avoid_: Hint, option, preference

## Locks

**Lock mode**:
A named member of the conflict table. "The only real difference between one lock
mode and another is the set of lock modes with which each conflicts"
([13.3.1](https://www.postgresql.org/docs/16/explicit-locking.html)) — so a mode
means nothing except who it excludes.
_Avoid_: Lock level, lock strength, lock type

**`ACCESS EXCLUSIVE`**:
Conflicts with every mode; "guarantees that the holder is the only transaction
accessing the table in any way". The default for `ALTER TABLE` subforms — the
page says silence means this mode, so silence is not ambiguity. **The only mode
that blocks a plain `SELECT`.**
_Avoid_: Exclusive lock, write lock, table lock

**`SHARE ROW EXCLUSIVE`**:
Conflicts with `ROW EXCLUSIVE` and above; "protects a table against concurrent
data changes, and is self-exclusive". Permits reads, blocks every write. What
`ADD FOREIGN KEY` takes — **on both tables**.
_Avoid_: Row lock (it is table-level), write-blocking lock

**`SHARE UPDATE EXCLUSIVE`**:
Conflicts with schema changes and `VACUUM`, not with reads or writes. What
`VALIDATE CONSTRAINT` and `CREATE INDEX CONCURRENTLY` take. The mode that makes
the two-step patterns worth doing.
_Avoid_: Weak lock, light lock, concurrent lock

**Lock queue convoy**:
A waiting `ACCESS EXCLUSIVE` request blocking the requests queued behind it, so
that `SELECT`s stall behind DDL that is itself stalled — even though `SELECT`
does not conflict with `SELECT`. **PostgreSQL never documents this.** MySQL
states the equivalent outright: "a pending exclusive metadata lock requested by
an online DDL operation blocks subsequent transactions on the table"
([17.12.2](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html)).
_Avoid_: Lock storm, pile-up, blocking chain — and never cite PostgreSQL for it

**`lock_timeout`**:
"Abort any statement that waits longer than the specified amount of time while
attempting to acquire a lock […] The time limit applies **separately to each lock
acquisition attempt**"
([20.11.2](https://www.postgresql.org/docs/16/runtime-config-client.html)). The
per-attempt scoping means it does not bound a multi-relation statement.
_Avoid_: Statement timeout (a different setting that pre-empts this one)

**Advisory lock**:
A lock "that ha[s] application-defined meanings […] because the system does not
enforce their use"
([13.3.5](https://www.postgresql.org/docs/16/explicit-locking.html)). The
mechanism you must supply yourself if you want two migration runs serialised —
preferably the `_xact_` form, which a transaction pooler will not break.
_Avoid_: Application lock, mutex, named lock

## The two-step patterns

**`NOT VALID`**:
The option that makes `ADD CONSTRAINT` skip its verification scan and commit
immediately. **It removes the scan, not the lock** — `ADD CHECK ... NOT VALID`
still takes `ACCESS EXCLUSIVE`. It is safe because the lock is held *briefly*.
_Avoid_: Deferred constraint (means something else), unvalidated constraint

**`VALIDATE CONSTRAINT`**:
The second step, which verifies pre-existing rows under only
`SHARE UPDATE EXCLUSIVE`, because "it knows that other transactions will be
enforcing the constraint for rows that they insert or update".
_Avoid_: Validation, checking, confirming

**Expand/contract**:
Reaching a target schema through individually-safe steps, at the cost of a period
where both shapes are live. "A pattern to implement backward-incompatible changes
to an interface in a safe manner, by breaking the change into three distinct
phases: expand, migrate, and contract" — Danilo Sato,
[Parallel Change](https://martinfowler.com/bliki/ParallelChange.html), 2014.
**No vendor manual names or endorses it**; its primitives are all documented, the
pattern is not.
_Avoid_: Zero-downtime migration, blue-green schema, safe rename

**Contract phase**:
The deletion at the end, and the half practitioners skip: "If the contract phase
is not executed you might end up in a worse state than you started, therefore you
need discipline to finish the transition successfully" (Sato).
_Avoid_: Cleanup, tidy-up, phase three

## Alembic's model

**Revision**:
One migration script, identified by a generated id, containing `upgrade()` and
`downgrade()`. Ids may not contain `@`, `-` or `+`, because those three
characters are reserved for the addressing syntax.
_Avoid_: Migration file, version, changeset

**`down_revision`**:
The pointer to the revision that must run before this one. "This is how Alembic
knows the correct order in which to apply migrations"
([Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)). A
`down_revision` of `None` marks a base.
_Avoid_: Parent, previous, predecessor

**Head**:
A revision nothing points down to — the end of a line. Plural when branches are
unmerged, which is why `alembic_version` may hold more than one row.
_Avoid_: Latest, tip, current

**Merge point**:
A revision whose `down_revision` is a tuple of length ≥ 2. There is no merge
type and no merge flag: `return len(self._versioned_down_revisions) > 1`
(`alembic/script/revision.py:1702`). That is the entire definition.
_Avoid_: Merge migration, join, merge commit

**`dependencies`**:
Revisions that must run before this one **without** being its lineage. They
order the run; they do not define ancestry, do not make a revision a merge
point, and never collapse rows in `alembic_version`.
_Avoid_: Dependencies as parents, soft down_revision

**`alembic_version`**:
The one-column table holding the current head or heads.
`version_num VARCHAR(32) NOT NULL`, primary key `<table>_pkc`. The column name is
a documented contract; **the width 32 is a bare literal** with no named constant.
_Avoid_: Version table (fine in prose), migration log, schema_version

**Compare-and-swap**:
`UPDATE alembic_version SET version_num='<to>' WHERE version_num='<from>'`,
followed by a rowcount assertion that exactly one row matched. The whole of
Alembic's concurrency control, and it runs **after** the DDL.
_Avoid_: Lock, guard, mutex — it is none of those

**Autogenerate**:
Comparing model metadata against a reflected database and emitting operations
for the difference. Its detection surface is exactly nine comparator functions in
one file, so anything outside them is invisible by construction.
_Avoid_: Diffing, schema sync, introspection

**Comparator**:
A function registered on the autogenerate dispatcher for `schema`, `table` or
`column`. Nine exist in 1.14.1; **no dialect registers one**.
_Avoid_: Detector, checker, rule

**Offline mode**:
`--sql`: the statement is compiled against the configured dialect and written to
a buffer, never executed. A **compiler, not an executor** — it can tell you a
migration renders, never that it works.
_Avoid_: Dry run, preview, SQL export

**Batch mode**:
The move-and-copy wrapper that gives SQLite the `ALTER TABLE` forms it lacks:
create new → copy → drop old → rename new into old. Exists because SQLite stores
its schema as the original `CREATE` statement text.
_Avoid_: Table recreate, SQLite mode, workaround

## The grades of evidence

**Documented guarantee**:
A claim quoted from a vendor manual for a named version. The only grade that may
be stated without qualification — and even then, only for that version.
_Avoid_: The docs say, officially, canonically

**Source-code fact**:
A claim read from Alembic 1.14.1 or SQLAlchemy 2.0.36 on disk because the
documentation is silent or wrong. Weaker: it describes one released version and
may change without a release note.
_Avoid_: Internally, under the hood, actually

**Maintainer statement**:
A first-party comment on the project's own tracker. Authoritative about
*intent*, carrying no versioned guarantee, and not covered by any test.
_Avoid_: The maintainers say, officially supported

**Practitioner pattern**:
A named technique with an attributable author and no vendor owner.
Expand/contract is the only one this topic teaches, and it is labelled every
time.
_Avoid_: Best practice, the standard approach, industry standard

**Argument from absence**:
A claim that a source says nothing, established by exhaustive search with a
working control group — the method used for the convoy, and for Alembic having
no concurrency material at all. Sound only when the search is shown.
_Avoid_: There's nothing about it, undocumented (without showing the search)

## Notes on usage

- **Say "rewrite" or "scan", never "slow".** They are different costs with
  different fixes: a scan can be removed with `NOT VALID`, a rewrite cannot be
  removed at all. Collapsing them into "slow migration" loses the only
  distinction that decides what to do.
- **Never say `NOT VALID` "avoids the lock".** It avoids the *scan*. Only
  `ADD FOREIGN KEY` gets a weaker lock, and that is a separate documented fact
  about a different subform.
- **Say "blocks writes on both tables" about `ADD FOREIGN KEY`.** Naming only
  the table in the statement is the mistake that makes this operation surprising
  in production.
- **Never cite PostgreSQL for the convoy.** Cite MySQL and say it is an
  analogy. This is the place where confident sourcing is most tempting and most
  wrong.
- **"Online" is MySQL's word and it is qualified.** Repeating it about
  PostgreSQL imports a promise no PostgreSQL page makes.
- **Distinguish "atomic" from "transactional".** MySQL's own manual puts the
  distinction in a Note box, because conflating them is the error that loses
  data on a five-statement MySQL migration.
- **Say "compare-and-swap", not "lock", about `alembic_version`.** It detects a
  concurrent run after the fact; it does not prevent one, and on a
  non-transactional-DDL backend it does not even clean up after one.
- **A migration that "passed in `--sql` mode" has been compiled, not tested.**
  Saying it was checked implies an execution that never happened.
