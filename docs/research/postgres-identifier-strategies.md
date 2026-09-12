# Primary Keys and External Identifiers in PostgreSQL

A study guide, built from primary sources.

**Scope.** This is an educational deep dive for someone choosing an identifier
strategy for a PostgreSQL schema. It covers seven candidates — `bigint` identity,
UUIDv4, UUIDv7, ULID, Twitter Snowflake, TypeID, and natural/semantic keys —
across four questions: what they cost in storage and index mechanics, what the
engine can generate natively, what they expose to an attacker, and how the
increasingly common dual-identifier pattern (internal `bigint` surrogate plus
external public id) actually behaves.

**Sourcing.** Every substantive claim is tied to a source fetched and read while
writing this document. Definitions and normative statements are quoted rather
than paraphrased. Three grades of evidence are kept visibly distinct:

1. **Documented guarantees** — the PostgreSQL manual, RFC 9562, vendor specs.
2. **Source code** — `REL_18_STABLE` header files and READMEs, used only where
   the manual is silent, and labelled every time. A `#define` is not a promise.
3. **My arithmetic** — derived from quoted constants, always labelled as derived.

Where a number everybody repeats turns out not to be in any specification, this
document says so rather than supplying it. [§8](#8-what-could-not-be-verified)
records every such case.

**Version.** PostgreSQL 18 is the current stable major, first released
2025-09-25; the current minor is 18.6, released 2026-08-13. Unqualified
references to "the docs" mean the 18.6 build of `/docs/current/`.

---

## Contents

1. [The Shape of the Decision](#1-the-shape-of-the-decision)
2. [Storage and Index Mechanics](#2-storage-and-index-mechanics)
3. [What PostgreSQL Can Generate](#3-what-postgresql-can-generate)
4. [The Candidates](#4-the-candidates)
5. [Security, Collisions, and Offline Generation](#5-security-collisions-and-offline-generation)
6. [The Dual-Identifier Architecture](#6-the-dual-identifier-architecture)
7. [Sources](#7-sources)
8. [What could not be verified](#8-what-could-not-be-verified)

---

## 1. The Shape of the Decision

### 1.1 One column, two unrelated jobs

Most arguments about primary keys go badly because the participants are
optimising different things without saying so. A key column is asked to do two
jobs that have almost nothing in common:

- **Internal identity.** Join children to parents, anchor indexes, survive
  physical reorganisation. Judged on width, ordering, and immutability.
- **External reference.** Appear in URLs, API payloads, support tickets, and
  webhook bodies. Judged on opacity, portability, and whether a client can mint
  one before the database has seen it.

A single column can do both, and for most systems it should — but the moment the
two sets of requirements conflict, you are no longer choosing a key type. You
are choosing which job to sacrifice. [§6](#6-the-dual-identifier-architecture)
covers the pattern that refuses to choose.

### 1.2 What the relational model actually says

The term "primary key" comes from Codd's 1970 paper, and it is worth reading
what he wrote rather than what is usually attributed to him:

> Normally, one domain (or combination of domains) of a given relation has values
> which uniquely identify each element (n-tuple) of that relation. Such a domain
> (or combination) is called a primary key. In the example above, part number
> would be a primary key, while part color would not be. A primary key is
> nonredundant if it is either a simple domain (not a combination) or a
> combination such that none of the participating simple domains is superfluous in
> uniquely identifying each element. A relation may possess more than one
> nonredundant primary key. [...] Whenever a relation has two or more nonredundant
> primary keys, **one of them is arbitrarily selected and called the primary key of
> that relation.**

— E. F. Codd, "A Relational Model of Data for Large Shared Data Banks",
*Communications of the ACM* 13(6), June 1970, p. 379. Read from the
[University of Pennsylvania mirror](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf)
of the scanned original; canonical record at
[dl.acm.org](https://dl.acm.org/doi/10.1145/362384.362685).

Two things in that passage are routinely misremembered. First, the choice among
candidate keys is **arbitrary** — Codd attaches no significance to which one you
pick, which undercuts any appeal to "the relational model" in defence of a
particular style. Second, his own worked example of a primary key, `part number`,
is a *natural* key. Codd is not the authority for surrogate keys; the word
"surrogate" does not appear in the 1970 paper.

His definition of a foreign key, from the same page, is the one that makes
§6 coherent:

> We shall call a domain (or domain combination) of relation R a foreign key if it
> is not the primary key of R but its elements are values of the primary key of
> some relation S

### 1.3 What PostgreSQL enforces

> A primary key constraint indicates that a column, or group of columns, can be
> used as a unique identifier for rows in the table. This requires that the values
> be both unique and not null.
>
> Adding a primary key will automatically create a unique B-tree index on the
> column or group of columns listed in the primary key, and will force the
> column(s) to be marked `NOT NULL`.
>
> A table can have at most one primary key. (There can be any number of unique
> constraints, which combined with not-null constraints are functionally almost
> the same thing, but only one can be identified as the primary key.) **Relational
> database theory dictates that every table must have a primary key. This rule is
> not enforced by PostgreSQL**, but it is usually best to follow it.

— [§5.5.4, Primary Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)

The parenthesis matters for §6: a `UNIQUE` constraint plus `NOT NULL` is
"functionally almost the same thing" as a primary key. PostgreSQL's primary key
is a *designation*, not a distinct physical structure. Both produce the same
unique B-tree index.

The one privilege the designation carries is documented on the same page: "the
primary key defines the default target column(s) for foreign keys referencing
its table."

---

## 2. Storage and Index Mechanics

### 2.1 Where these numbers come from

Three figures that appear in every blog post on this subject are **not in the
PostgreSQL manual**:

- The manual calls `uuid` a "128-bit quantity" and gives no byte count.
- It says a B-tree entry "cannot exceed approximately one-third of a page" and
  never says 2704.
- It does not describe the rightmost-page fastpath for ascending inserts at all.
  A full-text search of `btree.html` for "fastpath", "rightmost", "ascending" and
  "monotonic" returns zero hits.

Each lives in the source tree, and the manual explicitly sends you there:

> See `src/backend/access/nbtree/README` in the source distribution for a much
> more detailed, internals-focused description of the B-Tree implementation.

— [§65.1.4](https://www.postgresql.org/docs/current/btree.html)

So: the manual where the manual speaks, `REL_18_STABLE` source where it does not,
labelled each time.

### 2.2 The quoted constants

| Constant | Value | Source |
| --- | --- | --- |
| Page size | "usually 8 kB" | [§66.6](https://www.postgresql.org/docs/current/storage-page-layout.html) |
| `PageHeaderData` | "24 bytes long" | §66.6, Table 66.2 |
| `ItemIdData` (line pointer) | "4 bytes per item" | §66.6, Table 66.2 |
| Heap tuple header | "occupying 23 bytes on most machines" | §66.6.1 |
| `bigint` | "8 bytes" | [§8.1, Table 8.2](https://www.postgresql.org/docs/current/datatype-numeric.html) |
| `uuid` | "128-bit quantity" | [§8.12](https://www.postgresql.org/docs/current/datatype-uuid.html) |
| Short string (≤126 bytes) | "1 byte plus the actual string" | [§8.3](https://www.postgresql.org/docs/current/datatype-character.html) |
| Max index entry | "approximately one-third of a page" | [§65.1.1](https://www.postgresql.org/docs/current/btree.html) |
| B-tree default fillfactor | "90" | [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) |

From source, for what the manual omits:

- `#define UUID_LEN 16` — `src/include/utils/uuid.h`. This is where "16 bytes"
  comes from.
- `IndexTupleData` = `ItemPointerData` (6) + `unsigned short` (2) = **8 bytes** —
  `src/include/access/itup.h`.
- `BTMaxItemSize` evaluates to **2704** at 8 kB pages — `src/include/access/nbtree.h`.

MAXALIGN is 8 on 64-bit platforms. The manual never states the value, only that
`t_hoff` "must always be a multiple of the MAXALIGN distance for the platform".
Treat it as a platform fact, not a documented constant.

On text keys specifically, the docs pre-empt a common assumption:

> There is no performance difference among these three types, apart from
> increased storage space when using the blank-padded type, and a few extra CPU
> cycles to check the length when storing into a length-constrained column. While
> `character(n)` has performance advantages in some other database systems, there
> is no such advantage in PostgreSQL; in fact `character(n)` is usually the
> slowest of the three because of its additional storage costs.

— [§8.3](https://www.postgresql.org/docs/current/datatype-character.html)

So `varchar(26)` buys nothing over `text`. If you store an identifier as a string,
store it as `text` with a `CHECK`.

### 2.3 Per-entry arithmetic

**Everything in this subsection is computed, not quoted.** Assumptions: 8 kB
pages, MAXALIGN 8, single-column `NOT NULL` key, no `INCLUDE` columns, ASCII text.

A B-tree leaf page has 8192 − 24 (page header) − 16 (`BTPageOpaqueData`) =
**8152 bytes** to share between line pointers and tuples.

| Key | tuple header | + key | MAXALIGNed | + line ptr | per entry |
| --- | --- | --- | --- | --- | --- |
| `bigint` | 8 | 8 | 16 | 4 | **20 bytes** |
| `uuid` | 8 | 16 | 24 | 4 | **28 bytes** |
| `text`, 26 chars | 8 | 1 + 26 = 27 | 40 | 4 | **44 bytes** |

Giving entries per leaf page:

| Key | at 100% | at fillfactor 90 | relative |
| --- | --- | --- | --- |
| `bigint` | 407 | ~366 | 1.00 |
| `uuid` | 291 | ~262 | 0.72 |
| `text`, 26 chars | 185 | ~166 | 0.45 |

**This model is checkable against the manual, and it checks out.** The
`pageinspect` documentation prints real output for `pg_proc_oid_index`:

> `live_items | 367`, `avg_item_size | 16`, `page_size | 8192`, `free_size | 808`

— [§F.23.3](https://www.postgresql.org/docs/current/pageinspect.html)

A 4-byte `oid` key gives 8 + 4 = 12 → MAXALIGN 16: the same item size as a
`bigint`. The model predicts 8152 − 367 × 20 = 812 bytes free, and
`PageGetFreeSpace` withholds one further line pointer, giving 808 — the number
the manual prints. And 367 / 407 = 90.2%, the documented fillfactor arriving on
its own.

**A `uuid` primary-key index needs roughly 1.4× the leaf pages of a `bigint` one;
a 26-character text key roughly 2.2×.**

### 2.4 Index depth barely moves

This is where the folklore overreaches. Taking fan-out ≈ 366 / 262 / 166:

| Rows | `bigint` | `uuid` | `text`(26) |
| --- | --- | --- | --- |
| 10⁶ | 3 levels | 3 | 3 |
| 10⁸ | 4 | 4 | 4 |
| 10¹⁰ | 4 | 5 | 5 |

Depth is logarithmic in fan-out, so a 28% fan-out reduction usually buys zero
extra levels and occasionally one. **Key width is a size problem, not a depth
problem.** Anyone claiming UUID keys cost you a tree level at realistic table
sizes is not doing the arithmetic.

What does follow from the size difference is cache pressure: the same working
set occupies 1.4× the pages, competing for a `shared_buffers` whose default is
"typically 128 megabytes" and whose recommended starting point is "25% of the
memory in your system"
([§20.4.1](https://www.postgresql.org/docs/current/runtime-config-resource.html)).

### 2.5 Page splits, and the ascending-insert fastpath

> New leaf pages are added to a B-Tree index when an existing leaf page cannot fit
> an incoming tuple. A page split operation makes room for items that originally
> belonged on the overflowing page by moving a portion of the items to a new page.
> Page splits must also insert a new downlink to the new page in the parent page,
> which may cause the parent to split in turn. Page splits "cascade upwards" in a
> recursive fashion.

— [§65.1.4](https://www.postgresql.org/docs/current/btree.html)

The manual's only nod to ordered inserts is inside the `fillfactor` description:

> For B-trees, leaf pages are filled to this percentage during initial index
> builds, **and also when extending the index at the right (adding new largest key
> values)**. If pages subsequently become completely full, they will be split,
> leading to fragmentation of the on-disk index structure.

— [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html)

The mechanism behind that clause is in the source, and it is the most important
single fact in this document:

> If the page is the rightmost page on its level, we instead try to arrange to
> leave the left split page fillfactor% full. In this way, when we are inserting
> successively increasing keys (consider sequences, timestamps, etc) we will end
> up with a tree whose pages are about fillfactor% full, **instead of the 50% full
> result that we'd get without this special case**.

— `src/backend/access/nbtree/nbtsplitloc.c`, `_bt_findsplitloc()`

Together with the cached-page optimisation:

> We optimize for a common case of insertion of increasing index key values by
> caching the last page to which this backend inserted the last value, if this
> page was the rightmost leaf page. For the next insert, we can then quickly check
> if the cached page is still the rightmost leaf page and also the correct place
> to hold the current value. **We can avoid the cost of walking down the tree in
> such common cases.**

— `src/backend/access/nbtree/README`, "Fastpath For Index Insertion"

This is the real, mechanical difference between a random key and a time-ordered
one in PostgreSQL:

- An **ordered** key (bigint sequence, UUIDv7, ULID, Snowflake) inserts at the
  right edge. Splits there leave the left page ~90% full, so the tree settles at
  about 90% density. One hot leaf page, cached, no tree descent.
- A **random** key (UUIDv4) inserts everywhere. Those are ordinary 50/50 splits,
  so the tree tends toward **~50% density**, and every insert touches a different
  leaf page.

Note what this does to the table in §2.3. At ~90% a `uuid` index holds ~262
entries per leaf; a *randomly*-ordered uuid index tends toward ~50%, i.e. ~145.
Against a bigint sequence's ~366, that is the genuine ~2.5× gap — and **most of
it is the split behaviour, not the 8 extra bytes.** This is why UUIDv7 recovers
most of the difference without narrowing the column by a single byte.

The README makes the same point about unique indexes directly:

> a primary key on an identity column will usually only have leaf page splits
> caused by the insertion of new logical rows within the rightmost leaf page. If
> there is a split of a non-rightmost leaf page, then the split must have been
> triggered by inserts associated with UPDATEs of existing logical rows.

— `src/backend/access/nbtree/README`, "Deduplication in unique indexes"

### 2.6 There is no clustered index in PostgreSQL

This is the fact that invalidates most cross-engine advice on this topic, and it
deserves to be stated before anyone imports an argument from SQL Server or
InnoDB.

> When a table is clustered, it is physically reordered based on the index
> information. **Clustering is a one-time operation: when the table is subsequently
> updated, the changes are not clustered. That is, no attempt is made to store new
> or updated rows according to their index order.**

— [CLUSTER](https://www.postgresql.org/docs/current/sql-cluster.html)

> Each table and index is stored in a separate file.

— [§66.1](https://www.postgresql.org/docs/current/storage-file-layout.html)

> All indexes in PostgreSQL are secondary indexes, meaning that each index is
> stored separately from the table's main data area (which is called the table's
> heap in PostgreSQL terminology).

— [§11.9](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)

In an engine with a clustered index, the primary key *is* the table's physical
order, so a random key scatters **row** insertions and fragments the table
itself. In PostgreSQL that mechanism does not exist. Heap inserts go to whatever
page the free space map offers, regardless of key value.

**The cost of a random key in PostgreSQL is confined to the B-tree index on that
key.** It does not fragment your table. Any advice that says otherwise was
written for a different engine. (The manual never states this conclusion in so
many words; it follows from the three quotations above.)

### 2.7 Write amplification

The mechanism is documented precisely, and it is about *pages touched*, not rows
written:

> When this parameter is on, the PostgreSQL server writes the entire content of
> each disk page to WAL during the first modification of that page after a
> checkpoint. [...] Storing the full page image guarantees that the page can be
> correctly restored, but at the price of increasing the amount of data that must
> be written to WAL. (Because WAL replay always starts from a checkpoint, it is
> sufficient to do this during the first change of each page after a checkpoint.
> Therefore, one way to reduce the cost of full-page writes is to increase the
> checkpoint interval parameters.) [...] The default is on.

— [`full_page_writes`, §20.5.1](https://www.postgresql.org/docs/current/runtime-config-wal.html)

**Be careful here.** The docs establish that each *distinct page* dirtied after a
checkpoint costs one ~8 kB full-page image. They say nothing about key ordering,
UUIDs, or insert locality. The chain — random keys scatter inserts across many
leaf pages → more distinct pages dirtied per checkpoint → more full-page images →
more WAL — is an **inference** from the quoted mechanism plus the quoted
rightmost-page behaviour in §2.5. It is a sound inference, but no PostgreSQL
document states it, and this note will not pretend otherwise.

If it does bite you, `wal_compression` ("The default value is `off`") compresses
full-page images specifically.

### 2.8 Fragmentation, and how to stop guessing

> B-tree indexes on tables where many inserts and/or updates are anticipated can
> benefit from lower fillfactor settings at CREATE INDEX time [...] Values in the
> range of 50 - 90 can usefully "smooth out" the rate of page splits during the
> early life of the B-tree index

> In other specific cases it might be useful to increase fillfactor to 100 [...]
> You should only consider this when you are completely sure that the table is
> static (i.e. that it will never be affected by either inserts or updates). A
> fillfactor setting of 100 otherwise risks harming performance: **even a few
> updates or inserts will cause a sudden flood of page splits.**

— [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html)

And on space that does not come back:

> B-tree index pages that have become completely empty are reclaimed for re-use.
> However, there is still a possibility of inefficient use of space: if all but a
> few index keys on a page have been deleted, the page remains allocated.
> Therefore, a usage pattern in which most, but not all, keys in each range are
> eventually deleted will see poor use of space. For such usage patterns, periodic
> reindexing is recommended.

— [§24.2](https://www.postgresql.org/docs/current/routine-reindex.html)

Rather than argue about any of this, measure it. `pgstatindex` reports
`avg_leaf_density` ("Average density of leaf pages") and `leaf_fragmentation`
("Leaf page fragmentation") — and those are the **complete** documented
definitions. The manual does not say how either is computed, gives no units for
`leaf_fragmentation`, and names no threshold for "bad". Anyone quoting a target
number for these is not quoting PostgreSQL.

`bt_multi_page_stats(idx, 1, -1)` gives per-leaf `live_items`, `avg_item_size`
and `free_size`, which answers "how wide is my index entry, really" empirically
and makes all of §2.3 unnecessary for a database you actually have. Access is
restricted: `pgstattuple` defaults to the `pg_stat_scan_tables` role, and "All of
these functions [pageinspect] may be used only by superusers."

### 2.9 Two features that change the calculus

**Bottom-up index deletion** (PostgreSQL 14+) targets version churn before it
splits a page:

> B-Tree indexes incrementally delete version churn index tuples by performing
> bottom-up index deletion passes. Each deletion pass is triggered in reaction to
> an anticipated "version churn page split". [...] **It's quite possible that the
> on-disk size of certain indexes will never increase by even one single
> page/block despite constant version churn from UPDATEs.**

— [§65.1.4.2](https://www.postgresql.org/docs/current/btree.html)

**Deduplication** (13+, "enabled by default") stores repeated keys once. A
primary key has no logical duplicates, so the space saving is nil — but the docs
name a second use that does apply:

> It is sometimes possible for unique indexes (as well as unique constraints) to
> use deduplication. This allows leaf pages to temporarily "absorb" extra version
> churn duplicates. Deduplication in unique indexes augments bottom-up index
> deletion, especially in cases where a long-running transaction holds a snapshot
> that blocks garbage collection.

— [§65.1.4.3](https://www.postgresql.org/docs/current/btree.html)

One restriction bears directly on §6:

> There is one further implementation-level restriction that applies regardless of
> the operator class or collation used: **INCLUDE indexes can never use
> deduplication.**

### 2.10 HOT, and why a key must never change

> To help reduce the overhead of updates, PostgreSQL has an optimization called
> heap-only tuples (HOT). This optimization is possible when:
>
> - **The update does not modify any columns referenced by the table's indexes**, not
>   including summarizing indexes. [...]
> - There is sufficient free space on the page containing the old row for the
>   updated row.

— [§66.7](https://www.postgresql.org/docs/current/storage-hot.html)

This is the mechanical argument against mutable keys, and it is stronger than the
usual aesthetic one. An indexed column that changes forfeits HOT for that row
*and* forces a new index entry in **every** index on the table.

### 2.11 TOAST is a non-issue

> The TOAST management code is triggered only when a row value to be stored in a
> table is wider than TOAST_TUPLE_THRESHOLD bytes (normally 2 kB).

— [§66.2](https://www.postgresql.org/docs/current/storage-toast.html)

`bigint` and `uuid` are fixed-length and not TOAST-able at all. A 26- or
36-character text identifier is TOAST-able in principle but sits two orders of
magnitude below the trigger. TOAST never enters this decision.

---

## 3. What PostgreSQL Can Generate

### 3.1 The feature ledger, with release-note evidence

| Capability | First shipped | Evidence |
| --- | --- | --- |
| `GENERATED { ALWAYS \| BY DEFAULT } AS IDENTITY` | 10 (2017-10-05) | [PG10 notes](https://www.postgresql.org/docs/release/10.0/) |
| `INCLUDE` covering indexes | 11 (2018-10-18) | [PG11 notes](https://www.postgresql.org/docs/release/11.0/) |
| `gen_random_uuid()` in core | 13 (2020-09-24) | [PG13 notes](https://www.postgresql.org/docs/release/13.0/) |
| `UNIQUE NULLS NOT DISTINCT` | 15 (2022-10-13) | [PG15 notes](https://www.postgresql.org/docs/release/15.0/) |
| `uuidv7()`, `uuidv4()` | 18 (2025-09-25) | [PG18 notes](https://www.postgresql.org/docs/release/18.0/) |

The PG13 note retired a long-standing piece of advice:

> Add function `gen_random_uuid()` to generate version-4 UUIDs (Peter Eisentraut)
> Previously UUID generation functions were only available in the external modules
> uuid-ossp and pgcrypto.

The PG18 note retires most of the case for an extension:

> `uuidv7()` function for generating timestamp-ordered UUIDs. (Andrey Borodin)
> This `UUID` value is temporally sortable.
>
> Function alias `uuidv4()` has been added to explicitly generate version 4 UUIDs.

### 3.2 The monotonicity guarantee is narrower than it is usually quoted

> In our implementation, the 12-bit sub-millisecond timestamp fraction is stored
> immediately after the timestamp, in the space referred to as "rand_a" in the
> RFC. This ensures additional monotonicity within a millisecond. The rand_a bits
> also function as a counter. We select a sub-millisecond timestamp so that it
> monotonically increases for generated UUIDs within the same backend, even when
> the system clock goes backward or when generating UUIDs at very high frequency.
> **Therefore, the monotonicity of generated UUIDs is ensured within the same
> backend.**

— Masahiko Sawada, commit `78c5e141e`, 2024-12-11,
[git.postgresql.org](https://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=78c5e141e9c139fc2ff36a220334e4aa25e1b0eb)

Read the last sentence carefully, because it is the one summaries drop. A
PostgreSQL backend is one connection's server process. The guarantee does **not**
extend across connections in a pool, across two application instances, or across
servers. Two rows inserted in the same millisecond on two different connections
have no defined order.

What `uuidv7()` gives you is millisecond-granular approximate ordering globally,
and strict ordering only along a single connection. For index locality that is
entirely sufficient — the B-tree only needs inserts to land near the right edge,
not in perfect sequence. For "sort by id to get creation order" it is not.

This construction is RFC 9562 §6.2 Method 3, "Replace Leftmost Random Bits with
Increased Clock Precision", though the commit message does not name it. (The
commit cites "RFC 9652"; that is a typo in the commit itself — the `uuid` type
page and the function docs both correctly say RFC 9562.)

### 3.3 The function catalogue

> `uuidv7([ shift interval ])` → `uuid` — Generates a version 7 (time-ordered)
> UUID. The timestamp is computed using UNIX timestamp with millisecond precision
> + sub-millisecond timestamp + random. The optional parameter *shift* will shift
> the computed timestamp by the given `interval`. [...] The shifted timestamp must
> fall within the range supported by UUID version 7's 48-bit millisecond timestamp
> field: from 1970-01-01 00:00:00 UTC to approximately year 10889.

> `uuid_extract_timestamp(uuid)` → `timestamp with time zone` — Extracts a
> `timestamp with time zone` from a UUID of version 1 or 7. For other versions,
> this function returns null. **Note that the extracted timestamp is not
> necessarily exactly equal to the time the UUID was generated; this depends on
> the implementation that generated the UUID.**

— [§9.14](https://www.postgresql.org/docs/current/functions-uuid.html)

That caveat matters: the timestamp is whatever the generator put there. For a
client-generated id, `uuid_extract_timestamp()` reports the *client's* clock.

### 3.4 What the `uuid` type is for, according to the project

> This identifier is a 128-bit quantity that is generated by an algorithm chosen
> to make it very unlikely that the same identifier will be generated by anyone
> else in the known universe using the same algorithm. **Therefore, for distributed
> systems, these identifiers provide a better uniqueness guarantee than sequence
> generators, which are only unique within a single database.**

> PostgreSQL provides native support for generating UUIDs using the UUIDv4 and
> UUIDv7 algorithms. Alternatively, UUID values can be generated outside of the
> database using any algorithm. **The data type `uuid` can be used to store any
> UUID, regardless of the origin and the UUID version.**

— [§8.12](https://www.postgresql.org/docs/current/datatype-uuid.html)

Note what the stated rationale is: **uniqueness without coordination**. It is not
unguessability, and it is not security. Note also the second paragraph — the type
is a 128-bit container with a canonical text format, not a validator. That is
what makes ULID, a Snowflake-in-a-UUID, and TypeID storable in it.

### 3.5 Extensions: what is left of the case for them

**`pgcrypto`** — the UUID function is now a shim:

> `gen_random_uuid()` returns uuid — Returns a version 4 (random) UUID.
> **(Obsolete, this function internally calls the core function of the same name.)**

— [F.26](https://www.postgresql.org/docs/current/pgcrypto.html)

Installing `pgcrypto` *for UUID generation* has been pointless since 13. It
remains the source of `gen_random_bytes(count integer)` — "cryptographically
strong random bytes", at most 1024 per call.

**`uuid-ossp`** — still the only in-tree source of v1/v3/v5:

> This module is only necessary for special requirements beyond what is available
> in core PostgreSQL. See Section 9.14 for built-in ways to generate UUIDs.

— [F.47](https://www.postgresql.org/docs/current/uuid-ossp.html)

Its `uuid_generate_v1()` entry carries a warning relevant to §5:

> Note that UUIDs of this kind reveal the identity of the computer that created
> the identifier and the time at which it did so, which might make it unsuitable
> for certain security-sensitive applications.

**`pg_uuidv7`** (third-party, MPL-2.0) — its own README now narrows its remit:

> As of Postgres 18, there is a built in `uuidv7()` function, however it does not
> include all of the functionality below.
>
> A tiny Postgres extension to create valid version 7 UUIDs in Postgres. Supports
> Postgres 13 through 18.

— [fboulnois/pg_uuidv7](https://github.com/fboulnois/pg_uuidv7)

It provides `uuid_generate_v7()`, `uuid_v7_to_timestamptz()` and
`uuid_timestamptz_to_v7()`. Post-18, the first two are duplicated by core. The
one function with no core equivalent is the range-boundary constructor:

> ```
> -- for date range queries set the second argument to true to zero the random bits
> SELECT uuid_timestamptz_to_v7('2023-01-02 04:26:40.637+00', true);
> → 018570bb-4a7d-7000-8000-000000000000
> ```

That is how you turn a time range into a `WHERE id >= … AND id < …` predicate
against the primary key index, with no secondary index on `created_at` at all.
It is a genuinely useful thing and PG18 core documents no equivalent.

Status, reported honestly: not archived, latest release v1.7.0 (2025-10-13),
roughly annual cadence.

**Availability usually decides this, not performance.** From first-party vendor
documentation:

- **AWS RDS/Aurora** lists `uuid-ossp` (1.1) and `pgcrypto`. `pg_uuidv7` does
  **not** appear in the supported-extensions list for any major version.
- **Neon** lists `pg_uuidv7` at 1.6 for PG14–18, noting "PostgreSQL 18 and later
  include the built-in `uuidv7()` function."
- **Supabase** does not enumerate its extensions, so nothing can be concluded
  either way.

A schema that depends on `uuid_timestamptz_to_v7()` is not portable to RDS.

### 3.6 Identity columns

> This clause creates the column as an *identity column*. It will have an implicit
> sequence attached to it and in newly-inserted rows the column will automatically
> have values from the sequence assigned to it. Such a column is implicitly
> `NOT NULL`.
>
> In an `INSERT` command, if `ALWAYS` is selected, a user-specified value is only
> accepted if the `INSERT` statement specifies `OVERRIDING SYSTEM VALUE`. If
> `BY DEFAULT` is selected, then the user-specified value takes precedence.
>
> In an `UPDATE` command, if `ALWAYS` is selected, any update of the column to any
> value other than `DEFAULT` will be rejected. If `BY DEFAULT` is selected, the
> column can be updated normally.

— [CREATE TABLE](https://www.postgresql.org/docs/current/sql-createtable.html)

`ALWAYS` is the right choice for a surrogate key precisely because of that
`UPDATE` clause: it makes the key immutable at the schema level, which is what
§2.10 says you want. The docs describe it as "protection against accidentally
inserting an explicit value".

And the trap, stated outright:

> An identity column does not guarantee uniqueness; a `PRIMARY KEY` or `UNIQUE`
> constraint is needed for that

— [§5.3](https://www.postgresql.org/docs/current/ddl-identity-columns.html)

Also worth knowing for partitioned schemas: "Partitions inherit identity columns
from the partitioned table; they cannot have their own."

### 3.7 Gaps are guaranteed, and are not a security feature

> To avoid blocking concurrent transactions that obtain numbers from the same
> sequence, the value obtained by `nextval` is not reclaimed for re-use if the
> calling transaction later aborts. This means that transaction aborts or database
> crashes can result in gaps in the sequence of assigned values. That can happen
> without a transaction abort, too. For example an `INSERT` with an `ON CONFLICT`
> clause will compute the to-be-inserted tuple, including doing any required
> `nextval` calls, before detecting any conflict [...] **Thus, PostgreSQL sequence
> objects cannot be used to obtain "gapless" sequences.**

— [§9.17](https://www.postgresql.org/docs/current/functions-sequence.html)

With `CACHE > 1` values additionally go out of order across sessions:

> although multiple sessions are guaranteed to allocate distinct sequence values,
> the values might be generated out of sequence when all the sessions are
> considered. For example, with a *cache* setting of 10, session A might reserve
> values 1..10 and return `nextval`=1, then session B might reserve values 11..20
> and return `nextval`=11 before session A has generated `nextval`=2.

— [CREATE SEQUENCE](https://www.postgresql.org/docs/current/sql-createsequence.html)

The default is `CACHE 1`, at which "it is safe to assume that `nextval` values are
generated sequentially". The honest summary: **a bigint identity column is
sequential by default; gaps exist but are incidental; nothing here is designed to
make the next value hard to guess.**

---

## 4. The Candidates

### 4.1 At a glance

| | Width in PG | Ordered? | Offline generation | Spec status |
| --- | --- | --- | --- | --- |
| `bigint` identity | 8 B | Yes, strictly | No | SQL standard |
| UUIDv4 | 16 B | No | Yes | RFC 9562 §5.4 |
| UUIDv7 | 16 B | To the millisecond | Yes | RFC 9562 §5.7 |
| ULID | 16 B as `uuid`, or 26 chars as text | To the millisecond | Yes | GitHub README, unversioned, last touched 2019 |
| Snowflake | 8 B | To the millisecond | Yes, with coordinated worker ids | Archived repo |
| TypeID | 16 B + prefix, or ~30 chars as text | To the millisecond | Yes | Spec v0.3.0 |
| Natural key | Varies | No | N/A | Whoever issues it |

### 4.2 `BIGINT GENERATED ALWAYS AS IDENTITY`

The narrowest key available, the best index behaviour available (§2.5: strictly
ascending, so the rightmost fastpath applies on every insert), and the SQL
standard spelling.

Its limits are the ones §3.7 and §1.1 describe. It requires a round trip to the
database — `nextval()` is a call into one database, so nothing offline or
client-side can mint one. It is sequential by default, which is a real
information leak if exposed: `/orders/1247` tells any customer roughly how many
orders you have taken, and `/orders/1248` is very likely somebody else's.

`bigserial` is the older spelling. The docs are more neutral about the choice
than is usually claimed — the current §8.1.4 note says only "This section
describes a PostgreSQL-specific way to create an autoincrementing column. Another
way is to use the SQL-standard identity column feature". The documented advantage
is the PG10 release note's "SQL standard compliant", plus the `ALWAYS` immutability
described in §3.6.

Range: −9223372036854775808 to +9223372036854775807. The docs note `bigserial`
"should be used if you anticipate the use of more than 2³¹ identifiers over the
lifetime of the table" — the reason to skip `integer` entirely for anything that
grows.

### 4.3 UUIDv4

> UUIDv4 is meant for generating UUIDs from truly random or pseudorandom numbers.
>
> [...] an implementation MAY choose to randomly generate the exact required number
> of bits for random_a, random_b, and random_c (**122 bits total**) and then
> concatenate the version and variant in the required position.

— [RFC 9562 §5.4](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.4)

122 random bits out of 128; the other six are the version nibble (`0b0100`) and
the two variant bits (`0b10`), both of which **MUST** be set (§4.1, §4.2).

Everything good about v4 follows from having no structure at all: no timestamp,
no node id, nothing to correlate, nothing to leak. RFC 9562 §8 singles it out for
exactly this reason — "If UUIDs are required for use with any security operation
within an application context in any shape or form, then UUIDv4 SHOULD be
utilized."

Everything bad about it follows from the same property. The RFC is blunt:

> UUID versions that are not time ordered, such as UUIDv4 [...] have poor
> database-index locality. This means that new values created in succession are
> not close to each other in the index; thus, they require inserts to be performed
> at random locations. **The resulting negative performance effects on the common
> structures used for this (B-tree and its variants) can be dramatic.**

— RFC 9562 §2.1

In PostgreSQL terms, §2.5 of this document is what "dramatic" means: ~50% leaf
density instead of ~90%, a cold leaf page per insert, and the write-amplification
inference of §2.7.

### 4.4 UUIDv7

> UUIDv7 features a time-ordered value field derived from the widely implemented
> and well-known Unix Epoch timestamp source, the number of milliseconds since
> midnight 1 Jan 1970 UTC, leap seconds excluded. [...] UUIDv7 values are created
> by allocating a Unix timestamp in milliseconds in the most significant 48 bits
> and filling the remaining **74 bits**, excluding the required version and variant
> bits, with random bits [...]
>
> Implementations **SHOULD** utilize UUIDv7 instead of UUIDv1 and UUIDv6 if possible.

— RFC 9562 §5.7

The field layout, verbatim:

> **unix_ts_ms:** 48-bit big-endian unsigned number of the Unix Epoch timestamp in
> milliseconds [...] Occupies bits 0 through 47 (octets 0-5).
> **ver:** The 4-bit version field [...] set to 0b0111 (7).
> **rand_a:** 12 bits of pseudorandom data [...] Occupies bits 52 through 63.
> **var:** The 2-bit variant field [...] set to 0b10.
> **rand_b:** The final 62 bits of pseudorandom data [...] Occupies bits 66 through 127.

The RFC's own justification for the format is the database-index argument, and
it is the one place any specification in this document offers a magnitude:

> Time-ordered monotonic UUIDs benefit from greater database-index locality
> because the new values are near each other in the index. As a result, objects
> are more easily clustered together for better performance. **The real-world
> differences in this approach of index locality versus random data inserts can be
> one order of magnitude or more.**

— RFC 9562 §6.11

Two cautions on that sentence. It is unattributed and unquantified — no
experiment, no workload, no engine is named. And "objects are more easily
clustered together" is written for engines that cluster; per §2.6, PostgreSQL
does not. Treat it as the RFC's motivation for the format, not as a PostgreSQL
benchmark.

The RFC also gives explicit storage advice that PostgreSQL users get for free:

> For many applications, such as databases, storing UUIDs as text is
> unnecessarily verbose, requiring 288 bits to represent 128-bit UUID values.
> Thus, where feasible, UUIDs **SHOULD** be stored within database applications as
> the underlying 128-bit binary value.

— RFC 9562 §6.13

PostgreSQL's `uuid` type does this. Storing UUIDs in a `text` column is the
single most common and most expensive mistake in this area: by §2.3 it more than
doubles the index entry (44 bytes vs 28) for no benefit whatsoever.

The same section states a preference worth weighing against §5.5:

> Applications using a monolithic database may find using database-generated UUIDs
> (as opposed to client-generated UUIDs) provides the best UUID monotonicity.

### 4.5 ULID

ULID predates UUIDv7 and solves the same problem. Its stated motivation:

> UUID can be suboptimal for many use-cases because:
> - It isn't the most character efficient way of encoding 128 bits of randomness
> - UUID v1/v2 is impractical in many environments, as it requires access to a
>   unique, stable MAC address
> - UUID v3/v5 requires a unique seed and produces randomly distributed IDs, which
>   can cause fragmentation in many data structures
> - UUID v4 provides no other information than randomness which can cause
>   fragmentation in many data structures

— [ULID spec](https://github.com/ulid/spec)

Layout: 48-bit millisecond timestamp + 80 bits of randomness, encoded as 26
characters of Crockford's Base32 (`0123456789ABCDEFGHJKMNPQRSTVWXYZ` — "This
alphabet excludes the letters I, L, O, and U to avoid confusion and abuse").

**The honest assessment is that UUIDv7 has superseded it**, for reasons that are
about governance rather than design:

- **The spec is unversioned and dormant.** No tags, no releases, no version
  number, no date inside the document. The last commit to `master` is
  `d0c7170`, dated **2019-05-23** — over seven years old at the time of writing.
  74 issues are open, and a `clarifications-jan-2020` branch was opened and never
  merged. The only way to cite a specific state is by commit SHA.
- **It defines itself by reference to one implementation**: "Below is the current
  specification of ULID as implemented in ulid/javascript", adding "*Note: the
  binary format has not been implemented in JavaScript as of yet.*"
- **It has no security considerations section at all**, and its randomness
  requirement is softer than the RFC's — "Cryptographically secure source of
  randomness, **if possible**".
- **Its "128-bit compatibility with UUID" claim is bare size-equivalence.** The
  spec says nothing about version or variant bits, so a ULID stored in a `uuid`
  column is *not* a conformant RFC 9562 UUID — it will have whatever bits its
  randomness produced where the version nibble belongs. It round-trips through
  PostgreSQL's `uuid` type fine (§3.4: "any UUID, regardless of the origin"), but
  `uuid_extract_version()` on it returns whatever those four bits happen to be.
- **There is a real intra-millisecond trap.** The headline bullet says "Monotonic
  sort order (correctly detects and handles the same millisecond)", but the
  Sorting section says: "**Within the same millisecond, sort order is not
  guaranteed**". Only the separate `monotonicFactory` provides ordering — and §5.3
  explains why that mode is worse than it looks.

RFC 9562 §2.1 lists ULID first among the 16 implementations analysed while
drafting the standard. It is fair to read UUIDv7 as ULID's design, given a
version field, a variant field, a standards body, and a security section.

### 4.6 Twitter Snowflake

The only 64-bit candidate here that is also time-ordered, and the constraint that
produced it is worth reading:

> Additionally, these numbers have to fit into 64 bits. **We've been through the
> painful process of growing the number of bits used to store tweet ids before.**
> It's unsurprisingly hard to do when you have over 100,000 different codebases
> involved.

> We also considered various UUIDs, but all the schemes we could find required 128
> bits.

— "Announcing Snowflake", Twitter Engineering, 1 June 2010. Live page returns
HTTP 403; read from the
[Wayback capture of 2024-04-22](https://web.archive.org/web/20240422012321/https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake).

The layout, from the repo at the `snowflake-2010` tag:

> * id is composed of:
>   * time - 41 bits (millisecond precision w/ a custom epoch gives us 69 years)
>   * configured machine id - 10 bits - gives us up to 1024 machines
>   * sequence number - 12 bits - rolls over every 4096 per machine (with
>     protection to avoid rollover in the same ms)

— [twitter-archive/snowflake `README.mkd`](https://raw.githubusercontent.com/twitter-archive/snowflake/snowflake-2010/README.mkd)

The 5+5 datacenter/worker split and the epoch are **not** in the README — they are
in `IdWorker.scala`: `val twepoch = 1288834974657L`, `workerIdBits = 5`,
`datacenterIdBits = 5`, `sequenceBits = 12`. The sign bit is never stated
anywhere; it is implied by 41 + 10 + 12 = 63 of a signed `Long`.

Its ordering guarantee is deliberately weak, and named:

> We can guarantee, however, that the id numbers will be k-sorted [...] within a
> reasonable bound (we're promising 1s, but shooting for 10's of ms).

Three things make this a poor default in 2026:

**It is retired.** The repository is archived (`"archived": true`, last push
2020-07-22), and the master README says: "We have retired the initial release of
Snowflake [...] We won't be accepting pull requests or responding to issues for
the retired release." What you would adopt is the *design*, reimplemented.

**Worker-id assignment is a coordination problem.** "worker numbers are chosen at
startup via zookeeper". Ten bits means exactly 1024 concurrent generators, and
assigning them uniquely — across autoscaling, container restarts, and blue/green
deploys — is the actual engineering cost. It is not an uncoordinated scheme; it
is a scheme where the coordination happens once at startup instead of once per
id.

**64-bit ids break JavaScript**, which Twitter documented first-party:

> Numbers as large as 64-bits can cause issues with programming languages that
> represent integers with fewer than 64-bits. An example of this is JavaScript,
> where integers are limited to 53-bits in size. [...] If you run the command
> `(10765432100123456789).toString()` in a browser JavaScript console, the result
> will be `"10765432100123458000"` — the 64-bit integer loses accuracy

— Twitter developer docs, read from the
[Wayback capture of 2024-04-25](https://web.archive.org/web/20240425032320/https://developer.twitter.com/en/docs/twitter-ids)

Their fix was to serialise ids as strings (`id_str`), and "In newer versions of
the API, all large integer values are represented as strings by default." Discord
reached the same conclusion independently: "Because Snowflake IDs are up to 64
bits in size (e.g. a uint64), **they are always returned as strings in the HTTP
API** to prevent integer overflows in some languages."

This applies verbatim to a `bigint` primary key that you expose in JSON. It is
the one practical hazard `bigint` shares with Snowflake, and it is entirely
avoidable by serialising as a string.

Discord's live variant differs slightly — 42 timestamp bits (not 41), 5 worker +
5 process + 12 increment, epoch `1420070400000`
([Discord API reference](https://docs.discord.com/developers/reference)) — which
is a useful reminder that "Snowflake" names a family, not a format.

### 4.7 TypeID

> TypeIDs are a type-safe extension of UUIDv7, they encode UUIDs in base32 and add
> a type prefix.

> A typeid consists of three parts:
> 1. A **type prefix**: a string denoting the type of the ID. The prefix should be
>    at most 63 characters in all lowercase snake_case ASCII `[a-z_]`.
> 2. A **separator**: an underscore `_` character. The separator is omitted if the
>    prefix is empty.
> 3. A **UUID suffix**: a 128-bit UUIDv7 encoded as a 26-character string in base32.

— [TypeID Specification v0.3.0](https://github.com/jetify-com/typeid/blob/main/spec/README.md)

Giving `user_2x4y6z8a0b1c2d3e4f5g6h7j8k`. Prefix rules:
`^([a-z]([a-z_]{0,61}[a-z])?)?$` — lowercase alphabetic and underscore only, no
digits, no leading or trailing underscore. Total length 26 to 90 characters.

The encoding is careful in a way worth noting: 128 bits are left-padded to 130
and split into 26 groups of five, so "Implementations MUST reject any suffix where
the first character is greater than `7`, as this would represent a value that
exceeds 128 bits."

Critically, the underlying value is required to be a real UUIDv7:

> When generating a new TypeID, the generated UUID suffix MUST decode to a valid
> UUIDv7. This means:
> - Bits 48-51 of the UUID MUST be `0111` (indicating version 7)
> - Bits 64-65 of the UUID MUST be `10` (indicating the UUID variant)

This is the property ULID lacks (§4.5). A TypeID is a UUIDv7 plus a presentation
layer, so the storage question has a clean answer: **store the `uuid`, render the
prefix.**

The official SQL implementation offers two encodings, and neither is that:

> ### 1. Text-based encoding
> This encoding is more inefficient than the alternative, but it's very
> straight-forward to understand, it's easy to debug [...]
>
> ```sql
> CREATE TABLE users (
>     "id" text not null default typeid_generate_text('user') CHECK (typeid_check_text(id, 'user')),
>     ...
> );
> ```

> ### 2. UUID-based encoding using compound types
> In this approach, we internally encode typeids as a `(prefix, uuid)` tuple. [...]
> The advantage of this approach is that it is a more efficient encoding because
> we store the uuid portion of the typeid using the native `uuid` type. The
> disadvanage is that it is harder to work with and debug.
>
> ```sql
> create type "typeid" as ("type" varchar(63), "uuid" uuid);
> ```

— [jetify-com/typeid-sql](https://github.com/jetify-com/typeid-sql)

Both are worse than necessary as a key. The text encoding costs ~30 characters
per index entry (§2.3: roughly 2× a native `uuid`). The composite stores a
`varchar(63)` **prefix on every single row**, even though the prefix is a
property of the table, not the row — it is constant for all rows in `users`.

The pragmatic reading: adopt TypeID as an **API format**, not a storage format.
Keep `uuid` in the column and add the prefix at the serialisation boundary, which
is where the type-safety benefit is actually realised anyway. Note also that the
SQL implementation tracks spec v0.2 while Go and TypeScript are at v0.3, and the
root README still describes UUIDv7 as "the upcoming UUID standard", linking an
expired IETF draft rather than the published RFC.

The acknowledged inspiration is Stripe, and Stripe's own position on their ids is
instructive:

> Changing the length or format of opaque strings, such as object IDs [...] This
> includes adding or removing fixed prefixes (such as `ch_` on charge IDs). Make
> sure that your integration can handle Stripe-generated object IDs, which can
> contain up to 255 characters.

— [Stripe API upgrades](https://docs.stripe.com/upgrades), "Backward-compatible changes"

Stripe classifies changing ID length and adding or removing the prefix as
**backward-compatible** changes clients must tolerate. TypeID inverts this: its
format is fixed and parseable by design. Both are defensible; they are opposite
bets on whether an identifier is opaque.

### 4.8 Natural and semantic keys

A natural key uses data that already means something — an email address, an ISBN,
a country code, an order number from the warehouse system.

The appeal is genuine: one less column, no join needed to read the meaningful
value, and a uniqueness constraint that expresses a real business rule.

The problem is that the issuing authority is not you, and it will change the
format. The cleanest cited example is ISBN:

> ISBNs were 10 digits in length up to the end of December 2006, but since 1
> January 2007 they now always consist of 13 digits.

— [International ISBN Agency](https://www.isbn-international.org/content/what-isbn/10)

A schema that keyed on ISBN-10 needed, on a date chosen by someone else, to widen
the key column in every table that referenced it. PostgreSQL prices that
migration explicitly:

> Changing the type of an existing column will normally cause the entire table and
> its indexes to be rewritten. [...] Table and/or index rebuilds may take a
> significant amount of time for a large table, and will temporarily require as
> much as double the disk space.

> `ALTER TABLE` changes the definition of an existing table. **An `ACCESS EXCLUSIVE`
> lock is acquired** unless explicitly noted.

— [ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)

Even without a type change, a natural key that merely *updates* is expensive.
`ON UPDATE CASCADE` exists precisely for this:

> Analogous to `ON DELETE` there is also `ON UPDATE` which is invoked when a
> referenced column is changed (updated). [...] In this case, `CASCADE` means that
> the updated values of the referenced column(s) should be copied into the
> referencing row(s).

— [§5.5.5](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

"Copied into the referencing row(s)" means rewriting every child row, in every
child table, inside the transaction that changed one email address — and by
§2.10, each of those rewrites forfeits HOT and touches every index on the child
table. One user correcting a typo in their email becomes an unbounded write
amplification.

RFC 9562 makes the same argument from the other direction, about name-based UUIDs:

> Designers of database schema are cautioned against using name-based UUIDs [...]
> as primary keys in tables. The general advice is to avoid name-based UUID natural
> keys and, instead, to utilize time-based UUID surrogate keys

— RFC 9562 §6.13

**The synthesis is not "never use natural keys".** It is that a natural key's
uniqueness is a genuine business rule and belongs in the schema — as a `UNIQUE`
constraint, which by §1.3 is "functionally almost the same thing" as a primary
key. What it should not be is the target of your foreign keys. Declare
`UNIQUE (email)`; key on something you control.

One PostgreSQL-specific subtlety if you do this: by default "two null values are
not considered equal", so a nullable natural key permits duplicate rows that are
null in the constrained column. `UNIQUE NULLS NOT DISTINCT` (PG15+) changes that,
and the docs warn: "The default null treatment in unique constraints is
implementation-defined according to the SQL standard, and other implementations
have a different behavior."

---

## 5. Security, Collisions, and Offline Generation

### 5.1 What the RFC actually says about guessability

The entire security posture of RFC 9562 is four paragraphs, and they are more
restrained than the advice usually given in their name:

> Implementations **SHOULD NOT** assume that UUIDs are hard to guess. For example,
> they **MUST NOT** be used as security capabilities (identifiers whose mere
> possession grants access). Discovery of predictability in a random number source
> will result in a vulnerability.
>
> Implementations **MUST NOT** assume that it is easy to determine if a UUID has been
> slightly modified in order to redirect a reference to another object. Humans do
> not have the ability to easily check the integrity of a UUID by simply glancing
> at it.
>
> MAC addresses pose inherent security risks around privacy and **SHOULD NOT** be used
> within a UUID. Instead CSPRNG data **SHOULD** be selected from a source with
> sufficient entropy [...]
>
> Timestamps embedded in the UUID do pose a **very small attack surface**. The
> timestamp in conjunction with an embedded counter does signal the order of
> creation for a given UUID and its corresponding data but does not define
> anything about the data itself or the application as a whole. **If UUIDs are
> required for use with any security operation within an application context in any
> shape or form, then UUIDv4 SHOULD be utilized.**

— [RFC 9562 §8](https://www.rfc-editor.org/rfc/rfc9562.html#section-8)

Three consequences.

**A UUID is not an authorisation mechanism, and the RFC says so normatively.**
"MUST NOT be used as security capabilities (identifiers whose mere possession
grants access)" is unambiguous. If an object is reachable by anyone holding its
id, that is a missing ownership check, and swapping `bigint` for `uuid` does not
fix it — it hides it behind a larger search space. This is the most commonly
misapplied idea in the whole subject: teams migrate to UUIDs *instead of* adding
the check. The RFC forbids exactly that reasoning.

The language also hardened between revisions. RFC 4122 §6 said "Do not assume
that UUIDs are hard to guess"; RFC 9562 restates it as **SHOULD NOT** / **MUST
NOT**.

**Timestamp exposure is real but the RFC rates it small.** A UUIDv7 carries a
plaintext 48-bit millisecond timestamp in its leading bits, so anyone holding one
learns when the row was created, and anyone holding two learns their order. The
RFC's assessment is the paragraph above; it never uses the words "leak" or
"enumeration".

Whether that matters is a question about your domain. A `user_id` revealing
signup time is usually harmless; an `invoice_id` that lets a competitor measure
your order volume by creating two accounts an hour apart is not — and note that
this attack works against **any** time-ordered scheme, including `bigint`, ULID
and Snowflake. It is the price of sortability, not a defect peculiar to v7.

**The RFC names its own escape hatch**: UUIDv4, for anything security-adjacent.

### 5.2 Unguessability is a property of your RNG

> Implementations **SHOULD** utilize a cryptographically secure pseudorandom number
> generator (CSPRNG) to provide values that are both difficult to predict
> ("unguessable") and have a low likelihood of collision ("unique"). [...] **Take
> care to ensure the CSPRNG state is properly reseeded upon state changes, such as
> process forks**, to ensure proper CSPRNG operation.

— RFC 9562 §6.9

The fork caveat is the practical one. A pre-forking application server that seeds
its RNG before forking hands every worker the same stream, and the resulting
"random" ids are neither unguessable nor unique. The RFC calls this out by name
because it is a recurring bug, not a theoretical one.

### 5.3 The trap in ULID's monotonic mode

This is the sharpest cross-specification finding in this document, and both specs
are individually reasonable.

RFC 9562 §6.2 offers "Monotonic Random (Method 2)", in which the random field
doubles as a counter, with this warning:

> The increment value for every UUID generation is a random integer of any desired
> length larger than zero. It ensures that the UUIDs retain the required level of
> unguessability provided by the underlying entropy. The increment value **MAY** be 1
> when the number of UUIDs generated in a particular period of time is important
> and guessability is not an issue. **However, incrementing the counter by 1 SHOULD
> NOT be used by implementations that favor unguessability, as the resulting values
> are easily guessable.**

— RFC 9562 §6.2

And the ULID specification, defining its monotonic mode:

> When generating a ULID within the same millisecond, we can provide some
> guarantees regarding sort order. Namely, if the same millisecond is detected,
> **the `random` component is incremented by 1 bit in the least significant bit
> position** (with carrying).

— ULID spec, "Monotonicity", with the worked example
`01BX5ZZKBKACTAV9WEVGEMMVRZ` → `01BX5ZZKBKACTAV9WEVGEMMVS0`

**ULID's monotonic factory is Method 2 with an increment of exactly 1** — the
construction RFC 9562 says SHOULD NOT be used where unguessability matters. The
consequence is concrete: given one ULID from a monotonic generator, the next one
issued in that millisecond is not merely guessable, it is *determined*. If you
chose ULIDs as public identifiers partly because they are hard to guess,
monotonic mode removes that property for any id sharing a millisecond with one an
attacker holds.

ULID has no security considerations section, so it issues no warning of its own.

PostgreSQL's `uuidv7()` does not have this problem: per §3.2 it uses Method 3
(sub-millisecond clock precision in `rand_a`), leaving all 62 bits of `rand_b`
random on every call.

### 5.4 Collision probability: what the specs refuse to say

**Neither specification states a numeric collision probability.** RFC 9562 never
mentions the birthday problem — a full-text search of the canonical text returns
zero hits for "birthday", and "probability" appears four times, never attached to
a figure. What the RFC offers instead is a framing:

> **Low Impact:** A UUID collision generated a duplicate log entry, which results in
> incorrect statistics derived from the data. [...]
>
> **High Impact:** A duplicate key causes an airplane to receive the wrong course,
> which puts people's lives at risk. In this scenario, there is no margin for
> error. Collisions must be avoided: failure is unacceptable.

— RFC 9562 §6.7

and a caution against over-claiming:

> Although **true global uniqueness is impossible to guarantee without a shared
> knowledge scheme**, a shared knowledge scheme is not required by a UUID to provide
> uniqueness for practical implementation purposes.

— RFC 9562 §6.8

The familiar "a billion a second for a century" figures are not in the RFC, and
this document does not attribute them to it. What can be stated honestly is the
entropy each format carries, because the bit counts are quoted facts:

| Format | Bits not determined by time or format | Source |
| --- | --- | --- |
| UUIDv4 | 122, once | RFC 9562 §5.4: "122 bits total" |
| UUIDv7 | 74, **per millisecond** | RFC 9562 §5.7: "the remaining 74 bits" |
| ULID | 80, **per millisecond** | ULID spec: "Randomness — 80 bits" |

The per-millisecond framing is the structural reason a v7 can be safe with fewer
random bits than a v4: the timestamp partitions the space, so only ids born in
the same millisecond can possibly collide. ULID advertises this as "1.21e+24
unique ULIDs per millisecond" (2⁸⁰).

Whatever collision arithmetic you do from these numbers, do it explicitly and
label it as yours. The specifications decline to do it for you, and that is a
deliberate choice on their part, not an oversight.

The practical mitigation is the same regardless: **a unique index is the only
thing that actually guarantees uniqueness.** Per §3.6, even an identity column
does not — "a `PRIMARY KEY` or `UNIQUE` constraint is needed for that."

### 5.5 Generating away from the database

> One of the main reasons for using UUIDs is that no centralized authority is
> required to administer them [...] As a result, generation on demand can be
> completely automated

— RFC 9562 §2

This is the capability a `bigint` identity column cannot offer at any price, and
it is the honest reason to reach for a 128-bit id. A client, a mobile app
offline, or three services writing to different shards can each mint an
identifier with no round trip and no coordination. `nextval()` cannot: it is a
call into one database.

Two concrete consequences worth designing around:

- **Idempotent retries.** If the client generates the id, a retried `INSERT`
  hits a unique-violation instead of creating a duplicate row.
- **Batch construction.** An object graph — order, line items, shipment — can be
  built entirely in memory with all foreign keys already wired, then inserted in
  one round trip, because the parent id existed before the parent row did.

The RFC's guidance for multi-node generation is narrower than folklore suggests:

> implementations should utilize the pseudorandom Node ID option if additional
> collision resistance for distributed UUID generation is a requirement. [...]
> Implementations that choose to leverage an embedded node id **SHOULD** utilize
> UUIDv8. The node id **SHOULD NOT** be an IEEE 802 MAC address per Section 8.
>
> **Centralized Registry:** [...] Shared knowledge schemes with central/global
> registries are outside the scope of this specification and are **NOT RECOMMENDED**.
>
> Distributed applications generating UUIDs at a variety of hosts **MUST** be willing
> to rely on the random number source at all hosts.

— RFC 9562 §6.4

That last sentence is the operative constraint on client-side generation, and it
is a trust statement rather than a technical one. If browsers or mobile devices
mint your ids, you have accepted every one of those devices' RNGs into your
uniqueness argument — and since the value arrives over the wire, you must treat
it as hostile input and constrain it exactly as you would any other
client-supplied field.

Against which the RFC sets a preference cutting the other way for a single
database (§4.4): "Applications using a monolithic database may find using
database-generated UUIDs [...] provides the best UUID monotonicity." And per
§3.2, even server-side generation in PostgreSQL orders strictly only within one
backend.

---

## 6. The Dual-Identifier Architecture

### 6.1 The pattern

Give the row two identifiers, each doing one of the jobs from §1.1:

```sql
CREATE TABLE orders (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id   uuid   NOT NULL DEFAULT uuidv7(),
    -- ... domain columns ...
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT orders_public_id_key UNIQUE (public_id)
);

CREATE TABLE order_lines (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id  bigint NOT NULL REFERENCES orders (id),
    -- ...
);

CREATE INDEX ON order_lines (order_id);   -- see §6.3
```

`id` is never serialised. `public_id` never appears in a foreign key. Every
internal join runs on 8-byte integers with the best possible index behaviour
(§2.5), and every external reference is an opaque 128-bit value that reveals only
a creation timestamp.

`uuidv7()` requires PostgreSQL 18. On 13–17 the equivalent is `pg_uuidv7`'s
`uuid_generate_v7()` where your platform allows it (§3.5), `gen_random_uuid()` if
you would rather have v4 than a dependency, or application-side generation.

### 6.2 What it costs, stated plainly

This pattern is not free, and most write-ups skip the bill:

- **An extra 16-byte column** on every row of the parent table.
- **An extra unique B-tree index**, which by §2.3 runs about 28 bytes per entry
  and, being on a v7 value, benefits from the rightmost fastpath.
- **An extra lookup on every external request.** A URL carries `public_id`; the
  query needs `id`. That is one index probe before the real work starts.
- **Two ways to name the same row**, which is a permanent invitation to leak the
  wrong one. This is a discipline cost, and it is the one that actually bites.

The third cost is the one §6.4 addresses and the only one that is really
negotiable.

### 6.3 Foreign keys

Two documented facts govern the design.

**The referenced side does not have to be the primary key:**

> A foreign key must reference columns that either are a primary key or form a
> unique constraint, or are columns from a non-partial unique index.

— [§5.5.5](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

So `REFERENCES orders (public_id)` is legal — the `UNIQUE` constraint suffices.
It is also the mistake this whole pattern exists to avoid: it puts 16 bytes in
every child row and 16-byte keys in every child index, discarding the benefit and
keeping all of the cost. **Reference `id`.**

**The referencing side is not indexed for you**, and the docs are explicit about
why you usually want to:

> Since a `DELETE` of a row from the referenced table or an `UPDATE` of a referenced
> column will require a scan of the referencing table for rows matching the old
> value, **it is often a good idea to index the referencing columns too.** Because
> this is not always needed, and there are many choices available on how to index,
> the declaration of a foreign key constraint does not automatically create an
> index on the referencing columns.

— same section

This is where the dual-identifier pattern quietly pays off a second time. You
will create that index on `order_lines (order_id)` regardless; making it 8 bytes
wide rather than 16 is a ~28% reduction in its entry size by §2.3, replicated
across every child table in the schema. In a schema with many
many-to-one relationships, this compounds far more than the single extra index on
the parent costs.

Note also that an `ALWAYS` identity primary key can never be updated (§3.6), so
the `ON UPDATE` scan the docs describe simply cannot occur for it — the natural-key
failure mode of §4.8 is structurally excluded.

### 6.4 Making the extra lookup cheap

The `public_id` → `id` resolution can be served entirely from the index, without
touching the heap:

```sql
CREATE UNIQUE INDEX orders_public_id_idx
    ON orders (public_id) INCLUDE (id);
```

> A non-key column cannot be used in an index scan search qualification, and it is
> disregarded for purposes of any uniqueness or exclusion constraint enforced by
> the index. However, **an index-only scan can return the contents of non-key columns
> without having to visit the index's table**, since they are available directly from
> the index entry.

— [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html)

There are three caveats, all documented, and all worth knowing before reaching
for this.

**It depends on the visibility map, not just the index.** An index-only scan
checks the visibility map for each candidate's heap page; if the all-visible bit
is not set it must visit the heap anyway. The docs say index-only scans are most
beneficial "when a large fraction of heap pages have their all-visible bits set",
i.e. on slowly-changing data. A hot, frequently-updated `orders` table will not
get the benefit reliably.

**It disables deduplication on that index.** Per §2.9: "INCLUDE indexes can never
use deduplication." For a unique index there are no logical duplicates to
deduplicate, so the direct cost is nil — but you also lose the documented
secondary use, absorbing version churn to postpone page splits. On an
update-heavy table that is a real trade, not a free win.

**It only helps if the query touches nothing else.** `SELECT id FROM orders WHERE
public_id = $1` qualifies. `SELECT * FROM orders WHERE public_id = $1` does not,
and that is what most application code actually issues — in which case the plain
`UNIQUE (public_id)` index is all you need and the `INCLUDE` buys nothing.

Measure before adding it. For most applications the honest answer is that a
unique index probe on 16 bytes is already fast enough that this optimisation is
premature.

### 6.5 Does a wider join key actually cost anything?

**The PostgreSQL documentation makes no claim that join-key width affects join
performance.** `using-explain.html` reports row `width=` estimates but never
connects key width to join cost or plan choice. Any "16-byte keys join more
slowly than 8-byte keys" assertion is undocumented, and this note will not make
it.

What *is* documented is the chain a reader can reason from:

> Here, the planner has chosen to use a hash join, in which rows of one table are
> entered into an in-memory hash table, after which the other table is scanned and
> the hash table is probed for matches to each row.

— [§14.1](https://www.postgresql.org/docs/current/using-explain.html)

> Sets the base maximum amount of memory to be used by a query operation (such as
> a sort or hash table) **before writing to temporary disk files.** [...] The memory
> limit for a hash table is computed by multiplying `work_mem` by
> `hash_mem_multiplier`.

— [`work_mem`, §20.4.1](https://www.postgresql.org/docs/current/runtime-config-resource.html)

Hash joins build an in-memory table bounded by `work_mem × hash_mem_multiplier`;
exceeding it produces multiple batches, which involve disk. Wider keys make each
entry larger, so the bound is reached with fewer rows. That is a coherent
argument and probably true, but it is **inference, not documentation** — and the
effect is a step function at the spill threshold, not a smooth tax on every join.

The defensible version of the claim is the one from §2.3 and §2.4: narrower keys
make **indexes smaller**, which means more of the working set fits in
`shared_buffers`. That is a cache-residency argument, it is grounded in quoted
constants, and it does not require any claim about join algorithms.

### 6.6 The API boundary

The decoupling is the point, and it is worth being concrete about what it buys.

- **Renumbering becomes possible.** Merging two databases, resharding, or
  backfilling from a legacy system can renumber `id` freely as long as
  `public_id` travels with the row. External references — links customers
  bookmarked, ids in partners' systems, values in your own webhook history —
  stay valid.
- **JSON stays safe.** By §4.6, a 64-bit integer does not survive JavaScript's
  53-bit number type. A `uuid` serialises as a string and cannot be corrupted
  this way. If you ever *do* expose `id`, serialise it as a string.
- **Enumeration stops being trivial.** With the §5.1 caveat firmly attached: this
  is defence in depth behind an authorisation check, never a substitute for one.

If you want TypeID's ergonomics (§4.7), this is exactly where to add them:
`public_id` stays `uuid` in the database, and the serialisation layer renders it
as `order_2x4y6z8a0b1c2d3e4f5g6h7j8k`. The prefix is a property of the table, so
storing it per row buys nothing.

### 6.7 When not to do this

The pattern earns its cost when identifiers are exposed to parties you do not
control, or when the internal id might have to change. Below that threshold it is
two columns and a lookup where one column would do.

A reasonable default ladder:

1. **Single-node application, ids not publicly meaningful** → `bigint GENERATED
   ALWAYS AS IDENTITY`. Narrowest, fastest, simplest. Serialise as a string.
2. **Ids in URLs or third-party hands** → the dual-identifier pattern, `bigint`
   internal + `uuidv7()` external.
3. **Client-side or offline generation required** (§5.5) → a single `uuid`
   primary key holding a v7. You give up 8 bytes per row and every child index
   entry; you gain generation without a round trip. This is the honest trade, and
   for many distributed systems it is the right one.
4. **Ids are a security-relevant surface** → v4 for the external id, on the RFC's
   own advice (§5.1), accepting the index behaviour of §4.3 for that one index.

What survives every rung: **key on something you control, never update it, and
put a unique constraint on anything that must be unique** — including the
identifier your framework already thinks is unique.

---

## 7. Sources

### Specifications

- **RFC 9562**, "Universally Unique IDentifiers (UUIDs)". K. Davis, B. Peabody,
  P. Leach. IETF, Standards Track, May 2024. Obsoletes RFC 4122.
  <https://www.rfc-editor.org/rfc/rfc9562.html>
- **RFC 4122**, "A Universally Unique IDentifier (UUID) URN Namespace". Leach,
  Mealling, Salz. IETF, July 2005. Obsoleted by 9562; used here only for
  historical contrast. <https://www.rfc-editor.org/rfc/rfc4122>
- **ULID specification**. `ulid/spec` on GitHub, GPL-3.0. No version, no tags, no
  releases; `master` last committed `d0c7170`, 2019-05-23.
  <https://github.com/ulid/spec>
- **TypeID Specification v0.3.0**. jetify-com.
  <https://github.com/jetify-com/typeid/blob/main/spec/README.md>

### PostgreSQL 18 documentation

Data types and functions — [§8.1 Numeric
Types](https://www.postgresql.org/docs/current/datatype-numeric.html) ·
[§8.3 Character
Types](https://www.postgresql.org/docs/current/datatype-character.html) ·
[§8.12 UUID Type](https://www.postgresql.org/docs/current/datatype-uuid.html) ·
[§9.14 UUID
Functions](https://www.postgresql.org/docs/current/functions-uuid.html) ·
[§9.17 Sequence
Functions](https://www.postgresql.org/docs/current/functions-sequence.html)

Schema and DDL — [§5.3 Identity
Columns](https://www.postgresql.org/docs/current/ddl-identity-columns.html) ·
[§5.5
Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) ·
[CREATE TABLE](https://www.postgresql.org/docs/current/sql-createtable.html) ·
[CREATE
SEQUENCE](https://www.postgresql.org/docs/current/sql-createsequence.html) ·
[CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) ·
[ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html) ·
[CLUSTER](https://www.postgresql.org/docs/current/sql-cluster.html)

Indexes — [§11.3
Multicolumn](https://www.postgresql.org/docs/current/indexes-multicolumn.html) ·
[§11.9 Index-Only
Scans](https://www.postgresql.org/docs/current/indexes-index-only-scans.html) ·
[§65.1 B-Tree Indexes](https://www.postgresql.org/docs/current/btree.html)
(incl. §65.1.4.2 bottom-up deletion, §65.1.4.3 deduplication)

Storage — [§66.1 File
Layout](https://www.postgresql.org/docs/current/storage-file-layout.html) ·
[§66.2 TOAST](https://www.postgresql.org/docs/current/storage-toast.html) ·
[§66.3 FSM](https://www.postgresql.org/docs/current/storage-fsm.html) ·
[§66.6 Page
Layout](https://www.postgresql.org/docs/current/storage-page-layout.html) ·
[§66.7 HOT](https://www.postgresql.org/docs/current/storage-hot.html)

Maintenance and configuration — [§20.4.1
Memory](https://www.postgresql.org/docs/current/runtime-config-resource.html) ·
[§20.5.1 WAL
Settings](https://www.postgresql.org/docs/current/runtime-config-wal.html) ·
[§20.7.2 Planner Cost
Constants](https://www.postgresql.org/docs/current/runtime-config-query.html) ·
[§24.1
Vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html) ·
[§24.2
Reindexing](https://www.postgresql.org/docs/current/routine-reindex.html) ·
[§28.5 WAL
Configuration](https://www.postgresql.org/docs/current/wal-configuration.html) ·
[§28.6 WAL
Internals](https://www.postgresql.org/docs/current/wal-internals.html)

Diagnostics and modules — [§14.1 Using
EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html) ·
[F.23 pageinspect](https://www.postgresql.org/docs/current/pageinspect.html) ·
[F.26 pgcrypto](https://www.postgresql.org/docs/current/pgcrypto.html) ·
[F.33 pgstattuple](https://www.postgresql.org/docs/current/pgstattuple.html) ·
[F.47 uuid-ossp](https://www.postgresql.org/docs/current/uuid-ossp.html)

Release notes — [10](https://www.postgresql.org/docs/release/10.0/) ·
[11](https://www.postgresql.org/docs/release/11.0/) ·
[13](https://www.postgresql.org/docs/release/13.0/) ·
[15](https://www.postgresql.org/docs/release/15.0/) ·
[18](https://www.postgresql.org/docs/release/18.0/) ·
[versioning policy](https://www.postgresql.org/support/versioning/)

### PostgreSQL source (`REL_18_STABLE`)

Used only where the manual is silent, and labelled as such throughout.

- `src/include/utils/uuid.h` — `UUID_LEN 16`
- `src/include/access/itup.h` — `IndexTupleData`
- `src/include/access/nbtree.h` — `BTMaxItemSize`, `BTPageOpaqueData`
- `src/backend/access/nbtree/README` — "Fastpath For Index Insertion";
  "Deduplication in unique indexes"
- `src/backend/access/nbtree/nbtsplitloc.c` — `_bt_findsplitloc()`, rightmost-page
  fillfactor behaviour
- Commit `78c5e141e`, "Add UUID version 7 generation function", Masahiko Sawada,
  2024-12-11 —
  [gitweb](https://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=78c5e141e9c139fc2ff36a220334e4aa25e1b0eb)

### Vendor and implementation sources

- **Twitter**, "Announcing Snowflake", 1 June 2010. Live page returns HTTP 403;
  read from the [Wayback capture of
  2024-04-22](https://web.archive.org/web/20240422012321/https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake).
- **twitter-archive/snowflake**, `README.mkd` and `IdWorker.scala` at the
  `snowflake-2010` tag; master `README.md` for the retirement notice. Repository
  archived; last push 2020-07-22. <https://github.com/twitter-archive/snowflake>
- **Twitter developer documentation**, "Twitter IDs". Live URL redirects and the
  content is gone; read from the [Wayback capture of
  2024-04-25](https://web.archive.org/web/20240425032320/https://developer.twitter.com/en/docs/twitter-ids).
- **Discord API Reference**, snowflake format.
  <https://docs.discord.com/developers/reference>
- **jetify-com/typeid-sql** — the official PostgreSQL implementation, tracking
  spec v0.2. <https://github.com/jetify-com/typeid-sql>
- **Stripe**, "Upgrades" — backward-compatible changes to object IDs.
  <https://docs.stripe.com/upgrades>
- **fboulnois/pg_uuidv7**, MPL-2.0, v1.7.0 (2025-10-13).
  <https://github.com/fboulnois/pg_uuidv7>
- **AWS RDS** PostgreSQL supported extensions ·
  **Neon** extension list · **Supabase** extensions overview.

### Other

- **E. F. Codd**, "A Relational Model of Data for Large Shared Data Banks",
  *CACM* 13(6), June 1970, pp. 377–387. Canonical record at
  [dl.acm.org](https://dl.acm.org/doi/10.1145/362384.362685) (paywalled); quoted
  from the scanned copy mirrored at
  [seas.upenn.edu](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf).
- **International ISBN Agency**, "What is an ISBN?" — the 10→13 digit change.
  <https://www.isbn-international.org/content/what-isbn/10>

---

## 8. What could not be verified

1. **No benchmark numbers appear in this document, because no primary source
   provides any.** The PostgreSQL manual publishes no performance comparison of
   `bigint`, `uuid` and text keys — not for insert throughput, index size, or
   cache behaviour. The only magnitude claim anywhere in the primary sources is
   RFC 9562 §6.11's "one order of magnitude or more", which is unattributed,
   names no workload or engine, and is framed around clustering behaviour that
   §2.6 shows PostgreSQL does not have. Every performance statement here is
   either a quoted mechanism or labelled arithmetic.

2. **The write-amplification argument is an inference, not documentation.** The
   docs establish the `full_page_writes` mechanism and the rightmost-page insert
   behaviour separately, and never connect them. The chain in §2.7 — random keys
   → more distinct pages dirtied per checkpoint → more full-page images — is my
   reasoning from two quoted facts.

3. **PostgreSQL documents nothing about enumeration, guessability, or ID
   exposure.** The stated rationale for the `uuid` type is uniqueness in
   distributed systems, not security. The entire "expose a UUID so attackers
   cannot enumerate rows" argument has no support in the project's documentation.
   It may well be sound; §5.1 sources it to RFC 9562 instead, which is where the
   normative language actually lives.

4. **Three widely-quoted constants are not in the manual** and are cited from
   source: `uuid` = 16 bytes (`UUID_LEN`), the 2704-byte maximum index entry
   (`BTMaxItemSize`), and the rightmost-leaf fastpath for ascending inserts. A
   full-text search of `btree.html` for "fastpath", "rightmost", "ascending" and
   "monotonic" returns zero hits. §65.1.4 does direct readers to the source
   README, but a header file is still weaker evidence than a documented
   guarantee, and these could change without a release note.

5. **MAXALIGN's value is never stated by the docs** — only "the MAXALIGN distance
   for the platform". All arithmetic in §2.3 assumes 8 on 64-bit.

6. **The docs make no claim that join-key width affects join performance.** §6.5
   says so explicitly rather than repeating the common assertion. The `work_mem`
   spill reasoning offered there is labelled as inference.

7. **`avg_leaf_density` and `leaf_fragmentation` are undefined by the manual.**
   The quoted descriptions — "Average density of leaf pages", "Leaf page
   fragmentation" — are complete. No computation, no units, no threshold for
   "bad". Any target figure for these does not come from PostgreSQL.

8. **The introducing version of `uuid_extract_timestamp()` and
   `uuid_extract_version()` was not verified.** Both are present in 18; the PG17
   release notes were not fetched, so no version is claimed for them.

9. **Two prompt assumptions turned out to be false and are not repeated here.**
   The `uuid-ossp` page contains no statement that `gen_random_uuid()` is
   preferable — only the generic "This module is only necessary for special
   requirements beyond what is available in core PostgreSQL." And §8.1.4 does not
   recommend identity columns over `serial`; it calls identity "Another way", and
   the only documented advantage is the PG10 release note's "SQL standard
   compliant".

10. **Snowflake's sign bit, custom epoch, and 5+5 datacenter/worker split are not
    in its README.** The epoch (`1288834974657`) and the bit split come from
    `IdWorker.scala`. The sign bit is stated nowhere and is only inferable from
    41 + 10 + 12 = 63 of a signed `Long`.

11. **Two Twitter sources are Wayback captures, not live pages.** The 2010
    announcement returns HTTP 403 at its live URL, and the developer
    documentation on Twitter IDs has been removed — the live URL now redirects to
    a page without that content. Capture dates are given in §7. An archived copy
    of the original is still a primary source; a blog post describing it would
    not be.

12. **Instagram's sharded-ID post could not be retrieved** — the host refused the
    connection and the Wayback availability API rate-limited. No Instagram bit
    layout is quoted anywhere in this document.

13. **Codd is quoted from a university mirror of the scanned original**, not from
    the ACM Digital Library, whose full text is paywalled. The scan's page footer
    matches the citation. OCR run-together artifacts were corrected in two places
    ("possessmore" → "possess more", "casein" → "case in"). Codd's 1970 paper
    does **not** use the term "surrogate key"; that term comes from his later
    work and is not attributed to the paper here.

14. **The ULID specification cannot be cited by version.** It has no tags, no
    releases, no version number and no internal date. §4.5 cites it by commit
    SHA (`d0c7170`, 2019-05-23) because that is the only stable reference
    available.

15. **ULID's case-insensitivity is a feature-bullet claim, not a specified
    behaviour.** "Case insensitive" appears only in the README's headline list;
    the Encoding section defines a single uppercase alphabet and says nothing
    normative about accepting or emitting lowercase. The same applies to "No
    special characters (URL safe)".

16. **Supabase's support for `pg_uuidv7` could not be determined.** Its docs do
    not enumerate extensions ("over 50 extensions"), and there is no first-party
    page for it. Absence of a page is not evidence of absence of the extension,
    so §3.5 claims nothing either way.

17. **TypeID's "binary representation" is not specified.** The spec defines only
    the canonical lowercase string encoding. The `uuid`-column recommendation in
    §4.7 is my inference from the spec's requirement that the suffix decode to a
    valid UUIDv7, not a documented storage format.

18. **Per-attribute alignment and column-ordering advice is not documented.**
    `storage-page-layout.html` covers page and tuple *header* layout and the
    `t_hoff` MAXALIGN rule, but says nothing about inter-column padding or
    ordering a `bigint` beside a `uuid`. Both types are fixed-width, so no
    padding between them is expected — that is inference, not a quotation.
