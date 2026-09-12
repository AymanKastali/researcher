# PostgreSQL Identifier Resources

Sources for this topic, kept in three grades of evidence that the lessons never
blur. A documented guarantee, a header file, and someone's arithmetic are three
different kinds of claim, and each page says which one it is using.

1. **Documented guarantees** — the PostgreSQL manual, RFC 9562, vendor specs.
2. **Source code** — `REL_18_STABLE` headers and READMEs, used only where the
   manual is silent, and labelled every time. A `#define` is not a promise.
3. **Derived arithmetic** — computed from quoted constants, always labelled.

All entries were fetched and read while writing
`docs/research/postgres-identifier-strategies.md` in this repo. PostgreSQL 18 is
the version taught; unqualified references to "the docs" mean the 18.6 build of
`/docs/current/`.

## Knowledge

### Specifications and standards

- [RFC 9562: Universally Unique IDentifiers (UUIDs)](https://www.rfc-editor.org/rfc/rfc9562.html)
  Davis, Peabody & Leach, IETF, Standards Track, May 2024. Obsoletes RFC 4122.
  The normative text for every UUID claim in this topic. Use for: §2.1 index
  locality, §5.4 UUIDv4's 122 bits, §5.7 UUIDv7's layout and 74 bits, §6.2 the
  monotonic counter methods, §6.4 multi-node generation, §6.7 collision impact
  framing, §6.9 the CSPRNG and fork caveat, §6.11 the "order of magnitude"
  claim, §6.13 binary storage and the warning against name-based natural keys,
  §8 security considerations.
  **The single most important reading in this topic.**
- [RFC 4122](https://www.rfc-editor.org/rfc/rfc4122)
  Leach, Mealling & Salz, IETF, July 2005. Obsoleted by 9562. Use only for the
  historical contrast: 4122 §6 said "Do not assume that UUIDs are hard to
  guess"; 9562 hardened it to **SHOULD NOT** / **MUST NOT**.
- [ULID specification](https://github.com/ulid/spec)
  `ulid/spec` on GitHub, GPL-3.0. **No version, no tags, no releases, no date
  inside the document.** `master` last committed `d0c7170`, 2019-05-23, which is
  the only stable way to cite it. Use for: the 48+80 layout, Crockford's Base32,
  the monotonicity section, and the intra-millisecond sort caveat.
- [TypeID Specification v0.3.0](https://github.com/jetify-com/typeid/blob/main/spec/README.md)
  jetify-com. Use for: the three-part format, the prefix regex, the base32
  encoding rule, and the requirement that the suffix decode to a valid UUIDv7.
- [E. F. Codd, "A Relational Model of Data for Large Shared Data Banks"](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf)
  *Communications of the ACM* 13(6), June 1970, pp. 377–387. Canonical record at
  [dl.acm.org](https://dl.acm.org/doi/10.1145/362384.362685) (paywalled); quoted
  here from the University of Pennsylvania scan of the original. Use for: the
  original definitions of primary key and foreign key, the "arbitrarily
  selected" clause, and the fact that Codd's own example is a *natural* key.
  **Caveat:** the word "surrogate" does not appear in the 1970 paper.

### PostgreSQL 18 documentation

The manual is the authority wherever it speaks. Grouped by what each page is
reached for.

- Types and functions —
  [§8.1 Numeric](https://www.postgresql.org/docs/current/datatype-numeric.html)
  (`bigint` is 8 bytes) ·
  [§8.3 Character](https://www.postgresql.org/docs/current/datatype-character.html)
  (no performance advantage to `character(n)`) ·
  [§8.12 UUID](https://www.postgresql.org/docs/current/datatype-uuid.html)
  (a "128-bit quantity"; the type stores *any* UUID) ·
  [§9.14 UUID functions](https://www.postgresql.org/docs/current/functions-uuid.html)
  (`uuidv7()`, `uuidv4()`, `uuid_extract_timestamp()`) ·
  [§9.17 Sequence functions](https://www.postgresql.org/docs/current/functions-sequence.html)
  (why gapless sequences are impossible).
- Schema and DDL —
  [§5.3 Identity columns](https://www.postgresql.org/docs/current/ddl-identity-columns.html) ·
  [§5.5 Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
  (primary keys; foreign keys; the advice to index the referencing side) ·
  [CREATE TABLE](https://www.postgresql.org/docs/current/sql-createtable.html)
  (`ALWAYS` vs `BY DEFAULT`) ·
  [CREATE SEQUENCE](https://www.postgresql.org/docs/current/sql-createsequence.html)
  (`CACHE` and out-of-order values) ·
  [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html)
  (fillfactor, right-edge extension, `INCLUDE`) ·
  [ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)
  (type changes rewrite the table under `ACCESS EXCLUSIVE`) ·
  [CLUSTER](https://www.postgresql.org/docs/current/sql-cluster.html)
  (clustering is a one-time operation).
- Indexes —
  [§11.9 Index-only scans](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
  (all indexes are secondary; the visibility-map dependency) ·
  [§65.1 B-Tree](https://www.postgresql.org/docs/current/btree.html)
  (max entry size, page splits, bottom-up deletion, deduplication, and the
  pointer to the source README).
- Storage —
  [§66.1 File layout](https://www.postgresql.org/docs/current/storage-file-layout.html) ·
  [§66.2 TOAST](https://www.postgresql.org/docs/current/storage-toast.html) ·
  [§66.6 Page layout](https://www.postgresql.org/docs/current/storage-page-layout.html)
  (the 24-byte page header, 4-byte line pointer, 23-byte tuple header) ·
  [§66.7 HOT](https://www.postgresql.org/docs/current/storage-hot.html)
  (the mechanical argument against mutable keys).
- Configuration and maintenance —
  [§20.4.1 Memory](https://www.postgresql.org/docs/current/runtime-config-resource.html)
  (`shared_buffers`, `work_mem`) ·
  [§20.5.1 WAL](https://www.postgresql.org/docs/current/runtime-config-wal.html)
  (`full_page_writes`, `wal_compression`) ·
  [§24.2 Reindexing](https://www.postgresql.org/docs/current/routine-reindex.html).
- Diagnostics —
  [§14.1 Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html) ·
  [F.23 pageinspect](https://www.postgresql.org/docs/current/pageinspect.html)
  (the real page dump that validates the arithmetic) ·
  [F.26 pgcrypto](https://www.postgresql.org/docs/current/pgcrypto.html) ·
  [F.33 pgstattuple](https://www.postgresql.org/docs/current/pgstattuple.html) ·
  [F.47 uuid-ossp](https://www.postgresql.org/docs/current/uuid-ossp.html).
- Release notes, for dating every feature —
  [10](https://www.postgresql.org/docs/release/10.0/) ·
  [11](https://www.postgresql.org/docs/release/11.0/) ·
  [13](https://www.postgresql.org/docs/release/13.0/) ·
  [15](https://www.postgresql.org/docs/release/15.0/) ·
  [18](https://www.postgresql.org/docs/release/18.0/) ·
  [versioning policy](https://www.postgresql.org/support/versioning/).

### PostgreSQL source, `REL_18_STABLE`

Second-grade evidence. Reached for only where the manual is silent, and labelled
as source every time it is used. The manual itself sends readers here: §65.1.4
says to see `src/backend/access/nbtree/README` "for a much more detailed,
internals-focused description".

- `src/include/utils/uuid.h` — `#define UUID_LEN 16`. The origin of "a UUID is
  16 bytes", which the manual never states.
- `src/include/access/itup.h` — `IndexTupleData`, giving the 8-byte index tuple
  header.
- `src/include/access/nbtree.h` — `BTMaxItemSize` (2704 at 8 kB pages),
  `BTPageOpaqueData`.
- `src/backend/access/nbtree/README` — "Fastpath For Index Insertion" and
  "Deduplication in unique indexes".
- `src/backend/access/nbtree/nbtsplitloc.c`, `_bt_findsplitloc()` — the
  rightmost-page fillfactor behaviour. **The most important single quotation in
  this topic**, and it exists nowhere in the manual.
- [Commit `78c5e141e`](https://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=78c5e141e9c139fc2ff36a220334e4aa25e1b0eb),
  "Add UUID version 7 generation function", Masahiko Sawada, 2024-12-11. Use for
  the exact scope of the monotonicity guarantee. **Caveat:** the commit message
  cites "RFC 9652"; that is a typo in the commit itself.

### Vendor and implementation sources

- [twitter-archive/snowflake](https://github.com/twitter-archive/snowflake)
  `README.mkd` and `IdWorker.scala` at the `snowflake-2010` tag; `master`
  README for the retirement notice. Repository archived, last push 2020-07-22.
  Use for: the 41/10/12 bit layout, k-sortedness, and ZooKeeper worker ids.
- [Twitter, "Announcing Snowflake"](https://web.archive.org/web/20240422012321/https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake)
  1 June 2010. **The live page returns HTTP 403**; read from the Wayback capture
  of 2024-04-22. Use for: the 64-bit constraint and why UUIDs were rejected.
- [Twitter developer documentation, "Twitter IDs"](https://web.archive.org/web/20240425032320/https://developer.twitter.com/en/docs/twitter-ids)
  **The live URL no longer carries this content**; read from the Wayback capture
  of 2024-04-25. Use for: the first-party statement that 64-bit ids break
  JavaScript's 53-bit numbers, and `id_str`.
- [Discord API reference](https://docs.discord.com/developers/reference)
  Use for: a live Snowflake variant with a different bit split, and the
  independent decision to return ids as strings.
- [jetify-com/typeid-sql](https://github.com/jetify-com/typeid-sql)
  The official PostgreSQL implementation. Use for: both offered encodings, and
  why neither is what you want as a key. **Caveat:** tracks spec v0.2 while the
  Go and TypeScript implementations are at v0.3.
- [fboulnois/pg_uuidv7](https://github.com/fboulnois/pg_uuidv7)
  MPL-2.0, v1.7.0 (2025-10-13). Use for: `uuid_timestamptz_to_v7()`, the
  range-boundary constructor with no core equivalent, and the README's own
  narrowing of its remit after PostgreSQL 18.
- [Stripe API upgrades](https://docs.stripe.com/upgrades)
  Use for: the position that changing an object id's length or prefix is a
  *backward-compatible* change — the opposite bet to TypeID's.
- [International ISBN Agency, "What is an ISBN?"](https://www.isbn-international.org/content/what-isbn/10)
  Use for: the 10→13 digit change, the cleanest documented case of an issuing
  authority widening a natural key on a date it chose.
- AWS RDS PostgreSQL supported extensions · Neon extension list · Supabase
  extensions overview. Use for: which extensions a managed platform will
  actually let you install, which usually decides this question before
  performance does.

## Wisdom (Communities)

Every entry below was checked against the PostgreSQL project's own
[community page](https://www.postgresql.org/community/) on 12 September 2026.
Channels that page does not list are not listed here either.

- [pgsql-general](https://www.postgresql.org/list/pgsql-general/) — the project's
  own list for "General PostgreSQL Support", publicly archived. Use for: schema
  and index-design questions answered by people who read the source. This is the
  right place to settle a question the manual leaves open, which in this topic is
  most of §2.
- [pgsql-hackers](https://www.postgresql.org/list/pgsql-hackers/) — the
  development list, publicly archived. `uuidv7()` was argued into existence here
  before commit `78c5e141e` landed. Use for: finding out *why* a feature is
  shaped the way it is. Searching the archive for the feature name is usually
  more informative than the release note, because the objections survive.
- [#postgresql on Libera Chat](https://www.postgresql.org/community/irc/) —
  described by the project as "General technical PostgreSQL discussion". Use for:
  a quick real-time sanity check on a schema, which is the one thing a mailing
  list is bad at. `#postgresql-lounge` is the off-topic channel.
- [Local PostgreSQL User Groups](https://www.postgresql.org/community/user-groups/)
  — "many local PostgreSQL User Groups all over the world". Use for: the
  experience of people running these choices at scale, which is exactly what no
  specification records and no mailing list thread quite captures.
- [Planet PostgreSQL](https://planet.postgresql.org/) — "an aggregator of blogs
  covering many topics around PostgreSQL". Use for: watching the identifier
  argument recur, and for practising the skill this topic actually teaches —
  spotting which claims in a post are sourced and which are repeated. That
  practice is more valuable here than in most subjects, because the folklore is
  unusually dense and unusually checkable.
- [IETF UUIDREV working group archive](https://mailarchive.ietf.org/arch/browse/uuidrev/)
  — the group that produced RFC 9562. **Status: concluded**, having "completed
  all milestones and fulfilled its charter", so this is a reading resource rather
  than a live community. Use for: why a clause that looks arbitrary is worded the
  way it is — the monotonic-counter methods of §6.2 above all.

No preference for or against joining communities has been stated. Record it here
if one is.

## Gaps

Areas the mission touches where the public record is thin. These are gaps in the
sources, not omissions from this workspace.
`docs/research/postgres-identifier-strategies.md` §8 lists all eighteen.

- **No primary source publishes a benchmark** for `bigint` versus `uuid` versus
  text keys in PostgreSQL — not for insert throughput, index size, or cache
  behaviour. The only magnitude claim anywhere is RFC 9562 §6.11's "one order of
  magnitude or more", which names no workload and no engine, and is framed
  around clustering behaviour PostgreSQL does not have.
- **Three widely-quoted constants are not in the manual** — `uuid` = 16 bytes,
  the 2704-byte maximum index entry, and the rightmost-leaf fastpath. All three
  are cited from source here, and could change without a release note.
- **`avg_leaf_density` and `leaf_fragmentation` are undefined by the manual.**
  The quoted one-line descriptions are complete: no computation, no units, no
  threshold for "bad". Any target figure for them does not come from PostgreSQL.
- **The ULID specification cannot be cited by version** — no tags, no releases,
  no internal date. It is cited by commit SHA because nothing better exists.
- **Instagram's sharded-ID post could not be retrieved.** The host refused the
  connection and the Wayback availability API rate-limited, so no Instagram bit
  layout appears anywhere in this workspace.
- **No textbook treatment was quotable in-session.** A recognised database
  textbook on physical index design would strengthen lessons 2–5, which
  currently rest on the manual plus source code. If one becomes available, those
  lessons should be revisited against it.
