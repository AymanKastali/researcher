# The worked example stays a polling publisher

Decided 2026-09-10 in Lesson 04, after teaching the polling-vs-CDC comparison
properly rather than as a shrug. The mission requires Ayman to *argue* the
trade-off and *pick one with reasons*, so the lesson had to end in a decision,
not a table.

## The decision

**Polling**, for this stack: Postgres, RabbitMQ, SQLAlchemy async, no existing
streaming platform. Three reasons, in the order they carry weight:

1. **The cost lands on the primary.** A replication slot retains WAL and blocks
   `VACUUM` whether or not anything is reading it, so a connector that is off is
   a database availability incident. `max_slot_wal_keep_size` does not fix that,
   it only swaps a full disk for an unusable slot.
2. **The reference deployment is Kafka-shaped.** Reaching a queue we already run
   would mean adopting a streaming platform to avoid writing a loop.
3. **The thing CDC buys is not the thing we need.** Commit order is real and
   polling genuinely cannot match it — but per-aggregate ordering is almost
   always sufficient, and that is reachable from polling.

Revisit when: Debezium is already deployed and owned by someone else; global
ordering becomes a hard requirement; the polling latency floor starts to hurt;
or a third service wants the same mechanism, at which point one connector beats
three relays.

## Why this matters beyond one lesson

Lessons 05 and 06 now have a concrete relay to reason about. Ordering fixes can
be written against the polling query, and the health metric can be "age of the
oldest unpublished row" rather than "lag, in whichever of two senses".

## The insight worth keeping

The strongest framing found while writing this was **the asymmetry of failure**,
and it is what actually decides the argument in a room:

> A polling relay that is down is a messaging problem — rows pile up, lag rises,
> you restart it. A CDC connector that is down is a database problem — the slot
> silently pins WAL until the disk fills.

Everything else in the comparison is a fair fight. This is not, and it is the
part candidates who have only read about CDC never say.

Second-best framing, and the one that reframes the whole question: **CDC
replaces the relay, not the outbox.** Said early, it converts "which pattern?"
into "which relay implementation?" — a much easier argument to win.

## Unverified

Debezium's non-Kafka runtimes were not checked. The lesson is worded to send
Ayman to verify rather than to assert. See `NOTES.md`, debts carried by Lesson
04.
