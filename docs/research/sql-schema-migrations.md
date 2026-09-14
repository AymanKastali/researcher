# SQL Schema Migrations and How Alembic Implements Them

A study guide, built from primary sources.

**Scope.** This is an educational deep dive for a backend engineer who already
knows what a migration file looks like and wants to know what the database is
actually doing when one runs, which operations are safe to run against a live
production table and why, and how Alembic's own machinery implements and exposes
all of it. It moves from DDL transactionality at the engine level, through lock
modes and table rewrites and the non-blocking forms of each common operation, to
Alembic's revision graph, autogenerate comparators and operation dispatch, and
finally to the three places the tool's guarantees run out: offline mode, batch
mode, and concurrent deploys.

The targets are **PostgreSQL 16**, **Alembic 1.14**, and **SQLAlchemy 2.0**, with
**MySQL 8.0** used for contrast wherever its behaviour differs in a way that
changes what is safe. All Alembic internals were read from an installed
**1.14.1** tree alongside **SQLAlchemy 2.0.36**.

**Sourcing.** Every substantive claim below is tied to a source that was fetched
and read while writing this document. Database behaviour cites the vendor
documentation section; Alembic internals cite the file, class or function, and
line numbers, quoted from source rather than from memory. Documented guarantees
are kept visibly separate from current implementation detail — the distinction
matters here more than usual, because several of Alembic's most load-bearing
behaviours are neither documented nor promised. Where the documentation and the
source disagree, the source is preferred and the disagreement is stated. Anything
that could not be verified is marked as such, here and in
[§6](#6-what-could-not-be-verified).

One caveat applies to every Alembic documentation quote in this document.
`https://alembic.sqlalchemy.org/en/rel_1_14/` is not published, and
`/en/release-1.14.0/` returns HTTP 404; there is no way to read 1.14-era
documentation online. Every documentation quote below is therefore from the
current published docs — **1.20.0** at the time of writing — checked against
**1.14.1** source. Two of the documentation/source disagreements recorded here
are that version gap rather than an error.

---

## Contents

1. [The Mechanics of a Migration](#1-the-mechanics-of-a-migration)
2. [Running Migrations Safely in Production](#2-running-migrations-safely-in-production)
3. [How Alembic Implements Migrations](#3-how-alembic-implements-migrations)
4. [Alembic in Practice](#4-alembic-in-practice)
5. [Sources](#5-sources)
6. [What could not be verified](#6-what-could-not-be-verified)

---

## 1. The Mechanics of a Migration

### 1.1 There is no such sentence as "PostgreSQL has transactional DDL"

Start with the negative result, because it shapes everything after it. **The PostgreSQL 16
manual never affirmatively states that DDL is transactional.** There is no sentence to quote.
What the manual does is define a transaction block without carving DDL out of it —

> BEGIN initiates a transaction block, that is, all statements after a BEGIN command will be
> executed in a single transaction until an explicit COMMIT or ROLLBACK is given.

— [BEGIN, Description](https://www.postgresql.org/docs/16/sql-begin.html) — and then enumerate,
across a dozen reference pages, the specific statements that *cannot* run inside one. The
property is established by its exceptions. That enumeration would be pointless if DDL in
general were not transactional, so the inference is safe; but it is an inference, and worth
labelling as one.

The tutorial states the autocommit half plainly:

> PostgreSQL actually treats every SQL statement as being executed within a transaction. If you
> do not issue a BEGIN command, then each individual statement has an implicit BEGIN and (if
> successful) COMMIT wrapped around it.

— [3.4. Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)

#### The exceptions, each from its own reference page

| Statement | Documented restriction |
| --- | --- |
| `CREATE INDEX CONCURRENTLY` | "a regular CREATE INDEX command can be performed within a transaction block, but CREATE INDEX CONCURRENTLY cannot" |
| `DROP INDEX CONCURRENTLY` | "regular DROP INDEX commands can be performed within a transaction block, but DROP INDEX CONCURRENTLY cannot" |
| `REINDEX CONCURRENTLY` | "a regular REINDEX TABLE or REINDEX INDEX command can be performed within a transaction block, but REINDEX CONCURRENTLY cannot" |
| `REINDEX SCHEMA` / `DATABASE` / `SYSTEM`, and partitioned `REINDEX INDEX`/`TABLE` | "This form of REINDEX cannot be executed inside a transaction block." |
| `CREATE DATABASE` | "CREATE DATABASE cannot be executed inside a transaction block." |
| `CREATE TABLESPACE` | "CREATE TABLESPACE cannot be executed inside a transaction block." |
| `VACUUM` | "VACUUM cannot be executed inside a transaction block." |
| `ALTER SYSTEM` | "since this command acts directly on the file system and cannot be rolled back, it is not allowed inside a transaction block or function" |
| `ALTER TABLE ... DETACH PARTITION CONCURRENTLY` | "CONCURRENTLY cannot be run in a transaction block" |

#### One entry that is no longer on that list

Migration folklore still says you cannot add an enum value inside a transaction. In
PostgreSQL 16 you can. The restriction that survives is narrower:

> If ALTER TYPE ... ADD VALUE (the form that adds a new value to an enum type) is executed
> inside a transaction block, the new value cannot be used until after the transaction has been
> committed.

— [ALTER TYPE, Notes](https://www.postgresql.org/docs/16/sql-altertype.html)

Compare the same vendor, same page, pinned to PostgreSQL 11:

> ALTER TYPE ... ADD VALUE (the form that adds a new value to an enum type) cannot be executed
> inside a transaction block.

— [PG 11 ALTER TYPE, Notes](https://www.postgresql.org/docs/11/sql-altertype.html)

The prohibition was relaxed in PostgreSQL 12. Tooling and advice written against the older
wording is still in wide circulation.

#### Transactional DDL is not MVCC-clean

Worth knowing before you trust a rewrite inside a transaction:

> Some DDL commands, currently only TRUNCATE and the table-rewriting forms of ALTER TABLE, are
> not MVCC-safe. This means that after the truncation or rewrite commits, the table will appear
> empty to concurrent transactions, if they are using a snapshot taken before the DDL command
> committed.

— [13.6. Caveats](https://www.postgresql.org/docs/16/mvcc-caveats.html)

The same paragraph explains why this is usually invisible — any transaction that already
touched the table holds an ACCESS SHARE lock and therefore blocks the DDL — and why it is not
always invisible: the inconsistency shows up *between* the rewritten table and other tables.

### 1.2 What a half-failed migration leaves behind

#### On a transactional backend, in the ordinary case: nothing

If the whole migration ran in one transaction and a statement raised, the block is left in the
aborted state and every effect is discarded on rollback. Locks go with it:

> Once acquired, a lock is normally held until the end of the transaction. But if a lock is
> acquired after establishing a savepoint, the lock is released immediately if the savepoint is
> rolled back to.

— [13.3.1. Table-Level Locks](https://www.postgresql.org/docs/16/explicit-locking.html)

One note on sourcing: the familiar `current transaction is aborted, commands ignored until end
of transaction block` is a *server error message*, not documentation. It does not appear on
sql-begin, sql-savepoint, sql-rollback-to, tutorial-transactions, transaction-iso or app-psql.
The documented description of the state is in the wire-protocol chapter:

> the session will be left inside a failed regular transaction block, since the ROLLBACK is not
> reached after the divide-by-zero error. Another ROLLBACK will be needed to restore the session
> to a usable state.

— [55.2.2.1](https://www.postgresql.org/docs/16/protocol-flow.html)

#### The interesting case: the statements that cannot be in the transaction

Everything on the exception list above fails *outside* transactional protection, and
`CREATE INDEX CONCURRENTLY` is the one you will actually hit.

> If a problem arises while scanning the table, such as a deadlock or a uniqueness violation in
> a unique index, the CREATE INDEX command will fail but leave behind an "invalid" index. This
> index will be ignored for querying purposes because it might be incomplete; however it will
> still consume update overhead.

— [Building Indexes Concurrently](https://www.postgresql.org/docs/16/sql-createindex.html)

So the leftover is not inert. It costs write amplification on every INSERT and UPDATE while
contributing nothing to reads. And in the unique case it is less inert still:

> Also, if a failure does occur in the second scan, the "invalid" index continues to enforce its
> uniqueness constraint afterwards.

A failed concurrent unique index build leaves an index that is skipped by the planner, charged
to every writer, **and still rejecting duplicate rows**. That is the worst of all three worlds,
and it is easy to mistake for an application bug.

The documented detection route is `psql \d`, which reports the index as `INVALID`. The catalog
column people usually reach for is documented on a different page:

> indisvalid bool
>
> If true, the index is currently valid for queries. False means the index is possibly
> incomplete: it must still be modified by INSERT/UPDATE operations, but it cannot safely be
> used for queries. If it is unique, the uniqueness property is not guaranteed true either.

— [53.26. pg_index](https://www.postgresql.org/docs/16/catalog-pg-index.html)

The recommended recovery is to drop and retry.

`REINDEX CONCURRENTLY` leaves a better-labelled mess: the leftover is suffixed `_ccnew` if the
rebuild failed and `_ccold` if the rebuild succeeded but the old index could not be dropped,
with a numeric suffix if needed to stay unique. The suffix tells you which half of the swap
failed and therefore which index to drop.

#### MySQL 8.0: atomic DDL is not transactional DDL

MySQL 8.0 introduced atomic DDL, and its own documentation puts the disclaimer in a Note box
directly beneath the announcement.

The feature:

> An atomic DDL statement combines the data dictionary updates, storage engine operations, and
> binary log writes associated with a DDL operation into a single, atomic operation. The
> operation is either committed, with applicable changes persisted to the data dictionary,
> storage engine, and binary log, or is rolled back, even if the server halts during the
> operation.

The disclaimer:

> Atomic DDL is not transactional DDL. DDL statements, atomic or otherwise, implicitly end any
> transaction that is active in the current session, as if you had done a COMMIT before
> executing the statement. This means that DDL statements cannot be performed within another
> transaction, within transaction control statements such as START TRANSACTION ... COMMIT, or
> combined with other statements within the same transaction.

— [15.1.1 Atomic DDL](https://dev.mysql.com/doc/refman/8.0/en/atomic-ddl.html)

And the scope limit:

> Currently, only the InnoDB storage engine supports atomic DDL.

The distinction is exactly the one that matters for migrations. Atomic DDL is *crash*
atomicity for one statement: the dictionary write, the engine work and the binlog write all
land or none do, even if the server dies mid-operation. It is not *composition*: you cannot put
two DDL statements in a transaction and roll both back, because the second implicitly commits
the first.

The practical consequence is the one every MySQL migration tool has to design around. A
five-statement migration that fails on statement four leaves statements one through three
committed and unrecoverable by rollback. The database cannot help you; only a hand-written
compensating migration can.

One carve-out makes things worse rather than better:

> However, although no implicit commit occurs, neither can the statement be rolled back, which
> means that the use of such statements causes transactional atomicity to be violated. For
> example, if you use CREATE TEMPORARY TABLE and then roll back the transaction, the table
> remains in existence.

— [15.3.3 Statements That Cause an Implicit Commit](https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html)

---

## 2. Running Migrations Safely in Production

### 2.1 The rule that governs the whole ALTER TABLE page

> Note that the lock level required may differ for each subform. An ACCESS EXCLUSIVE lock is
> acquired unless explicitly noted. When multiple subcommands are given, the lock acquired will
> be the strictest one required by any subcommand.

— [ALTER TABLE, Description](https://www.postgresql.org/docs/16/sql-altertable.html)

Two things follow, and both are sourced rather than inferred. First, for any subform where the
page names no lock, the documented answer *is* ACCESS EXCLUSIVE — the default is stated, so
silence is not ambiguity. Second, batching is a genuine trade-off: combining subcommands takes
the strictest lock of the batch, while

> The main reason for providing the option to specify multiple changes in a single ALTER TABLE
> is that multiple table scans or rewrites can thereby be combined into a single pass over the
> table.

Adding a cheap SHARE ROW EXCLUSIVE foreign key alongside an ACCESS EXCLUSIVE change upgrades
the whole statement to ACCESS EXCLUSIVE.

### 2.2 The operations, by lock and by rewrite

| Operation | Lock | Rewrites? | Scans? |
| --- | --- | --- | --- |
| `ADD COLUMN`, no default | ACCESS EXCLUSIVE | No | No |
| `ADD COLUMN ... DEFAULT <non-volatile>` | ACCESS EXCLUSIVE | No | No |
| `ADD COLUMN ... DEFAULT <volatile>` | ACCESS EXCLUSIVE | **Yes** | — |
| `SET NOT NULL` | ACCESS EXCLUSIVE | No | Yes, unless a valid CHECK proves it |
| `ALTER COLUMN ... TYPE` | ACCESS EXCLUSIVE | Yes, unless binary coercible | — |
| `ADD CHECK` | ACCESS EXCLUSIVE | No | Yes |
| `ADD CHECK ... NOT VALID` | ACCESS EXCLUSIVE | No | **No** |
| `ADD FOREIGN KEY` | **SHARE ROW EXCLUSIVE**, both tables | No | Yes |
| `ADD FOREIGN KEY ... NOT VALID` | SHARE ROW EXCLUSIVE, both tables | No | **No** |
| `VALIDATE CONSTRAINT` | **SHARE UPDATE EXCLUSIVE** (+ ROW SHARE on referenced table for an FK) | No | Yes |
| `CREATE INDEX` | SHARE | No | Yes |
| `CREATE INDEX CONCURRENTLY` | SHARE UPDATE EXCLUSIVE | No | Twice |
| `DROP INDEX` | ACCESS EXCLUSIVE | — | — |
| `DROP INDEX CONCURRENTLY` | (waits for conflicting transactions) | — | — |

Three rows in that table routinely surprise people.

**`ADD COLUMN` with a default does not rewrite — and the criterion is broader than usually
stated.**

> When a column is added with ADD COLUMN and a non-volatile DEFAULT is specified, the default is
> evaluated at the time of the statement and the result stored in the table's metadata. That
> value will be used for the column for all existing rows. If no DEFAULT is specified, NULL is
> used. In neither case is a rewrite of the table required.
>
> Adding a column with a volatile DEFAULT or changing the type of an existing column will
> require the entire table and its indexes to be rewritten.

The word is **non-volatile**, not "constant". Any `IMMUTABLE` or `STABLE` expression qualifies,
not only a literal. The tutorial page says "constant default value", which is narrower than
what the reference page promises; the reference page is the precise one. This fast path arrived
in PostgreSQL 11.

**`ADD FOREIGN KEY` takes a weaker lock than you expect, on a table you did not name.**

> Although most forms of ADD table_constraint require an ACCESS EXCLUSIVE lock, ADD FOREIGN KEY
> requires only a SHARE ROW EXCLUSIVE lock. Note that ADD FOREIGN KEY also acquires a SHARE ROW
> EXCLUSIVE lock on the referenced table, in addition to the lock on the table on which the
> constraint is declared.

SHARE ROW EXCLUSIVE permits concurrent reads — ACCESS SHARE does not conflict with it — but it
conflicts with ROW EXCLUSIVE, so it blocks every INSERT, UPDATE and DELETE. On both tables.
Adding a foreign key to a small child table blocks writes to the large parent table, which is
the part that bites. It is also self-exclusive, so two FK additions pointing at the same parent
serialise against each other.

**`NOT VALID` removes the scan, not the lock.** Only `ADD FOREIGN KEY` gets the weaker lock;
`ADD CHECK ... NOT VALID` still takes ACCESS EXCLUSIVE. It is safe because the lock is held
*briefly* — no scan happens under it — not because the lock is weak. That distinction decides
whether `lock_timeout` is optional or mandatory.

### 2.3 The two-step constraint pattern, as documented

> Normally, this form will cause a scan of the table to verify that all existing rows in the
> table satisfy the new constraint. But if the NOT VALID option is used, this potentially-lengthy
> scan is skipped. The constraint will still be enforced against subsequent inserts or updates
> [...] But the database will not assume that the constraint holds for all rows in the table,
> until it is validated by using the VALIDATE CONSTRAINT option.

and the rationale paragraph, which is the clearest statement of why this works at all:

> The validation step does not need to lock out concurrent updates, since it knows that other
> transactions will be enforcing the constraint for rows that they insert or update; only
> pre-existing rows need to be checked. Hence, validation acquires only a SHARE UPDATE EXCLUSIVE
> lock on the table being altered. (If the constraint is a foreign key then a ROW SHARE lock is
> also required on the table referenced by the constraint.)

The same paragraph ends with a second use that is easy to miss:

> In addition to improving concurrency, it can be useful to use NOT VALID and VALIDATE
> CONSTRAINT in cases where the table is known to contain pre-existing violations. Once the
> constraint is in place, no new violations can be inserted, and the existing problems can be
> corrected at leisure until VALIDATE CONSTRAINT finally succeeds.

`NOT VALID` is the sanctioned way to adopt a constraint over dirty data: it freezes the
violation set at the moment of the ALTER and lets you clean up behind it.

### 2.4 `SET NOT NULL` without the scan

The pieces are all documented, but on three different parts of the page, and the manual never
assembles them into a recipe.

> SET NOT NULL may only be applied to a column provided none of the records in the table contain
> a NULL value for the column. Ordinarily this is checked during the ALTER TABLE by scanning the
> entire table; however, if a valid CHECK constraint exists (and is not dropped in the same
> command) which proves no NULL can exist, then the table scan is skipped.

plus

> Adding a CHECK or NOT NULL constraint requires scanning the table to verify that existing rows
> meet the constraint, but does not require a table rewrite.

Assembled, the zero-downtime sequence is: `ADD CONSTRAINT ... CHECK (col IS NOT NULL) NOT VALID`
(ACCESS EXCLUSIVE, instantaneous) → `VALIDATE CONSTRAINT` (SHARE UPDATE EXCLUSIVE, scans, does
not block writes) → `SET NOT NULL` (ACCESS EXCLUSIVE, scan skipped because the valid CHECK
proves it) → optionally drop the now-redundant CHECK.

### 2.5 Concurrent index builds

> When this option is used, PostgreSQL will build the index without taking any locks that
> prevent concurrent inserts, updates, or deletes on the table; whereas a standard index build
> locks out writes (but not reads) on the table until it's done.

The cost is stated just as plainly:

> When this option is used, PostgreSQL must perform two scans of the table, and in addition it
> must wait for all existing transactions that could potentially modify or use the index to
> terminate. Thus this method requires more total work than a standard index build and takes
> significantly longer to complete.

That waiting clause is the operational trap: a concurrent build cannot finish while any
long-running transaction predating it is still open. One forgotten `idle in transaction`
session stalls the build indefinitely. Even after it completes,

> in the worst case, it cannot be used as long as transactions exist that predate the start of
> the index build.

The concurrency restriction is per-table, and narrower than usually quoted:

> Regular index builds permit other regular index builds on the same table to occur
> simultaneously, but only one concurrent index build can occur on a table at a time.

Two *regular* builds on one table may run together; two *concurrent* builds may not.

PostgreSQL also blesses one multi-step recipe explicitly — the only place in the manual that
does anything of the kind:

> Adding a constraint using an existing index can be helpful in situations where a new
> constraint needs to be added without blocking table updates for a long time. To do that,
> create the index using CREATE INDEX CONCURRENTLY, and then install it as an official
> constraint using this syntax.

with the restrictions that make it sound: b-tree, default sort order, no expressions, not
partial, not partitioned.

### 2.6 Lock modes, and the definition that matters

> The only real difference between one lock mode and another is the set of lock modes with which
> each conflicts.

— [13.3.1. Table-Level Locks](https://www.postgresql.org/docs/16/explicit-locking.html)

The names are, in the manual's own word, "historical" — "all of these lock modes are table-level
locks, even if the name contains the word 'row'". The three that matter for migrations:

> **SHARE UPDATE EXCLUSIVE** — Conflicts with the SHARE UPDATE EXCLUSIVE, SHARE, SHARE ROW
> EXCLUSIVE, EXCLUSIVE, and ACCESS EXCLUSIVE lock modes. This mode protects a table against
> concurrent schema changes and VACUUM runs.

> **SHARE ROW EXCLUSIVE** — Conflicts with the ROW EXCLUSIVE, SHARE UPDATE EXCLUSIVE, SHARE,
> SHARE ROW EXCLUSIVE, EXCLUSIVE, and ACCESS EXCLUSIVE lock modes. This mode protects a table
> against concurrent data changes, and is self-exclusive so that only one session can hold it at
> a time.

> **ACCESS EXCLUSIVE** — Conflicts with locks of all modes [...] This mode guarantees that the
> holder is the only transaction accessing the table in any way.

and the Tip that summarises the reader's-eye view:

> Only an ACCESS EXCLUSIVE lock blocks a SELECT (without FOR UPDATE/SHARE) statement.

### 2.7 The convoy — a documented gap

Here is the thing everybody knows and PostgreSQL does not document. When an ACCESS EXCLUSIVE
request *waits*, subsequent SELECTs queue behind it, even though SELECT does not conflict with
SELECT. That is why a one-second `ALTER TABLE` behind one long transaction takes the site down
rather than delaying one statement.

**PostgreSQL's manual never states this rule.** What it offers is circumstantial. Wait queues
exist as a concept:

> Worse, the pg_locks view does not expose information about which processes are ahead of which
> others in lock wait queues

— [54.12. pg_locks](https://www.postgresql.org/docs/16/view-pg-locks.html)

and one sentence on the same page implies you can be blocked by a *waiter* rather than a holder:

> False indicates that this process is currently waiting to acquire this lock, which implies
> that at least one other process is holding **or waiting for** a conflicting lock mode on the
> same lockable object.

and waiting is unbounded by default:

> a transaction seeking either a table-level or row-level lock will wait indefinitely for
> conflicting locks to be released

That is as far as PostgreSQL goes. **MySQL states the rule outright**, with a three-session
worked example:

> Additionally, a pending exclusive metadata lock requested by an online DDL operation blocks
> subsequent transactions on the table.

— [17.12.2 Online DDL Performance and Concurrency](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html)

In MySQL's own example, session 1 holds an open transaction with a `SELECT`, session 2 runs
`ALTER TABLE t1 ADD COLUMN x INT, ALGORITHM=INPLACE, LOCK=NONE`, and session 3's plain `SELECT`
blocks. Note that session 2 asked for `LOCK=NONE` and still produced the outage: `LOCK=NONE`
governs the execution phase, not the brief exclusive metadata lock at commit. "Online" does not
mean "lock-free".

Teaching the convoy from MySQL's page while noting PostgreSQL behaves the same way is
defensible. Citing PostgreSQL for it is not.

### 2.8 `lock_timeout` is the mitigation, with one wrinkle

> Abort any statement that waits longer than the specified amount of time while attempting to
> acquire a lock on a table, index, row, or other database object. **The time limit applies
> separately to each lock acquisition attempt.** [...] A value of zero (the default) disables the
> timeout.

— [20.11.2. Statement Behavior](https://www.postgresql.org/docs/16/runtime-config-client.html)

Two operational notes the manual makes explicit. The per-attempt scoping means a
multi-subcommand `ALTER TABLE` touching several relations can wait up to N × `lock_timeout` in
total — the setting does not bound the statement. And:

> if statement_timeout is nonzero, it is rather pointless to set lock_timeout to the same or
> larger value, since the statement timeout would always trigger first

The discipline that follows: set a low `lock_timeout` around DDL, and retry on failure. The
failure mode you are buying protection against is not the DDL being slow — it is the DDL
waiting.

`idle_in_transaction_session_timeout` addresses the other end of the same problem, terminating
the long-lived transactions that DDL ends up queued behind.

### 2.9 MySQL's Online DDL, for contrast

MySQL exposes the same decisions as an explicit matrix per operation, with five columns —
`Instant`, `In Place`, `Rebuilds Table`, `Permits Concurrent DML`, `Only Modifies Metadata`.
Selected rows:

| Operation | Instant | In Place | Rebuilds Table | Permits Concurrent DML | Only Modifies Metadata |
| --- | --- | --- | --- | --- | --- |
| Adding a column | Yes\* | Yes | No\* | Yes\* | Yes |
| Renaming a column | Yes\* | Yes | No | Yes\* | Yes |
| **Changing the column data type** | **No** | **No** | **Yes** | **No** | **No** |
| Extending VARCHAR column size | No | Yes | No | Yes | Yes |
| Creating or adding a secondary index | No | Yes | No | Yes | No |
| Adding a foreign key constraint | No | Yes\* | No | Yes | Yes |

— [17.12.1 Online DDL Operations](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html)

Changing a column's data type is the only common column operation that is negative in every
column: not instant, not in place, rebuilds the table, blocks DML. That is MySQL's equivalent
of PostgreSQL's ACCESS EXCLUSIVE rewrite — and note the asymmetry: PostgreSQL can skip the
rewrite when the new type is binary coercible, while MySQL documents no such exception beyond
the narrow "Extending VARCHAR column size" row.

Two asterisks carry real weight. Adding a foreign key online:

> The INPLACE algorithm is supported when foreign_key_checks is disabled. Otherwise, only the
> COPY algorithm is supported.

MySQL buys onlineness by *skipping* the verification. PostgreSQL's `NOT VALID` defers it. Those
are different safety properties wearing similar-looking table rows.

And the clause that has no PostgreSQL equivalent:

> Specifying an ALGORITHM clause requires the operation to use the specified algorithm for
> clauses and storage engines that support it, or fail with an error otherwise.

— [15.1.9 ALTER TABLE](https://dev.mysql.com/doc/refman/8.0/en/alter-table.html)

`ALGORITHM=INPLACE` and `LOCK=NONE` are **assertions**, not requests: "If supported, permit
concurrent reads and writes. Otherwise, an error occurs." Naming the algorithm turns a silent
downgrade into a loud failure. PostgreSQL has nothing at statement level that does this; you
approximate it with `lock_timeout` and `NOWAIT`.

### 2.10 Expand/contract is not in either manual

Searched across every PostgreSQL 16 and MySQL 8.0 page consulted for this document: zero hits
for expand/contract, "parallel change", or any equivalent rolling-upgrade schema language. **No
vendor documents, names or endorses the pattern.** What the manuals supply are its primitives —
`NOT VALID` / `VALIDATE CONSTRAINT`, `CREATE INDEX CONCURRENTLY` plus
`ADD table_constraint_using_index`, the non-volatile-default fast path, MySQL's `ALGORITHM` /
`LOCK` assertions. The closest thing to vendor endorsement of a multi-step technique is the
ALTER TABLE Note quoted in §2.5, and it covers one constraint, not a protocol.

The pattern has an attributable owner, and it is a practitioner source — held to a different
evidential standard than everything above:

> Parallel change, also known as expand and contract, is a pattern to implement
> backward-incompatible changes to an interface in a safe manner, by breaking the change into
> three distinct phases: expand, migrate, and contract.

— Danilo Sato, [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html),
martinfowler.com, 13 May 2014

The three phases, in the source's words: "In the expand phase you augment the interface to
support both the old and the new versions." / "During the migrate phase you update all clients
using the old version to the new version." / "Once all usages have been migrated to the new
version, you perform the contract phase to remove the old version".

The database application is explicit in the same article:

> Database refactoring: this is a key component to evolutionary database design. Most database
> refactorings follow the parallel change pattern, where the migrate phase is the transition
> period between the original and the new schema, until all database access code has been
> updated to work with the new schema.

And the failure mode, which is the half practitioners skip:

> If the contract phase is not executed you might end up in a worse state than you started,
> therefore you need discipline to finish the transition successfully.

Provenance, from the article's own acknowledgements: "This technique was first documented as a
refactoring strategy by Joshua Kerievsky in 2006 and presented in his talk The Limited Red
Society presented at the Lean Software and Systems Conference in 2010." So the chain is
Kerievsky (2006) → named and written up by Sato (2014). Not Fowler, whose site hosts it.

#### What the pattern buys, in terms of the mechanics above

Every operation in the §2.2 table that is *safe* is safe because it is either metadata-only or
takes a weak lock. The ones that are unsafe — rewrites, scans under ACCESS EXCLUSIVE — cannot be
made safe by running them more carefully. Expand/contract exists because the only way to avoid
an unsafe operation is to not perform it: you reach the target schema through a sequence of
individually-safe steps, at the cost of a period in which both shapes are live and the
application must tolerate both.

Renaming a column is the canonical example precisely because no database offers a safe rename
that is also a compatible one. The rename itself is cheap; the incompatibility is the problem.
Expand/contract replaces it with add-column (metadata-only), dual-write, backfill in batches,
switch reads, drop-column — five operations, each individually cheap, spread across at least
three deploys.

---

## 3. How Alembic Implements Migrations

### 3.1 Where the version write sits relative to the migration body

The question "is `alembic_version` updated inside the transaction that ran the migration?"
has a one-line answer in the source, and it is not configurable: **yes, always, and after
the body**.

`alembic/runtime/migration.py::MigrationContext.run_migrations`, lines 610–631:

```python
        assert self._migrations_fn is not None
        for step in self._migrations_fn(heads, self):
            with self.begin_transaction(_per_migration=True):
                if self.as_sql and not head_maintainer.heads:
                    # for offline mode, include a CREATE TABLE from
                    # the base
                    assert self.connection is not None
                    self._version.create(self.connection)
                log.info("Running %s", step)
                if self.as_sql:
                    self.impl.static_output(
                        "-- Running %s" % (step.short_log,)
                    )
                step.migration_fn(**kw)

                # previously, we wouldn't stamp per migration
                # if we were in a transaction, however given the more
                # complex model that involves any number of inserts
                # and row-targeted updates and deletes, it's simpler for now
                # just to run the operations on every version
                head_maintainer.update_to_step(step)
```

Line 623 is the revision script's `upgrade()`. Line 630 is the `alembic_version`
INSERT/UPDATE/DELETE. They share one `with` block. The code comment at 625–629 records that
this was not always so: Alembic used to skip the per-migration stamp when the whole run was
already inside a transaction, and now always emits it.

That settles the ordering. It does **not** settle the transaction boundary, which is decided
one level down.

#### The boundary is one line

`MigrationContext.begin_transaction` is called from exactly two places: the user's `env.py`,
with no arguments (`_per_migration=False`), and `run_migrations` above, once per step, with
`_per_migration=True`. Lines 413–419:

```python
        if self._in_external_transaction:
            return nullcontext()

        if self.impl.transactional_ddl:
            transaction_now = _per_migration == self._transaction_per_migration
        else:
            transaction_now = _per_migration is True
```

Line 417 is an equality between two booleans, which makes the behaviour a truth table:

| `transaction_per_migration` | outer call | per-step call |
| --- | --- | --- |
| `False` (default) | real transaction | `nullcontext()` |
| `True` | `nullcontext()` | real transaction |

Exactly one of the two levels opens a real transaction — never both, never neither. So on
PostgreSQL with defaults, a single transaction wraps the entire `alembic upgrade` command:
every migration body and every version-table write for the whole run commits or rolls back
together. Set `transaction_per_migration=True` and the unit becomes one revision script plus
its own stamp.

Line 418 is the non-transactional-DDL branch: MySQL, SQLite and Oracle always take the
per-step path regardless of the setting, because there is no point holding a run-wide
transaction open around DDL the server has already committed behind your back.

Line 413 is the escape hatch. If the `Connection` handed to `configure()` was already inside
a transaction, Alembic opens and closes nothing — the embedding application owns the
boundary. This is implementation detail, not a documented promise.

The docstring at lines 392–401 documents the intent:

> A "Logical" transaction means that the operation may or may not
> correspond to a real database transaction.   If the target database
> supports transactional DDL (or
> :paramref:`.EnvironmentContext.configure.transactional_ddl` is true),
> the :paramref:`.EnvironmentContext.configure.transaction_per_migration`
> flag is not set, and the migration is against a real database
> connection (as opposed to using "offline" ``--sql`` mode), a real
> transaction will be started.

Note what it does not say: nothing in the published API promises that the version row is
written *after* the body, or inside the same scope. That is behaviour of this tree.

#### Which backends Alembic believes have transactional DDL

`transactional_ddl` is a class attribute on the dialect impl, overridable per-run via
`EnvironmentContext.configure(transactional_ddl=...)`:

| Impl | file:line | value |
| --- | --- | --- |
| `DefaultImpl` | `alembic/ddl/impl.py:97` | `False` |
| `PostgresqlImpl` | `alembic/ddl/postgresql.py:81` | `True` |
| `MSSQLImpl` | `alembic/ddl/mssql.py:53` | `True` |
| `MySQLImpl` | `alembic/ddl/mysql.py:44` | `False` |
| `SQLiteImpl` | `alembic/ddl/sqlite.py:43` | `False` |
| `OracleImpl` | `alembic/ddl/oracle.py:37` | `False` |

Two of six. The default is `False`, so a third-party dialect that says nothing is assumed
non-transactional.

`PostgresqlImpl.transactional_ddl = True` is a claim about the backend, not a universal
truth about it — PostgreSQL has statements that cannot run inside a transaction block at
all, which is precisely why `autocommit_block()` exists.

#### The table itself

In 1.14 the version table's structure moved behind a dialect hook,
`alembic/ddl/impl.py::DefaultImpl.version_table_impl`, lines 142–174:

```python
        vt = Table(
            version_table,
            MetaData(),
            Column("version_num", String(32), nullable=False),
            schema=version_table_schema,
        )
        if version_table_pk:
            vt.append_constraint(
                PrimaryKeyConstraint(
                    "version_num", name=f"{version_table}_pkc"
                )
            )
```

so on PostgreSQL:

```sql
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
)
```

The column *name* is a documented contract — the hook's docstring requires that a
replacement "be named based on the ``version_table`` parameter and contains at least a
single string-holding column named ``version_num``". The *width* is not: 32 is a bare
literal on line 164, and there is no named constant for it anywhere in the package.
Generated revision ids use 12 of those 32 characters (`uuid.uuid4().hex[-12:]`,
`alembic/util/langhelpers.py:232-233`).

The row count is not always one. It is the number of current heads: one row per unmerged
branch. `get_current_revision()` raises rather than guess when there is more than one.

#### The guard that matters for concurrency

There is no row-count check. The guard is a rowcount assertion on the write itself —
`HeadMaintainer._update_version`, lines 806–817:

```python
        if (
            not self.context.as_sql
            and self.context.dialect.supports_sane_rowcount
            and ret is not None
            and ret.rowcount != 1
        ):
            raise util.CommandError(
                "Online migration expected to match one "
                "row when updating '%s' to '%s' in '%s'; "
                "%d found"
                % (from_, to_, self.context.version_table, ret.rowcount)
            )
```

The UPDATE is `SET version_num='<to>' WHERE version_num='<from>'`. If another process has
already moved the row past `<from>`, this matches zero rows and the migration aborts. That
is a compare-and-swap, and it is the only thing in Alembic that resembles concurrency
control. It is skipped entirely in offline mode (`ret is None`) and on dialects that do not
report sane rowcounts.

Worth noting in passing: the revision string is interpolated into the statement with
`literal_column("'%s'" % version)` rather than bound, so that `--sql` mode emits a literal,
runnable statement. Revision ids are checked against `["@", "-", "+"]` and nothing else —
quotes are not rejected.

### 3.2 RevisionMap: what a branch and a merge actually are

#### A merge revision is a tuple

There is no merge type, no merge flag. `Revision.__init__` normalises `down_revision`
through `tuple_rev_as_scalar`, which collapses a one-element tuple back to a bare string,
and then:

```python
    @property
    def is_merge_point(self) -> bool:
        """Return True if this :class:`.Script` is a merge point."""

        return len(self._versioned_down_revisions) > 1
```

`alembic/script/revision.py:1698-1702`. A merge point is a revision whose `down_revision`
is a tuple of length ≥ 2. That is the entire definition.

#### Three different meanings of "below me"

The `dependencies` attribute exists alongside `down_revision`, and the split between them is
the thing that makes the rest of the module legible (`revision.py:1625-1645`):

| property | contents |
| --- | --- |
| `_versioned_down_revisions` | `down_revision` only |
| `_all_down_revisions` | `down_revision` + all resolved `dependencies` |
| `_normalized_down_revisions` | `down_revision` + dependencies not already implied by an ancestor |

The version table follows the first. Cycle detection uses the second. Traversal order uses
the third. This is why a revision with one `down_revision` and three `dependencies` is *not*
a merge point and never collapses rows in `alembic_version`: `dependencies` order the run,
they do not define lineage.

The docstring says as much (`revision.py:1565-1573`):

> Additional revisions which this revision is dependent on.
>
> From a migration standpoint, these dependencies are added to the
> down_revision to form the full iteration.  However, the separation
> of down_revision from "dependencies" is to assist in navigating
> a history that contains many branches, typically a multi-root scenario.

#### How heads are computed

`RevisionMap._revision_map` (lines 199–265) is a memoized property that builds the whole
graph in one pass and writes `heads`, `bases`, `_real_heads`, `_real_bases` over their own
memoized descriptors as a side effect. The algorithm is optimistic-then-subtractive:

1. every revision is added to `heads` and `_real_heads` (lines 220–221);
2. then one pass over all down-links (lines 238–249) installs back-links and discards:

```python
        for rev in map_.values():
            for downrev in rev._all_down_revisions:
                if downrev not in map_:
                    util.warn(
                        "Revision %s referenced from %s is not present"
                        % (downrev, rev)
                    )
                down_revision = map_[downrev]
                down_revision.add_nextrev(rev)
                if downrev in rev._versioned_down_revisions:
                    heads.discard(down_revision)
                _real_heads.discard(down_revision)
```

Line 247 is the distinction again: a pure `dependencies` link removes the target from
`_real_heads` but leaves it a versioned head.

Lines 240–245 are a wart: a missing `down_revision` target produces a warning and then
immediately raises `KeyError` on the next line. The warning never reaches the user as a
warning.

Line 258, `revision_map[None] = revision_map[()] = None`, is what makes `"base"` resolvable —
`_resolve_revision_number` returns the empty tuple for `"base"` and `None`, and looking `()`
up in the map yields `None`.

#### Symbolic and relative identifiers

Two module constants do most of the work (`revision.py:47-48`):

```python
_relative_destination = re.compile(r"(?:(.+?)@)?(\w+)?((?:\+|-)\d+)")
_revision_illegal_chars = ["@", "-", "+"]
```

The regex has three groups — an optional `branchlabel@` prefix, an optional symbol, and a
**required** `+N`/`-N` offset. It only matches when an offset is present; absolute targets
fall through to a different path. The illegal-character list is the reason a revision id may
not contain `@`, `-` or `+`: those three characters are reserved for the addressing syntax,
enforced by `Revision.verify_rev_id`.

`_resolve_revision_number` (lines 748–786) decodes the symbols. Two details are easy to miss:

- `"heads"` with no branch label returns `_real_heads` — dependency-aware — but with a label
  returns `filter_for_lineage(self.heads, ...)`, the versioned heads. An asymmetry, and
  implementation detail.
- `"head"` singular goes through `get_current_head`, which raises `MultipleHeads`.

Partial revision ids are matched with a hard four-character floor
(`_revision_for_ident`, line 631: `if x and len(x) > 3 and x.startswith(resolved_id)`), and
the error tells you so.

#### Upgrade and downgrade as set algebra

`_collect_upgrade_revisions` reduces to one line (`revision.py:1508`):

```python
        needs = required_node_set.difference(current_node_set)
```

where both sides are `_get_ancestor_nodes(..., include_dependencies=True)` unioned with
their targets. **Upgrade set = ancestors(target) − ancestors(current).**

Downgrade is the mirror: collect the descendants of the roots being dropped, then intersect
with what is currently active (lines 1395–1407). `iterate_revisions` then topologically
sorts the resulting set, and `ScriptDirectory._upgrade_revs` reverses the result because the
sort yields newest-first while an upgrade must run oldest-first.

The error hierarchy is small and the messages are worth recognising: `MultipleHeads`
("Multiple heads are present for given argument"), `RangeNotAncestorError` ("Revision X is
not an ancestor of revision Y"), `ResolutionError`, `CycleDetected` / `DependencyCycleDetected`
/ `LoopDetected`. All are converted to `util.CommandError` at the `ScriptDirectory` boundary
by `_catch_revision_errors`, which is where the familiar advice to use
`'<branchname>@head'` comes from.

### 3.3 What autogenerate compares — and the proof of what it cannot

#### The complete surface

Autogenerate's entire detection surface is nine functions registered on one dispatcher in
one file:

| key | function | line |
| --- | --- | --- |
| `schema` | `_autogen_for_tables` | 103 |
| `table` | `_compare_indexes_and_uniques` | 441 |
| `table` | `_compare_foreign_keys` | 1170 |
| `table` | `_compare_table_comment` | 1294 |
| `column` | `_compare_nullable` | 858 |
| `column` | `_setup_autoincrement` | 899 |
| `column` | `_compare_type` | 917 |
| `column` | `_compare_server_default` | 1054 |
| `column` | `_compare_column_comment` | 1142 |

A `grep` for `comparators.dispatch_for` across the whole package returns these nine lines and
nothing else — no dialect registers a comparator. Anything not in that table is invisible by
construction, not by accident.

Two structural facts frame everything else. First, the downgrade is not computed
(`compare.py:66`):

```python
    upgrade_ops.reverse_into(downgrade_ops)
```

It is the mechanical reverse of the upgrade. Second, only the default schema is examined
unless `include_schemas=True` (`compare.py:90-91`): `schemas = {None}`.

#### The proof that renames cannot be detected

`_compare_columns` (lines 365–436) is three set operations keyed on `c.name`:

```python
    for cname in metadata_col_names.difference(conn_col_names):
        ...  ops.AddColumnOp.from_column_and_tablename(...)

    for colname in metadata_col_names.intersection(conn_col_names):
        ...  comparators.dispatch("column")(...)

    for cname in set(conn_col_names).difference(metadata_col_names):
        ...  ops.DropColumnOp.from_column_and_tablename(...)
```

There is no fourth pass, no similarity heuristic, no type or ordinal matching — nothing that
could pair a dropped name with an added one. `AlterColumnOp` *has* a `modify_name` field (it
is how `op.alter_column(..., new_column_name=...)` is expressed), but no comparator ever
assigns it. `_compare_tables` has the same shape at the table level.

This is not a limitation that could be tightened with better heuristics without changing the
shape of the algorithm: rename detection requires pairing, and there is no pairing step.

#### Server defaults

Off by default: `MigrationContext._compare_server_default` returns `False` immediately
unless `compare_server_default=True` was passed. When it is on, the generic implementation is
the whole of `alembic/ddl/impl.py:600-607`:

```python
    def compare_server_default(
        self,
        inspector_column,
        metadata_column,
        rendered_metadata_default,
        rendered_inspector_default,
    ):
        return rendered_inspector_default != rendered_metadata_default
```

One string comparison between two rendered defaults. `server_default="0"` against a database
that reflects `'0'::integer` is a false positive.

PostgreSQL does better, and does it by asking the server
(`alembic/ddl/postgresql.py:142-149`):

```python
        # run a real compare against the server
        conn = self.connection
        assert conn is not None
        return not conn.scalar(
            sqla_compat._select(
                literal_column(conn_col_default) == metadata_default
            )
        )
```

It executes `SELECT <conn_default> = <metadata_default>` and inverts the answer — one round
trip per differing column. It also exempts SERIAL primary keys outright (lines 114–118), so
a `nextval(...)` default on an autoincrement PK is never reported.

#### Types

`compare_type` is on by default but is a *token* comparison, not a semantic one: the type is
compiled to a string and regex-split (`impl.py:491`, `:505`), then compared — with explicit
synonym tables that suppress real differences by design:

```python
    type_synonyms: Tuple[Set[str], ...] = ({"NUMERIC", "DECIMAL"},)
```

plus `{"FLOAT", "DOUBLE PRECISION"}` on PostgreSQL. And `_column_args_match` deliberately
ignores one-sided parameters — its docstring says "if only one specifies it, dont flag it
for being less specific". A `collation` present only in the model is never reported.

#### Named things only

The source states its own assumptions (`compare.py:619-625`):

```python
    # assumptions:
    # 1. a unique constraint or an index from the connection *always*
    #    has a name.
    # 2. an index on the metadata side *always* has a name.
    # 3. a unique constraint on the metadata side *might* have a name.
    # 4. The backend may double up indexes as unique constraints and
    #    vice versa (e.g. MySQL, Postgresql)
```

and enforces them at line 584 (`if c.is_named`) and line 595. Unnamed *unique* constraints get
a by-column-signature rescue — but an add-only one: there is no corresponding removal pass.
Anonymous constraints of any other kind have no rescue.

There is also a designed-in silent miss. `ComparisonResult.Skip` means "cannot be compared",
and its docstring is explicit about the consequence:

> the constraint cannot be compared for the provided reason(s).
>
> The message is logged, but the constraints will be otherwise
> considered equal, meaning that no migration command will be
> generated.

#### Where the published list and this version part company

The current documentation — [Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
— lists CHECK-constraint detection under "Autogenerate can
optionally detect". **That feature does not exist in 1.14.1** — `grep` for `CheckConstraint`
in `compare.py` returns zero hits, and the nine-comparator registry has no entry for it.

The docs page resolves the discrepancy itself: the subsection describing the feature is
marked *"Added in version 1.19.0"*, and *"Changed in version 1.19.2: This feature is no
longer enabled by default."* So `/en/latest/` documents a release five minor versions after
the target. There is no versioned docs URL for 1.14 (`/en/release-1.14.0/` returns 404), so
for this version the source is the only authority, and on 1.14.1 CHECK constraints are
simply undetectable.

The published "can not detect" list — table renames, column renames, anonymously named
constraints, `Enum` on backends without native ENUM — is also considerably shorter than what
the source supports. A fourth list, "can't currently, but will eventually detect", adds
free-standing PRIMARY KEY and EXCLUDE constraints and sequences. Beyond all of those, the
code shows that views (`get_view_names` is never called), triggers, stored procedures,
functions, extensions, grants, partitions, RLS policies, table data, non-default schemas
without `include_schemas`, computed/identity changes, and FK option changes on backends that
do not reflect options are all outside the comparison.

### 3.4 How `op.add_column()` reaches dialect-specific SQL

The chain, with the file each hop lives in:

```
alembic.op.add_column(...)                    alembic/op.py:5        (module proxy)
 → Operations.add_column(...)                 alembic/operations/base.py:173-193 (exec'd)
  → AddColumnOp.add_column(...)               alembic/operations/ops.py:2155-2156
   → Operations.invoke(op)                    alembic/operations/base.py:439-441  ← dialect dispatch
    → toimpl.add_column                       alembic/operations/toimpl.py:172-197
     → DefaultImpl.add_column                 alembic/ddl/impl.py:368-374
      → base.AddColumn construct              alembic/ddl/base.py:151-159
       → DefaultImpl._exec                    alembic/ddl/impl.py:204-247  ← online/offline fork
        → @compiles visit_add_column          alembic/ddl/base.py:188-193
         → add_column() helper                alembic/ddl/base.py:327-336
          → compiler.get_column_specification(column)   ← SQLAlchemy boundary
```

Four hops deserve comment.

**`alembic.op` is generated at import time.** The module is three lines; every public method
of `Operations` gets a proxy installed by `create_module_class_proxy`. `Operations.add_column`
itself is also generated — `@Operations.register_operation("add_column")` builds the method
source as a string and `exec`s it, rewriting the op class's `(cls, operations)` signature to
`(self)`. This is why the static signature and docs live in a stub file, `alembic/op.pyi`,
and why calling `op.add_column` outside a migration raises a `NameError` about the proxy not
being established.

**The first dialect-aware dispatch is `invoke`** (`base.py:439-441`), which looks up
`(op_class, dialect_name)` and falls back to `(op_class, "default")`. For `AddColumnOp` no
dialect registers an override, so every backend lands on the same `toimpl.add_column`.

**One `op.add_column()` can emit several statements** (`toimpl.py:172-197`). It fabricates a
throwaway `Table` to host the column so SQLAlchemy derives the implied constraints, emits
the `ALTER TABLE ... ADD COLUMN`, and then emits each non-primary-key constraint as its own
`ALTER TABLE ... ADD CONSTRAINT`, each index as its own `CREATE INDEX`, and on a dialect with
out-of-line comments a separate `COMMENT ON COLUMN`. The `Column` is copied first if it is
already bound to a `Table`, so the model object is not mutated.

**PostgreSQL does not override `AddColumn` at all.** `alembic/ddl/postgresql.py` has exactly
four `@compiles` registrations — `RenameTable`, `PostgresqlColumnType`, `ColumnComment`,
`IdentityColumnDefault` — and `AddColumn` is not among them. Nor does any dialect override
`DefaultImpl.add_column`.

So the hand-off is a single line, `alembic/ddl/base.py:328`:

```python
    text = "ADD COLUMN %s" % compiler.get_column_specification(column, **kw)
```

Alembic writes the strings `"ALTER TABLE"` and `"ADD COLUMN"`. Everything about the column —
its quoted name, its type, `DEFAULT`, `NOT NULL`, `GENERATED`, identity — is written by
SQLAlchemy's `DDLCompiler`, and on PostgreSQL by
`sqlalchemy/dialects/postgresql/base.py::PGDDLCompiler.get_column_specification`. That is
where `SERIAL` / `BIGSERIAL` / `SMALLSERIAL` are produced, and it requires
`column.table._autoincrement_column` — which is exactly why the throwaway `Table` in
`toimpl.add_column` matters.

The generalisation is worth holding onto: `op.add_column()` is dialect-neutral all the way
down inside Alembic, and its PostgreSQL-specific text comes from SQLAlchemy.
`op.alter_column()` is the opposite — there Alembic branches per dialect, which is how
`postgresql_using=` threads a `USING` clause into `ALTER COLUMN ... TYPE`.

Finally, the online/offline fork for this and every other statement is one `if` in
`DefaultImpl._exec` (`impl.py:213`): offline compiles the construct against the configured
dialect and writes the text plus a terminator to the output buffer, returning `None`; online
hands the construct to `Connection.execute`. That `None` is why the rowcount guards in
`HeadMaintainer` test `ret is not None` before asserting.

---

## 4. Alembic in Practice

### 4.1 Offline mode is a compiler, not an executor

`--sql` is documented as a first-class feature with a stated purpose:

> A major capability of Alembic is to generate migrations as SQL scripts, instead of running
> them against the database - this is also referred to as offline mode. This is a critical
> feature when working in large organizations where access to DDL is restricted, and SQL
> scripts must be handed off to DBAs.

— [Generating SQL Scripts (a.k.a. "Offline Mode")](https://alembic.sqlalchemy.org/en/latest/offline.html)

The implementation is one branch. `DefaultImpl._exec` — `alembic/ddl/impl.py:204-232` — is the
single fork the whole feature turns on:

```python
        if self.as_sql:
            if multiparams is not None or params:
                raise TypeError("SQL parameters not allowed with as_sql")
            ...
            compiled = construct.compile(dialect=self.dialect, **compile_kw)
            self.static_output(
                str(compiled).replace("\t", "    ").strip()
                + self.command_terminator
            )
            return None
```

Two consequences follow from those eight lines, and both matter more than the feature's
documentation suggests.

**The statement is compiled, never executed.** A construct that compiles cleanly but would fail
at runtime produces a clean-looking script. Offline mode cannot tell you that a migration
works; it can only tell you that it renders.

**`_exec` returns `None` offline.** Every rowcount-based safety check in Alembic is therefore
inert under `--sql` — see §4.3, where this turns out to disable the only concurrency guard the
tool has.

The connection is not real either. `MigrationContext.__init__` — `migration.py:152-157` —
swaps it out:

```python
        if as_sql:
            self.connection = cast(
                Optional["Connection"], self._stdout_connection(connection)
            )
            assert self.connection is not None
            self._in_external_transaction = False
```

and `_stdout_connection` — `migration.py:666-672` — returns a SQLAlchemy `MockConnection` whose
`dump` callable has no `return` statement:

```python
    def _stdout_connection(
        self, connection: Optional[Connection]
    ) -> MockConnection:
        def dump(construct, *multiparams, **params):
            self.impl._exec(construct)

        return MockEngineStrategy.MockConnection(self.dialect, dump)
```

#### What actually breaks, and the trap in how it breaks

The documentation's entire statement of offline limitations is one paragraph:

> The challenge of SQL script generation is that the scripts we generate can't rely upon any
> client/server database access. This means a migration script that pulls some rows into memory
> via a SELECT statement will not work in `--sql` mode.

— [Offline Mode](https://alembic.sqlalchemy.org/en/latest/offline.html)

There is no enumerated list. Everything more specific has to come from source, so here it is,
with the failure mode spelled out because it is nastier than "will not work" implies.

A data migration that reads — `op.get_bind().execute(select(...)).fetchall()` — fails offline
with `AttributeError: 'NoneType' object has no attribute 'fetchall'`, because `execute()`
returned `None`. But the `SELECT` **is still written into the output script**, compiled and
terminated like any DDL statement, because that is what `_exec` does with everything. The
handoff script you give the DBA contains a stray `SELECT` that does nothing. The script looks
plausible and is wrong.

> **Source disagrees with docs.** `Operations.get_bind` — `alembic/operations/base.py:528-538` —
> documents the opposite, and the author flagged their own doubt in the docstring:
>
> ```python
>     def get_bind(self) -> Connection:
>         """Return the current 'bind'.
>         ...
>         In a SQL script context, this value is ``None``. [TODO: verify this]
>
>         """
>         return self.migration_context.impl.bind  # type: ignore[return-value]
> ```
>
> It is not `None`; it is a `MockConnection`. Prefer the source. The practical consequence is
> that the natural defensive idiom `if op.get_bind() is not None:` guards nothing offline — it
> is always true. `MigrationContext.bind` (`migration.py:686-690`) has the accurate wording:
> *"this bind will be a 'mock' connection handler that cannot return results and is only
> appropriate for a very limited subset of commands."*

Four things are refused outright rather than silently mangled:

| Attempted offline | Error | Location |
| --- | --- | --- |
| `revision --autogenerate --sql` | `Using --sql with --autogenerate does not make any sense` | `command.py:207-209` |
| autogenerate reached programmatically | `autogenerate can't use as_sql=True as it prevents querying the database for schema information` | `autogenerate/api.py:344-347` |
| `upgrade --sql --purge` | `Can't use --purge with --sql mode` | `migration.py:596-597` |
| any bound parameter | `SQL parameters not allowed with as_sql` (`TypeError`) | `impl.py:215` |

That last one is why `op.bulk_insert()` takes a different branch offline: it inlines each row
as a literal, one `INSERT` per row (`impl.py:459-476`), rather than issuing one executemany.

#### The start revision — correcting a widely-held belief

It is commonly said that `upgrade --sql` requires an explicit start revision. It does not.
Docs and source agree, and both disagree with the folklore.

> Notice that our migration script started at the base - this is the default when using offline
> mode, as no database connection is present and there's no `alembic_version` table to read
> from.
>
> One way to provide a starting version in offline mode is to provide a range to the command
> line. This is accomplished by providing the "version" in `start:end` syntax [...]
>
> The `start:end` syntax is only allowed in offline mode; in "online" mode, the
> `alembic_version` table is always used to get at the current version.

— [Offline Mode, "Getting the Start Version"](https://alembic.sqlalchemy.org/en/latest/offline.html)

In `command.py::upgrade` (lines 386-406) `starting_rev` simply defaults to `None` and nothing
raises when it stays there. `command.py::downgrade` is the one that insists:

```python
    starting_rev = None
    if ":" in revision:
        if not sql:
            raise util.CommandError("Range revision not allowed")
        starting_rev, revision = revision.split(":", 2)
    elif sql:
        raise util.CommandError(
            "downgrade with --sql requires <fromrev>:<torev>"
        )
```

— `alembic/command.py:430-439`. So: `upgrade --sql` defaults to `base`; `downgrade --sql`
hard-requires `<from>:<to>`; and a range passed *without* `--sql` raises `Range revision not
allowed` from either command.

#### The version table under `--sql`

`run_migrations` (`migration.py:592-641`) treats the version table differently offline in three
places, and reading them precisely tells you what a handoff script will contain:

- `_ensure_version_table()` is **skipped entirely** when `as_sql` — the guard at line 605 is
  `if not self.as_sql and not heads and not dont_mutate:`.
- Instead, `CREATE TABLE alembic_version` is emitted **inline at the first step**, but only
  when the maintainer has no heads yet (lines 613-617). Pass a `start:end` range and no
  `CREATE TABLE` appears — correct, since the DBA's database already has one.
- `DROP TABLE alembic_version` is emitted when the script ends with no heads, i.e. a full
  downgrade to base (lines 639-641).
- Offline gets a `-- Running <step>` comment per migration (lines 619-622); online does not.

#### The transaction wrapper is dialect-dependent, and three dialects get none

The documented contract promises literal `BEGIN`/`COMMIT`:

> * If `is_offline_mode()` is `True`, returns a context manager that will invoke the
>   `DefaultImpl.emit_begin()` and `DefaultImpl.emit_commit()` methods, which will produce the
>   string directives `BEGIN` and `COMMIT` on the output stream, as rendered by the target
>   backend (e.g. SQL Server would emit `BEGIN TRANSACTION`).

— `EnvironmentContext.begin_transaction` docstring, `alembic/runtime/environment.py:990-1013`

But read the first clause of the same docstring — *"If `is_transactional_ddl()` is `False`,
returns a 'do nothing' context manager"* — and then the code, `migration.py:413-430`:

```python
        if self.impl.transactional_ddl:
            transaction_now = _per_migration == self._transaction_per_migration
        else:
            transaction_now = _per_migration is True

        if not transaction_now:
            return nullcontext()

        elif not self.impl.transactional_ddl:
            assert _per_migration

            if self.as_sql:
                return nullcontext()
```

On a backend with `transactional_ddl = False`, the offline branch returns `nullcontext()` and
**no `BEGIN` or `COMMIT` is emitted at all**. An offline SQLite or MySQL script is a bare
sequence of statements with no transaction wrapper — which is honest, since those backends
could not honour one for DDL anyway, but it is not what the docstring's second bullet leads you
to expect.

| Dialect | `transactional_ddl` | Terminator | Batch separator | Offline wrapper |
| --- | --- | --- | --- | --- |
| default | `False` (`impl.py:97`) | `";"` | — | none |
| postgresql | `True` (`postgresql.py:81`) | `";"` | — | `BEGIN;` … `COMMIT;` |
| mssql | `True` (`mssql.py:53`) | `";"` | `"GO"` (`mssql.py:54`) | `BEGIN TRANSACTION;` … `COMMIT;` + `GO` |
| mysql | `False` (`mysql.py:44`) | `";"` | — | **none** |
| sqlite | `False` (`sqlite.py:43`) | `";"` | — | **none** |
| oracle | `False` (`oracle.py:37`) | `""` (`oracle.py:39`) | `"/"` (`oracle.py:38`) | **none** |

SQLite's entry carries its reason in the source itself — `alembic/ddl/sqlite.py:43-46`:

```python
    transactional_ddl = False
    """SQLite supports transactional DDL, but pysqlite does not:
    see: http://bugs.python.org/issue10740
    """
```

Oracle's `command_terminator = ""` with `batch_separator = "/"` is the SQL\*Plus convention:
statements get no trailing semicolon and a `/` line after each. MSSQL's emitters are
asymmetric — `emit_begin` is fully overridden and emits no trailing `GO`, while `emit_commit`
calls super and then adds one (`mssql.py:73-84`).

The practical reading: **an offline script's transactional semantics are the target backend's,
not Alembic's.** Handing a DBA a PostgreSQL script means handing them something that rolls back
as a unit. Handing them a MySQL script does not.

### 4.2 Batch mode exists because SQLite stores its schema as text

The usual framing — "SQLite has a weak `ALTER TABLE`" — is true but incurious. SQLite explains
the cause itself:

> Most SQL database engines store the schema already parsed into various system tables. On
> those database engines, ALTER TABLE merely has to make modifications to the corresponding
> system tables.
>
> SQLite is different in that it stores the schema in the sqlite_schema table as the original
> text of the CREATE statements that define the schema. Hence ALTER TABLE needs to revise the
> text of the CREATE statement. Doing so can be tricky for certain "creative" schema designs.

— [SQLite, ALTER TABLE §9](https://www.sqlite.org/lang_altertable.html)

So the limitation is architectural, and SQLite says as much — Alembic's own docs call it
"philosophical and architectural concerns within SQLite, and they are unlikely to be changed"
([Batch Migrations](https://alembic.sqlalchemy.org/en/latest/batch.html)). What SQLite supports
is exactly four forms:

> SQLite supports a limited subset of ALTER TABLE. The ALTER TABLE command in SQLite allows
> these alterations of an existing table: it can be renamed; a column can be renamed; a column
> can be added to it; or a column can be dropped from it.

— [SQLite, ALTER TABLE §1](https://www.sqlite.org/lang_altertable.html)

#### SQLite's own 12-step procedure, and the ordering warning

For anything else, SQLite documents a procedure (§8, "Making Other Kinds Of Table Schema
Changes"): disable foreign keys, begin a transaction, record dependent objects, `CREATE TABLE
new_X`, `INSERT INTO new_X SELECT ... FROM X`, `DROP TABLE X`, `ALTER TABLE new_X RENAME TO X`,
rebuild indexes/triggers/views, `PRAGMA foreign_key_check`, commit, re-enable foreign keys.

The part worth quoting is the warning attached to it, because it is the reason Alembic's step
order is what it is and not the more obvious alternative:

> **Caution:** Take care to follow the procedure above precisely. The boxes below summarize two
> procedures for modifying a table definition. At first glance, they both appear to accomplish
> the same thing. However, the procedure on the right does not always work, especially with the
> enhanced rename table capabilities added by versions 3.25.0 and 3.26.0. In the procedure on
> the right, the initial rename of the table to a temporary name might corrupt references to
> that table in triggers, views, and foreign key constraints. The safe procedure on the left
> constructs the revised table definition using a new temporary name, then renames the table
> into its final name, which does not break links.

— [SQLite, ALTER TABLE §8](https://www.sqlite.org/lang_altertable.html)

| Correct | Incorrect |
| --- | --- |
| Create new table | Rename old table |
| Copy data | Create new table |
| Drop old table | Copy data |
| Rename new into old | Drop old table |

`ApplyBatchImpl._create` — `alembic/operations/batch.py:443-480` — implements the left-hand
column exactly:

```python
    def _create(self, op_impl: DefaultImpl) -> None:
        self._transfer_elements_to_new_table()

        op_impl.prep_table_for_batch(self, self.table)
        assert self.new_table is not None
        op_impl.create_table(self.new_table)

        try:
            op_impl._exec(
                _insert_inline(self.new_table).from_select(...)
            )
            op_impl.drop_table(self.table)
        except:
            op_impl.drop_table(self.new_table)
            raise
        else:
            op_impl.rename_table(
                self.temp_table_name, self.table.name, schema=self.table.schema
            )
            ...
```

Create new → copy → drop old → rename new into old, then rebuild indexes. The bare `except:`
that drops the temp table is not decoration: on SQLite `transactional_ddl` is `False`, so a
rollback cannot be relied on to clean up after a failed copy.

> **Source disagrees with docs — the temp table name.** The documentation shows
> `_alembic_batch_temp` in its worked example, and a source comment at `batch.py:352` repeats
> it. The actual name comes from `ApplyBatchImpl._calc_temp_name` — `batch.py:243-245`:
>
> ```python
>     @classmethod
>     def _calc_temp_name(cls, tablename: Union[quoted_name, str]) -> str:
>         return ("_alembic_tmp_%s" % tablename)[0:50]
> ```
>
> The real name is `_alembic_tmp_<tablename>`, truncated to 50 characters. Prefer the source.
> There is a consequence hiding in the truncation: the name is per-table, so it does not
> collide across tables in general — but two tables whose names share a long prefix can
> truncate to the same temp name.

#### When `recreate="auto"` actually recreates

The documented rule:

> :param recreate: under what circumstances the table should be recreated. At its default of
> `"auto"`, the SQLite dialect will recreate the table if any operations other than
> `add_column()`, `create_index()`, or `drop_index()` are present. Other options include
> `"always"` and `"never"`.

— `alembic/operations/base.py:299-303`

`SQLiteImpl.requires_recreate_in_batch` — `alembic/ddl/sqlite.py:48-74` — is that rule, plus
two escalations:

```python
        for op in batch_op.batch:
            if op[0] == "add_column":
                col = op[1][1]
                if isinstance(
                    col.server_default, schema.DefaultClause
                ) and isinstance(col.server_default.arg, sql.ClauseElement):
                    return True
                elif (
                    isinstance(col.server_default, util.sqla_compat.Computed)
                    and col.server_default.persisted
                ):
                    return True
            elif op[0] not in ("create_index", "drop_index"):
                return True
        else:
            return False
```

Even an `add_column` escalates to a full recreate if its server default is a SQL expression, or
if it is a persisted computed column. Those two escalations map precisely onto SQLite's own
stated `ADD COLUMN` restrictions — *"may not have a default value of CURRENT_TIME,
CURRENT_DATE, CURRENT_TIMESTAMP, or an expression in parentheses"* and *"may not be GENERATED
ALWAYS ... STORED, though VIRTUAL columns are allowed"* ([ALTER TABLE
§4](https://www.sqlite.org/lang_altertable.html)). The implementation is not approximating the
restriction; it is tracking it.

Two asymmetries worth knowing. `DefaultImpl.requires_recreate_in_batch` returns `False`
(`impl.py:176-187`), so non-SQLite backends never auto-recreate — batch mode on PostgreSQL is
a no-op wrapper around ordinary `ALTER TABLE` unless you pass `recreate="always"`. And
`drop_column` forces a full recreate on SQLite even though SQLite has supported `DROP COLUMN`
natively since 3.35.0; Alembic 1.14.1 does not take that shortcut.

#### What batch mode silently drops

`_grab_table_elements` — `batch.py:264-285` — sorts reflected constraints into three buckets,
and one of them is a hole:

```python
            elif (
                self.reflected
                and isinstance(const, CheckConstraint)
                and not const.name
            ):
                # TODO: we are skipping unnamed reflected CheckConstraint
                # because
                # we have no way to determine _is_type_bound() for these.
                pass
```

An unnamed CHECK constraint on a reflected table is discarded when the table is recreated.

> **Version gap worth stating precisely.** The published documentation says: *"Unnamed CHECK
> constraints continue to be omitted from the table recreate operation; up until version 1.20,
> this omission was silent. As of 1.20, it emits a warning."* On **1.14.1 the omission is
> silent** — the `pass` above has no `util.warn` anywhere near it. The docs are describing a
> version you are not running.
>
> A second, older staleness runs the other way. The `batch_alter_table` docstring at
> `operations/base.py:292-295` still carries pre-1.7 text: *"The table copy operation will
> currently not copy CHECK constraints, and may not copy UNIQUE constraints that are unnamed."*
> That contradicts both the docs (*"As of Alembic 1.7, named CHECK constraints are automatically
> included in batch mode"*) and the 1.14.1 code above, which routes named CHECK constraints into
> `self.named_constraints`. Here the **docstring** is the stale one: named CHECK constraints do
> participate in 1.14.1; only unnamed ones vanish.

There is a second silent drop, this one undocumented. `_transfer_elements_to_new_table` —
`batch.py:345-346`:

```python
            if not const_columns.issubset(self.column_transfers):
                continue
```

Any constraint touching a dropped column is discarded without comment.

And a set of limitations that live only in source:

| Behaviour | Location |
| --- | --- |
| `create_table` / `drop_table` inside a batch block raise `NotImplementedError` | `batch.py:203-207` |
| `rename_table` inside a recreate batch raises `NotImplementedError("TODO")` | `batch.py:716-717` |
| `insert_before` / `insert_after` on `add_column` require `recreate="always"` | `batch.py:169-177` |
| `drop_index` for a non-reflected index raises `ValueError("No such index: '%s'")` | `batch.py:710-714` |
| Any constraint covering a dropped column is silently discarded | `batch.py:345-346` |
| Temp table name truncated to 50 chars → possible collision on long names | `batch.py:243-245` |

#### Where batch mode and offline mode collide

Batch mode's whole method rests on reflecting the existing table. Offline mode has no database
to reflect from. The two features are therefore mutually exclusive by construction, and
`BatchOperationsImpl.flush` says so with an unusually long error — `batch.py:128-140`:

```python
                    if self.operations.migration_context.as_sql:
                        raise exc.CommandError(
                            f"This operation cannot proceed in --sql mode; "
                            f"batch mode with dialect "
                            f"{self.operations.migration_context.dialect.name} "
                            f"requires a live database connection with which "
                            f'to reflect the table "{self.table_name}". '
                            ...
                        )
```

The documented escape is to hand Alembic the table definition it would otherwise reflect:

> To support offline mode, the system must work without table reflection present, which means
> the full table as it intends to be created must be passed to `Operations.batch_alter_table()`
> using `copy_from` [...] The above use pattern is pretty tedious and quite far off from
> Alembic's preferred style of working; however, if one needs to do SQLite-compatible "move and
> copy" migrations and need them to generate flat SQL files in "offline" mode, there's not much
> alternative.

— [Batch Migrations, "Working in Offline Mode"](https://alembic.sqlalchemy.org/en/latest/batch.html)

And autogenerate does not bridge the gap:

> Note that autogenerate support does not include "offline" mode, where the
> `Operations.batch_alter_table.copy_from` parameter is used. The table definition here would
> need to be entered into migration files manually if this is needed.

— same page

#### One thing batch mode does not do for you

SQLite's procedure begins with `PRAGMA foreign_keys=OFF` and ends with re-enabling it, and
Alembic's docs restate the requirement:

> It is important to note that batch table operations do not work with foreign keys that
> enforce referential integrity. This because the target table is dropped; if foreign keys refer
> to it, this will raise an error. On SQLite, whether or not foreign keys actually enforce is
> controlled by the `PRAGMA FOREIGN KEYS` pragma; this pragma, if in use, must be disabled when
> the workflow mode proceeds.

— [Batch Migrations](https://alembic.sqlalchemy.org/en/latest/batch.html)

Alembic does not emit those pragmas. There is no `foreign_keys` pragma emission anywhere in
`alembic/ddl/sqlite.py`. That step is the operator's.

#### Batch on backends that do support ALTER

The documented reason to reach for `recreate="always"` elsewhere is lock avoidance:

> There's an odd use case some shops have, where the "move and copy" style of migration is
> useful in some cases for databases that do already support ALTER. There's some cases where an
> ALTER operation may block access to the table for a long time, which might not be acceptable.

— [Batch Migrations](https://alembic.sqlalchemy.org/en/latest/batch.html)

It is worth being clear-eyed about this, given §2: move-and-copy on PostgreSQL does not
avoid the lock so much as relocate it. The `DROP TABLE` and `RENAME` at the end take ACCESS
EXCLUSIVE anyway, and the copy window is one during which writes to the original table are lost
unless you have arranged otherwise. The docs are candid about the unautomated parts:

> Since a new table is replacing the old one, existing foreign key constraints which refer to
> the target table will need to be unconditionally dropped before the batch operation, and
> re-created to refer to the new table afterwards. **Batch mode currently does not provide any
> automation for this.**

— same page

PostgreSQL additionally needs the old table's constraint names freed before the new table can
claim them, which is `PostgresqlImpl.prep_table_for_batch` — `alembic/ddl/postgresql.py:98-104`:

```python
    def prep_table_for_batch(self, batch_impl, table):
        for constraint in table.constraints:
            if (
                constraint.name is not None
                and constraint.name in batch_impl.named_constraints
            ):
                self.drop_constraint(constraint)
```

called from `_create` before `create_table`. The base-class hook is a no-op.

### 4.3 Concurrent deploys: what Alembic provides is nothing

This is the part of the brief where the honest answer is the shortest, and it needs to be
established as an absence rather than asserted.

#### The documentation contains no concurrency material at all

Searching the pages named in the brief is not sufficient to prove an absence, so the whole
published Sphinx search index was searched instead —
`https://alembic.sqlalchemy.org/en/latest/searchindex.js`, which covers every page including
the full changelog. Stemmed whole-word hit counts:

```
advisori      0        (control group, same index:)
concurr       0          batch        8
mutex         0          sqlite      41
lock          0          stamp        8
kubernet      0          offlin       2
deploy        1
```

The control group establishes that the index and the method work. **There is no page,
paragraph, or changelog entry in the Alembic documentation about running migrations
concurrently, about mutual exclusion, about advisory locks, or about rolling deploys.** The
single `deploy` hit is a cookbook sentence about slow DDL, not concurrency. There is no FAQ
page to consult — `faq.html` is a JavaScript search stub, not a content page.

#### The source contains no locking primitive

An exhaustive grep over the entire package:

```
$ grep -rniE "advisory|for_update|for update|lock" alembic-src/alembic/ | wc -l
35
$ grep -rniE "advisory|for_update|for update|lock" alembic-src/alembic/ \
      | grep -viE "block" | wc -l
0
```

All 35 hits are the English word *block* — `autocommit_block`, prose about "transaction block",
test names, a comment reading "assert outside the block". Zero hits for `advisory`,
`pg_advisory`, `FOR UPDATE`, `LOCK TABLE`, `threading.Lock`, or any mutex of any kind.

**Alembic 1.14.1 has no built-in mutual exclusion of any form.** Nothing serialises two
`alembic upgrade head` processes except the database's own transaction semantics.

The read that starts every migration run is a bare `SELECT`. `get_current_heads` —
`migration.py:533-539`:

```python
        assert self.connection is not None
        return tuple(
            row[0]
            for row in self.connection.execute(
                _select(self._version.c.version_num)
            )
        )
```

No `.with_for_update()`, no execution option. It compiles to `SELECT
alembic_version.version_num FROM alembic_version`. Two processes starting together both read
the same head and both compute the same list of migrations to run.

There is a second, narrower race on a virgin database. `_ensure_version_table` uses
`self._version.create(self.connection, checkfirst=True)` (`migration.py:541-547`), and
`checkfirst=True` is a read-then-write with no lock: two processes can both observe the table
as absent and both attempt the `CREATE`. Because it is guarded by `not heads` in
`run_migrations`, this window exists on first-ever deploy only.

#### The compare-and-swap is the only serialisation point — and it is post-hoc

§3.1 established the mechanism; what matters here is its scope. `HeadMaintainer._update_version`
— `migration.py:792-817` — emits

```sql
UPDATE alembic_version SET version_num='<to>' WHERE alembic_version.version_num = '<from>'
```

and raises unless exactly one row matched:

```python
        if (
            not self.context.as_sql
            and self.context.dialect.supports_sane_rowcount
            and ret is not None
            and ret.rowcount != 1
        ):
            raise util.CommandError(
                "Online migration expected to match one "
                "row when updating '%s' to '%s' in '%s'; "
                "%d found"
                % (from_, to_, self.context.version_table, ret.rowcount)
            )
```

Alembic's author describes it in exactly those terms — *"the UPDATE is performed using a
standard compare and swap technique"*
([sqlalchemy/alembic#633](https://github.com/sqlalchemy/alembic/issues/633), 2019-12-06).

What it catches is the **bookkeeping** race: if another process advanced the row first, the
`WHERE` matches zero rows and this process aborts with a clear `CommandError` rather than
silently double-stamping.

What it does not catch is the **DDL** race, and the reason is the ordering established in
§3.1. `head_maintainer.update_to_step(step)` runs at `migration.py:630`, *after*
`step.migration_fn(**kw)` at line 623. The `CREATE TABLE` and `ALTER TABLE` statements have
already been issued before the version row is touched. So:

- On a **transactional-DDL** backend (PostgreSQL, MSSQL), the DDL and the version `UPDATE` are
  in the same transaction, so the loser's `CommandError` rolls the DDL back with it. The
  outcome is an ugly failure, but a safe one.
- On a **non-transactional-DDL** backend (MySQL, SQLite, Oracle), the DDL has already
  committed and cannot be rolled back. The loser leaves the schema half-changed and the version
  table inconsistent with it.

Three further preconditions narrow the guard:

| Situation | Behaviour | Evidence |
| --- | --- | --- |
| Loser's `UPDATE` matches 0 rows | `CommandError: Online migration expected to match one row when updating ...; 0 found` | `migration.py:806-817` |
| Same, on a branch-delete step | `CommandError: ... when deleting '<v>' ...; 0 found` | `migration.py:779-790` |
| Branch-create step (`INSERT`) | **no check at all** | `migration.py:759-767` |
| Offline (`--sql`) | **check disabled** — `not self.context.as_sql` | `migration.py:806-811` |
| Dialect without sane rowcount | check disabled | `migration.py:808` |

`supports_sane_rowcount` is `True` on all five major dialects in SQLAlchemy 2.0.36, so in
practice only the offline and `INSERT` exclusions bite.

The defensible summary: **the compare-and-swap serialises the bookkeeping, converting a
concurrent run into a rolled-back `CommandError` on transactional-DDL backends — not into a
correct queued migration, and not into anything at all on the backends that need it most.**

#### The maintainer's position, which is first-party but not documentation

The absence is deliberate, and the project says so — on the issue tracker, which is
authoritative about intent but carries no versioned guarantee. Mike Bayer (`@zzzeek`), Alembic's
author, [2025-05-18](https://github.com/sqlalchemy/alembic/issues/633):

> I really dont have an answer as to specifics, it should be noted that I personally don't
> support the "run Alembic concurrently" use case and implementing it is up to the people who
> want this sort of thing to work. The reason Alembic has the `env.py` architecture is so that
> the entire process and connectivity model is open-ended so that we (alembic devs, mostly me)
> don't have to be on the hook to maintain cases like this ourselves.

And, asked directly about running `alembic upgrade head` on every instance start in an
autoscaling group
([discussion #1438](https://github.com/sqlalchemy/alembic/discussions/1438), 2024-03-07):

> yah that's totally not correct, you'd have multiple connections all trying to run the same
> CREATE / ALTER statements etc. and conflicting. you need to run just one connection at a time
> with DDL in it, you can't mix those things up.
>
> usually the part of the program that runs migrations is separate from the part of the program
> that handles requests, so the "run the migrations" part would not be in an "auto scaled"
> system. it would be part of whatever your framework uses for building up initial setup.

That is the clearest first-party statement of the "migrate as a separate step, then deploy"
practice that exists — and it is a tracker comment, not documentation. Label it accordingly.

#### If you must serialise it yourself

Since Alembic provides nothing, the exclusion has to come from the database, and `env.py` is
the documented place to put it. PostgreSQL's advisory locks are the fit:

> PostgreSQL provides a means for creating locks that have application-defined meanings. These
> are called advisory locks, because the system does not enforce their use — it is up to the
> application to use them correctly. Advisory locks can be useful for locking strategies that
> are an awkward fit for the MVCC model.

— [13.3.5. Advisory Locks](https://www.postgresql.org/docs/16/explicit-locking.html)

The session/transaction distinction is the crux, and it is documented precisely:

> There are two ways to acquire an advisory lock in PostgreSQL: at session level or at
> transaction level. Once acquired at session level, an advisory lock is held until explicitly
> released or the session ends. Unlike standard lock requests, session-level advisory lock
> requests do not honor transaction semantics: a lock acquired during a transaction that is
> later rolled back will still be held following the rollback [...] Transaction-level lock
> requests, on the other hand, behave more like regular lock requests: they are automatically
> released at the end of the transaction, and there is no explicit unlock operation.

— [13.3.5. Advisory Locks](https://www.postgresql.org/docs/16/explicit-locking.html)

`pg_advisory_xact_lock(key)` "obtains an exclusive transaction-level advisory lock, waiting if
necessary"; `pg_try_advisory_xact_lock(key)` "will either obtain the lock immediately and return
true, or return false without waiting"
([9.27.10. Advisory Lock Functions](https://www.postgresql.org/docs/16/functions-admin.html)).
The `try_` forms are what you want in a deploy pipeline: a second migrator that returns `false`
can exit zero and let the winner proceed, rather than piling up in a lock queue behind it.

Two caveats, both sourced.

**The maintainer's own suggestion has a known hole.** The `LOCK TABLE alembic_version IN ACCESS
EXCLUSIVE MODE` recipe in issue #633 cannot protect the case where the table does not exist yet
— the virgin-database race above. An advisory lock does not depend on the table existing,
which is why later commenters on that issue moved to `pg_advisory_xact_lock`. Those specific
`env.py` recipes are *user* comments; the maintainer explicitly declined to endorse them.

**Session-level advisory locks and connection poolers do not mix.** PostgreSQL's manual does
not discuss connection pooling — the only `pool` references on the locking pages are about
shared memory. The first-party statement comes from PgBouncer's own feature matrix, which lists
"Session-level advisory locks" as `Yes` under session pooling and **`Never`** under transaction
pooling ([PgBouncer Features](https://www.pgbouncer.org/features.html)). Transaction-level
advisory locks are not listed as broken, because they are released at transaction end. That is
the concrete reason to prefer `pg_advisory_xact_lock` behind a pooler — with the corresponding
limitation that a transaction-scoped lock cannot span a multi-transaction migration run, so
`transaction_per_migration` or an `autocommit_block` (§3.1) will step outside its protection.

#### A deploy gate that is documented

Separately from exclusion, the cookbook documents a read-only check that the database is at
head, useful as a pipeline gate before starting application instances:

```
alembic current --check-heads
...
ERROR [alembic.util.messaging] Database is not on all head revisions
FAILED: Database is not on all head revisions
```

— [Cookbook, "Test current database revision is at head(s)"](https://alembic.sqlalchemy.org/en/latest/cookbook.html)

Note the version: `--check-heads` arrived in **1.17.1**, so it is not available in 1.14.1. On
1.14.1 the same check has to be the hand-rolled recipe the cookbook also gives — compare
`ScriptDirectory.get_heads()` against `MigrationContext.get_current_heads()`. It is a gate, not
a lock: it tells you whether to proceed, not whether anyone else is already proceeding.

---

## 5. Sources

Everything below was fetched and read while writing this document. Source trees
were installed locally and read on disk rather than browsed, so that line numbers
correspond to a specific released version.

### Source code read on disk

| Artefact | Version | Established by |
| --- | --- | --- |
| Alembic | **1.14.1** | `alembic/__init__.py`: `__version__ = "1.14.1"` |
| SQLAlchemy | **2.0.36** | `SQLAlchemy-2.0.36.dist-info/METADATA` |

Installed with `uv pip install --target ./alembic-src "alembic==1.14.1"
"SQLAlchemy==2.0.36"`. Every `file.py:NNN` citation in §3 and §4 refers to this
tree. Files read in full or in substantial part: `alembic/runtime/migration.py`,
`alembic/runtime/environment.py`, `alembic/script/base.py`,
`alembic/script/revision.py`, `alembic/autogenerate/compare.py`,
`alembic/autogenerate/api.py`, `alembic/operations/base.py`,
`alembic/operations/batch.py`, `alembic/operations/toimpl.py`,
`alembic/operations/ops.py`, `alembic/ddl/base.py`, `alembic/ddl/impl.py`,
`alembic/ddl/postgresql.py`, `alembic/ddl/mysql.py`, `alembic/ddl/sqlite.py`,
`alembic/ddl/mssql.py`, `alembic/ddl/oracle.py`, `alembic/command.py`,
`alembic/util/sqla_compat.py`, and `sqlalchemy/engine/mock.py`.

### PostgreSQL 16

| Section | URL |
| --- | --- |
| `ALTER TABLE` | <https://www.postgresql.org/docs/16/sql-altertable.html> |
| `CREATE INDEX` | <https://www.postgresql.org/docs/16/sql-createindex.html> |
| `ALTER TYPE` | <https://www.postgresql.org/docs/16/sql-altertype.html> |
| `BEGIN` | <https://www.postgresql.org/docs/16/sql-begin.html> |
| 3.4. Transactions (tutorial) | <https://www.postgresql.org/docs/16/tutorial-transactions.html> |
| 13.3. Explicit Locking (incl. §13.3.5 Advisory Locks) | <https://www.postgresql.org/docs/16/explicit-locking.html> |
| 13.6. Caveats (MVCC) | <https://www.postgresql.org/docs/16/mvcc-caveats.html> |
| 9.27. System Administration Functions §9.27.10 | <https://www.postgresql.org/docs/16/functions-admin.html> |
| 20.11. Client Connection Defaults (`lock_timeout`, `statement_timeout`) | <https://www.postgresql.org/docs/16/runtime-config-client.html> |
| 53.26. `pg_index` | <https://www.postgresql.org/docs/16/catalog-pg-index.html> |
| 55.75. `pg_locks` | <https://www.postgresql.org/docs/16/view-pg-locks.html> |
| 55.2.3. Extended Query protocol flow | <https://www.postgresql.org/docs/16/protocol-flow.html> |

One page from an earlier release is cited deliberately, to date a change in
behaviour rather than to describe the target version:
<https://www.postgresql.org/docs/11/sql-altertype.html>.

### MySQL 8.0 (used for contrast)

| Section | URL |
| --- | --- |
| 15.1.1 Atomic Data Definition Statement Support | <https://dev.mysql.com/doc/refman/8.0/en/atomic-ddl.html> |
| 15.3.3 Statements That Cause an Implicit Commit | <https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html> |
| 15.1.9 `ALTER TABLE` | <https://dev.mysql.com/doc/refman/8.0/en/alter-table.html> |
| 17.12.1 Online DDL Operations | <https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html> |
| 17.12.5 Online DDL Performance and Concurrency | <https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html> |

### SQLite

| Section | URL |
| --- | --- |
| ALTER TABLE (all sections; §8 "Making Other Kinds Of Table Schema Changes" and §9 "Why ALTER TABLE is such a problem for SQLite" in particular) | <https://www.sqlite.org/lang_altertable.html> |
| pysqlite transactional-DDL bug, cited by Alembic's own source comment | <http://bugs.python.org/issue10740> |

### Alembic documentation (published version 1.20.0 — see the caveat in Scope)

| Page | URL |
| --- | --- |
| Auto Generating Migrations | <https://alembic.sqlalchemy.org/en/latest/autogenerate.html> |
| Working with Branches | <https://alembic.sqlalchemy.org/en/latest/branches.html> |
| Running "Batch" Migrations for SQLite and Other Databases | <https://alembic.sqlalchemy.org/en/latest/batch.html> |
| Generating SQL Scripts (a.k.a. "Offline Mode") | <https://alembic.sqlalchemy.org/en/latest/offline.html> |
| Cookbook | <https://alembic.sqlalchemy.org/en/latest/cookbook.html> |
| Tutorial | <https://alembic.sqlalchemy.org/en/latest/tutorial.html> |
| Runtime Objects | <https://alembic.sqlalchemy.org/en/latest/api/runtime.html> |
| Sphinx search index — used to *prove absence*, not to source a claim | <https://alembic.sqlalchemy.org/en/latest/searchindex.js> |

### First-party, but not documentation

These are statements by Alembic's author on the project's own trackers. They are
authoritative about intent and carry no versioned guarantee. They are quoted in
§4.3 and labelled there.

| Thread | URL |
| --- | --- |
| Issue #633, "Is multiple alembic upgrades ok to run concurrent?" | <https://github.com/sqlalchemy/alembic/issues/633> |
| Discussion #1438, "Question regarding multiple instances run alembic head upgrade at the same time" | <https://github.com/sqlalchemy/alembic/discussions/1438> |

### Non-vendor sources, used only where no vendor source exists

| Source | Used for | URL |
| --- | --- | --- |
| Danilo Sato, *Parallel Change* (2014), on martinfowler.com | The name and canonical description of expand/contract — see §2.10, where the absence of any vendor source for the pattern is stated explicitly | <https://martinfowler.com/bliki/ParallelChange.html> |
| PgBouncer, *Features* — SQL feature map for pooling modes | The incompatibility of session-level advisory locks with transaction pooling, which the PostgreSQL manual does not discuss | <https://www.pgbouncer.org/features.html> |

---

## 6. What could not be verified

Seven things in this document rest on something weaker than a vendor sentence.
They are flagged in place; they are collected here so the gaps are countable.

**1. PostgreSQL never affirmatively states that DDL is transactional.** There is
no sentence to quote. The property is established in §1.1 negatively — the manual
defines a transaction block without carving DDL out of it, then enumerates across
a dozen reference pages the specific statements that *cannot* run inside one. That
enumeration would be pointless if DDL in general were not transactional, so the
inference is safe. It is still an inference.

**2. `current transaction is aborted, commands ignored until end of transaction
block` is a server error message, not documentation.** It describes the
half-failed-migration behaviour in §1.2 exactly, and it is emitted by the server
rather than written by a technical writer. No manual section states the rule it
implies.

**3. PostgreSQL never documents the lock-queue convoy.** The fact that a waiting
`ACCESS EXCLUSIVE` request blocks the `ACCESS SHARE` requests queued behind it —
so a single slow `ALTER TABLE` stalls readers that do not conflict with it — is
the single most consequential operational fact in §2. PostgreSQL's manual does not
state it. §2.7 sources it from MySQL's manual, which documents the equivalent
metadata-lock behaviour with a three-session worked example, and says plainly that
this is a citation by analogy.

**4. PostgreSQL 16 does not state whether `ADD COLUMN` with an identity or
generated-stored specification rewrites the table.** The `ALTER TABLE` page's
rewrite discussion covers volatile defaults and type changes and stops there.
§2.2's table marks the cell as undocumented rather than guessing.

**5. Expand/contract appears in no vendor manual.** Not PostgreSQL's, not
MySQL's, not Alembic's. It is a practitioner pattern, and §2.10 attributes it as
one: named and written up by Danilo Sato in 2014, credited by Sato to Joshua
Kerievsky's 2006 refactoring work. Its *mechanics* are grounded — every step it
prescribes is one of the safe operations in §2.2, each individually vendor-sourced
— but the pattern as a pattern has no vendor owner.

**6. There is no Alembic 1.14 documentation online.** `/en/rel_1_14/` is not
published and `/en/release-1.14.0/` returns 404. Every documentation quote in §3
and §4 is from 1.20.0, checked against 1.14.1 source. Where they disagree — the
batch temp-table name, the `get_bind()` offline return value, the unnamed-CHECK
warning, the CHECK-constraint autogenerate comparator, the stale
`batch_alter_table` docstring — the source is preferred and the disagreement is
stated in place. It is not always possible to tell whether a 1.20 documentation
statement was *also* true at 1.14 except by reading the source, which is what was
done.

**7. "Run migrations as a separate step, before rolling out application
instances" has no documented owner.** It is not in the Alembic documentation —
§4.3 proves this exhaustively against the complete published search index, which
returns zero hits for `concurr`, `lock`, `advisori`, `mutex` and `kubernet`
against a working control group. It is not in the SQLAlchemy or PostgreSQL
documentation either. Its only first-party support is a maintainer comment on the
project's discussion tracker, dated 2024-03-07 and quoted in §4.3: *"usually the
part of the program that runs migrations is separate from the part of the program
that handles requests."* That is a statement of intent by the author, not
documentation, not versioned, and carries no guarantee.

Everything beyond that comment — Kubernetes init containers, Job-before-Deployment
ordering, Helm pre-install hooks, and the rest of the deployment folklore around
this — is **unverified practitioner consensus**. No first-party source for any of
it was found, and none is named here rather than cite one that was not read. The
same applies to the specific advisory-lock `env.py` recipes quoted in §4.3: those
are *user* comments on the issue tracker, not covered by Alembic's test suite, and
the maintainer explicitly declined to endorse them. One commenter there reports
that advisory locking did not fully prevent concurrent-upgrade errors in their
testing; that claim was not reproduced and is not repeated as fact.
