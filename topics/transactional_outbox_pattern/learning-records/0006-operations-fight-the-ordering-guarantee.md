# Operating the outbox fights the ordering guarantee you just bought

Decided 2026-09-10 in Lesson 06. The mission's production-failure list had three
items left — poison messages, relay lag, outbox bloat — and the working
assumption was that they were three independent chores. They are not.

## The decision

Four operational choices, each closing one of the remaining failure modes:

1. **Health metric is age, not count**: `max(now() - created_at)` over
   unpublished rows, grouped by shard. Count cannot separate busy from stuck.
2. **Poison messages are bounded on both sides.** The broker already counts
   (quorum-queue delivery limit, default 20) and dead-letters; turn on
   `at-least-once` dead-lettering because the default strategy can lose the
   message. The outbox has no such counter, so `attempts` gets a limit — and
   crossing it **parks the whole aggregate**, not the row.
3. **Retention is by daily partition and `DROP TABLE`**, not by `DELETE`.
4. **The aggregate cursor is exempt from retention.** Two of the three tables
   are logs; one is state.

## The insight worth keeping

This is the one to carry into a room:

> Ordering and poison-message isolation pull in opposite directions, and no
> position gets both. Per-aggregate order was bought by making each stream
> serial, and serial is exactly what turns one bad message into a stalled
> stream. Every mitigation — the delivery limit, the DLX, the parked aggregate
> — is a decision to break that order at a stated point. So state the point.
> "After twenty attempts we stop, dead-letter it and page someone" is an
> answer; "it retries until it works" is an outage with a countdown on it.

The corollary is the sharper half, and it is the thing an interviewer can push
on: the *obvious* poison-message fix is a regression. Filtering `attempts < N`
in the claim query publishes an aggregate's later events after skipping an
earlier one — order 42 shipped without ever being paid, which is the exact
failure Lesson 05 opened with. The unit you skip must be the aggregate.

## The second insight: bloat is silent by construction

> The partial index that makes the relay fast is what makes bloat invisible.
> The claim query's cost tracks the backlog, not the table, so a 106 MB outbox
> holding 18,000 live rows has no slow query, no latency signal and no alert.
> You find out when the disk fills.

This reframes the standard advice. "Bloat degrades your queries" is the lazy
version and is wrong here — the glossary said it and has been corrected. Table
size has to be a first-class metric precisely *because* nothing else moves.

## What was measured, not read

Second measured round, same PostgreSQL 17.11 image as Lesson 05. Full numbers
in the RESOURCES gaps; the three that shaped the lesson:

- **The naive attempt filter publishes `shipped` for an aggregate whose `paid`
  was skipped.** Shown as a `string_agg` per aggregate, so the regression is
  visible rather than argued. This became the lesson's trap callout.
- **One `UPDATE` per row doubled the heap** (52 → 106 MB over 200k rows), and
  deleting 91% of rows then plain-vacuuming returned nothing to the OS. The
  doc's "special case" exception never applies to a retention job, because the
  pages it frees are at the front.
- **Partitioning costs the claim query nothing measurable**: 203 buffers
  partitioned against 202 flat, gaining a `Merge Append` over each partition's
  local partial index. This one *removed* an objection rather than confirming
  one, which is the more useful kind of measurement.

## Why the sourcing mattered here

Two claims in this lesson would have been wrong from memory and are right from
the docs: the quorum-queue delivery limit's default (20, and only since
RabbitMQ 4.0), and the fact that the default dead-letter strategy is
`at-most-once` and can lose the message. The second is the kind of detail that
ends a question in an interview, and no amount of reasoning would have produced
it.

Conversely, one claim was deliberately *not* made: RabbitMQ's docs do not state
whether a requeued message returns to the head or the tail, so the lesson frames
the consumer-side stall purely as "the delivery limit ends the retry loop" and
never asserts head-of-line blocking at the broker.

## Revisit when

The Python actually runs (Lesson 07). Several operational claims here — that
the error-recording write must be committed separately, that a restart mid-claim
is safe — are argued from mechanism and have never been observed. A deliberate
`kill -9` would settle them.
