# Mission: Primary Keys and External Identifiers in PostgreSQL

## Why

To be able to choose a PostgreSQL identifier strategy from evidence rather than
from folklore, and to still be able to do it in a year. The identifier decision
is made once per table and is close to irreversible — changing the type of a key
column rewrites the table and every index that references it — so it is worth
understanding at the level of the mechanism rather than the recommendation. The
target is being able to reconstruct *why* a `bigint` sequence inserts differently
from a UUIDv4, not being able to recall which one a blog post preferred.

## Success looks like

- Explaining from memory why a random key costs about 2.5× the leaf pages of a
  sequential one in PostgreSQL, and why most of that gap is split behaviour
  rather than the eight extra bytes.
- Stating that PostgreSQL has no clustered index, and naming the three
  documented facts that establish it — because that single fact invalidates most
  advice imported from InnoDB or SQL Server.
- Naming the exact scope of `uuidv7()`'s monotonicity guarantee, and why "sort by
  id to get creation order" is unsafe across a connection pool.
- Reciting RFC 9562's normative position that UUIDs **MUST NOT** be used as
  security capabilities, and explaining why swapping `bigint` for `uuid` is not a
  fix for a missing authorisation check.
- Drawing the dual-identifier schema from memory, naming its four costs, and
  saying which of them is the one that actually bites.
- Separating a documented guarantee from a `#define` from your own arithmetic,
  and refusing to state a benchmark number that no primary source provides.

## Constraints

- Long-term retention is the goal, so lessons carry retrieval practice and are
  written to be spaced over days rather than read in one sitting.
- Built in a single pass rather than dripped out. The spacing lives in the study
  advice, not in the delivery schedule.
- Every claim is traceable to a quoted primary source, a labelled source-code
  reference, or labelled arithmetic. Nothing is asserted on recall.
- PostgreSQL 18 is the version taught. Where a feature is newer than 13, the
  release that introduced it is named so the lessons stay usable on older
  servers.

## Out of scope

- Benchmarks. No primary source publishes one for this question, so none is
  quoted, invented, or implied.
- Other engines. InnoDB and SQL Server appear only where an argument imported
  from them has to be disarmed.
- ORM and framework-specific configuration for any particular stack.
- Sharding and distributed-database architecture in their own right. Multi-node
  generation is covered only as the capability that motivates a 128-bit key.
