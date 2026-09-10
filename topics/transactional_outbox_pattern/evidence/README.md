# Evidence

Captured output from the runs behind every measured claim in these lessons.
Where a lesson says *measured*, the transcript is here. Where a lesson says
*the docs say*, the citation is in [RESOURCES.md](../RESOURCES.md) instead.

The harness that produced these files has been deleted. This directory is
kept because a number with no transcript behind it is an assertion, and the
point of this topic is that nothing in it is an assertion.

## Environment

Every run below, on one laptop, 2026-09-10:

- PostgreSQL 17.11 (alpine), `wal_level=logical`
- RabbitMQ 4.3.5 on Erlang OTP 27 — a three-node cluster, quorum queues with
  a replica on each node
- Python 3.13, SQLAlchemy 2.0 async, asyncpg, aio-pika 10.0.1

No network between the parts, no competing load. **Quote the shape of the
latency results, not the milliseconds.**

## The files

- `01-crash-window.txt` — a relay killed on each side of the publish, and a
  control with no outbox at all. With an outbox: a duplicate the inbox
  absorbs on one side, a clean republish on the other. Without one: order 3
  is paid and no event exists, ever. Backs Lesson 01 and Lesson 03.
- `03-ordering.txt` — the ordering ladder from Lesson 05, four configurations
  over 460 events across 23 aggregates. The clean sharded run has 0
  per-aggregate violations **and 185 global-order inversions** — the two are
  not the same guarantee. Adding 5% requeues at prefetch 20 breaks it: 15
  violations across 12 aggregates. Prefetch 1 returns it to 0.
- `04-requeue-position.txt` — five messages, message 1 rejected once, at three
  prefetch levels on both queue types. A requeued message returns to the
  **head**; what displaces it is the consumer's own prefetch window. This is
  the probe that predicted the prefetch-1 result above before it was run.
- `05-poison-dlx.txt` — one poison message against `x-delivery-limit: 3`.
  Trimmed: the marker in the file marks roughly 6,000 identical POISON lines
  removed, which is itself the finding — the limit never fired.
- `06-delivery-limit.txt` — the isolation of that finding.
  `nack(requeue=true)` reached 12 deliveries against a limit of 3; the same
  message returned by closing the channel was counted out at 4. Backs the
  correction in Lesson 06.

## Two things these files do not show

- **Failover.** The cluster is three nodes, but no run kills the queue leader.
  That quorum queues survive losing a node remains the vendor's claim.
- **The dead-letter hop.** In `06-delivery-limit.txt` the counted-out message
  left the queue and did not arrive on the bound dead-letter queue —
  `dead-lettered=0`. Unexplained. Lesson 06 says so rather than smoothing it
  over.
