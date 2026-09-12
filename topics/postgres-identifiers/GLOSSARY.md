# PostgreSQL Identifier Glossary

The vocabulary of choosing a key: what the relational model actually named, the
physical structures the choice lands in, the candidate formats, and the grades of
evidence this topic keeps apart. Where a term has a quoted definition in a
specification or in the PostgreSQL manual, that quotation is the authority and
this entry is its compression.

## The relational terms

**Primary key**:
The candidate key a designer selects to identify rows of a table. In PostgreSQL
it is a *designation* carrying a `UNIQUE` B-tree index and `NOT NULL`, not a
distinct physical structure. Defined by
[Codd 1970 p. 379](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf) and
[§5.5.4](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS).
_Avoid_: The ID, the row key, the clustered key

**Candidate key**:
Any column or combination that uniquely identifies rows and has no superfluous
part. Codd calls these "nonredundant primary keys" and says one is "arbitrarily
selected" to be *the* primary key.
_Avoid_: Alternate key, unique key

**Foreign key**:
"A domain (or domain combination) of relation R [that] is not the primary key of
R but its elements are values of the primary key of some relation S"
([Codd 1970](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf)). In
PostgreSQL it may reference any unique constraint, not only the primary key.
_Avoid_: Reference, pointer, FK link

**Surrogate key**:
A key whose values carry no meaning outside the database and are issued by it or
for it. **Not Codd's term** — the word does not appear in the 1970 paper.
_Avoid_: Artificial key, technical key, meaningless key

**Natural key**:
A key drawn from data that already means something to someone outside the
database — an email address, an ISBN, a country code. Its format is controlled by
its issuing authority, not by you.
_Avoid_: Business key, semantic key, real key

**Issuing authority**:
Whoever defines and may change the format of a natural key. The reason a natural
key is a schema risk: the ISBN agency widened ISBNs from 10 to 13 digits on
1 January 2007, on a date it chose.
_Avoid_: The source system, upstream, the standard

## The physical structures

**Heap**:
The table's own data area, stored in its own file. Rows go wherever the free
space map offers, never in key order.
_Avoid_: The table file, the data pages, the store

**Secondary index**:
An index stored separately from the heap. "All indexes in PostgreSQL are
secondary indexes"
([§11.9](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)),
which is why PostgreSQL has no clustered index.
_Avoid_: Non-clustered index (the contrast it implies does not exist here)

**Clustered index**:
An index that *is* the table's physical row order, so the key value determines
where the row lives. A structure PostgreSQL does not have; `CLUSTER` is a
one-time reordering, not a maintained property. Named here only to disarm advice
imported from engines that do have one.
_Avoid_: Index-organised table, primary index

**Page**:
The fixed unit of storage and I/O, "usually 8 kB"
([§66.6](https://www.postgresql.org/docs/current/storage-page-layout.html)). Every
cost in this topic is counted in pages, never in rows.
_Avoid_: Block, chunk, disk page

**Leaf page**:
A B-tree page holding actual index entries rather than downlinks to lower levels.
Where key width is paid for.
_Avoid_: Bottom page, data page, index block

**Line pointer**:
The 4-byte `ItemIdData` slot at the top of a page that locates one item within
it. Counted separately from the item itself in every arithmetic in this topic.
_Avoid_: Slot, item id, offset

**Index entry**:
One key occurrence in a leaf page: an 8-byte `IndexTupleData` header, the key
value, MAXALIGNed, plus its line pointer. The unit whose width a key type
decides.
_Avoid_: Index row, index tuple, key slot

**Fan-out**:
How many entries one page holds, and therefore how many children one internal
page can address. Sets tree depth logarithmically, which is why a 28% fan-out
reduction usually buys zero extra levels.
_Avoid_: Branching factor, page capacity

**Fillfactor**:
The percentage of a leaf page an index build or a right-edge extension fills,
defaulting to 90 for B-trees. Leaves room so that later inserts need not split
the page.
_Avoid_: Packing ratio, density setting

**Leaf density**:
How full leaf pages actually are. The number a key's insert ordering decides:
about 90% for an ordered key, tending toward 50% for a random one.
_Avoid_: Index bloat, fill ratio, utilisation

**Page split**:
The operation that makes room when a leaf page cannot fit an incoming entry, by
moving part of its contents to a new page and inserting a downlink in the parent
— which "may cause the parent to split in turn"
([§65.1.4](https://www.postgresql.org/docs/current/btree.html)).
_Avoid_: Rebalance, overflow, node split

**Rightmost-page fastpath**:
Two distinct optimisations for keys that arrive in increasing order: a split of
the rightmost page leaves the left side *fillfactor*% full "instead of the 50%
full result that we'd get without this special case", and a cached rightmost leaf
page lets an insert "avoid the cost of walking down the tree". From
`nbtsplitloc.c` and the `nbtree` README; **not in the manual**.
_Avoid_: Append optimisation, sequential insert path

**HOT (heap-only tuple)**:
An update optimisation available only when "the update does not modify any
columns referenced by the table's indexes"
([§66.7](https://www.postgresql.org/docs/current/storage-hot.html)). The
mechanical reason a key must never change.
_Avoid_: In-place update, cheap update

**Write amplification**:
More bytes written than the change logically requires. Here it arises because
`full_page_writes` costs one ~8 kB image per *distinct page* first dirtied after
a checkpoint, so scattering inserts across many pages costs more WAL. **The link
to key ordering is inference, not documentation.**
_Avoid_: WAL bloat, I/O overhead

**Index-only scan**:
A scan answered entirely from an index, possible only when the visibility map
marks the candidate rows' heap pages all-visible. The mechanism an `INCLUDE`
column exists to serve.
_Avoid_: Covering scan, index-covered query

## The candidate formats

**Identity column**:
A column declared `GENERATED { ALWAYS | BY DEFAULT } AS IDENTITY`, backed by an
implicit sequence and implicitly `NOT NULL`. The SQL-standard spelling of an
autoincrementing column. `ALWAYS` additionally rejects any `UPDATE` to a value
other than `DEFAULT`.
_Avoid_: Serial, autoincrement, auto number

**Gap**:
A sequence value allocated but never committed. Guaranteed to occur — "PostgreSQL
sequence objects cannot be used to obtain 'gapless' sequences"
([§9.17](https://www.postgresql.org/docs/current/functions-sequence.html)) — and
never a security property.
_Avoid_: Hole, skipped id, lost number

**UUIDv4**:
A UUID of 122 random bits plus a fixed version nibble and two variant bits
([RFC 9562 §5.4](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.4)). No
structure, therefore nothing to correlate and nothing to order by.
_Avoid_: Random UUID, GUID, v4 GUID

**UUIDv7**:
A UUID of a 48-bit big-endian Unix millisecond timestamp followed by 74 bits not
fixed by the format
([RFC 9562 §5.7](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.7)).
Time-ordered to the millisecond, and the version the RFC says implementations
**SHOULD** use instead of v1 and v6.
_Avoid_: Sortable UUID, ordered GUID, sequential UUID

**ULID**:
A 128-bit identifier of a 48-bit millisecond timestamp plus 80 random bits,
canonically rendered as 26 characters of Crockford's Base32. Its specification is
unversioned and last committed 2019-05-23, and it defines no version or variant
bits — so a ULID in a `uuid` column is not a conformant RFC 9562 UUID.
_Avoid_: Sortable UUID (that is v7), lexicographic ID

**Snowflake**:
A family of 64-bit time-ordered identifiers after Twitter's 2010 design: 41 bits
of custom-epoch milliseconds, 10 bits of machine id, 12 bits of sequence.
A *family*, not a format — Discord's live variant uses a different split.
_Avoid_: Snowflake ID format, the Snowflake standard

**k-sorted**:
Snowflake's own weaker-than-sorted guarantee: ids are ordered to within a bounded
window rather than exactly — "we're promising 1s, but shooting for 10's of ms".
_Avoid_: Roughly sorted, approximately ordered

**TypeID**:
A UUIDv7 rendered as a lowercase type prefix, an underscore, and a 26-character
base32 suffix, whose suffix **MUST** decode to a valid UUIDv7
([spec v0.3.0](https://github.com/jetify-com/typeid/blob/main/spec/README.md)).
A presentation layer over a UUIDv7, and best adopted as one.
_Avoid_: Prefixed UUID, typed ID, Stripe-style ID

**Opaque identifier**:
An identifier whose holder is expected to parse nothing out of it, so its issuer
may change its length and format freely. Stripe classifies exactly that change as
backward-compatible; TypeID takes the opposite bet.
_Avoid_: Random string, token, blob id

## The architecture

**Dual-identifier pattern**:
Giving a row two identifiers, each doing one job: a narrow internal `bigint` that
every foreign key references and nothing serialises, and an external `uuid` that
appears in URLs and payloads and never appears in a foreign key.
_Avoid_: Public/private key (means something else entirely), external ID pattern

**Internal identity**:
The job of joining children to parents, anchoring indexes, and surviving physical
reorganisation. Judged on width, ordering, and immutability.
_Avoid_: The real key, the true id

**External reference**:
The job of appearing in URLs, API payloads, support tickets, and webhook bodies.
Judged on opacity, portability, and whether a client can mint one before the
database has seen the row.
_Avoid_: Public key, slug, display id

**Offline generation**:
Minting a valid identifier with no round trip to the database and no coordination
with any other generator. The capability a sequence cannot offer at any price,
and the honest reason to accept a 128-bit key.
_Avoid_: Client-side ID, pre-generated key

**Security capability**:
"An identifier whose mere possession grants access". RFC 9562 §8 says UUIDs
**MUST NOT** be used as one. Naming the anti-pattern is the point of the term.
_Avoid_: Secret URL, unguessable link, capability URL

## The grades of evidence

**Documented guarantee**:
A claim quoted from the PostgreSQL manual, an RFC, or a vendor's own
specification. The only grade that may be stated without qualification.
_Avoid_: The docs say, officially, canonically

**Source-code fact**:
A claim taken from a `REL_18_STABLE` header, README, or commit because the manual
is silent. Weaker: it may change without a release note. **A `#define` is not a
promise.**
_Avoid_: Internally, under the hood, actually

**Derived arithmetic**:
A number computed from quoted constants rather than quoted. Always labelled as
derived, and checkable — the model in this topic is validated against a real page
dump printed in the manual.
_Avoid_: Roughly, about, in practice (when what is meant is "I calculated it")

## Notes on usage

- **"Primary key" names a designation, not a structure.** A `UNIQUE` constraint
  plus `NOT NULL` is, in the manual's own words, "functionally almost the same
  thing". Saying "the primary key is faster" is almost always a claim about a
  B-tree index, and is clearer stated that way.
- **Say "leaf density", not "bloat"**, when describing what a random key costs.
  Bloat conflates three unrelated things — dead tuples, low fill, and fragmented
  pages — and only one of them is caused by key ordering.
- **Never say a random key "fragments the table".** It cannot: PostgreSQL has no
  clustered index, so the cost is confined to the B-tree on that key. That
  sentence is imported from InnoDB or SQL Server every time it appears.
- **Say "effectively unguessable", never "secure".** Per RFC 9562 §8, a UUID's
  unguessability is a property of the RNG behind it and is never an authorisation
  mechanism.
- **Distinguish "ordered" from "sortable by creation time".** `uuidv7()` is
  ordered enough for the B-tree's right edge while guaranteeing strict
  monotonicity only "within the same backend" — that is, within one connection.
  The two properties are routinely conflated and only one of them is documented.
- **A "UUID" stored in a `text` column is not a UUID decision, it is a storage
  mistake.** It roughly doubles the index entry and buys nothing, and RFC 9562
  §6.13 says so directly.
