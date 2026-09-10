# Mission: Transactional Outbox Pattern (Python + Postgres)

## Why

Ayman wants to hold his own on the transactional outbox pattern under
questioning — in interviews and in system-design discussions — not just
recognise the name. That means deriving the pattern from first principles at a
whiteboard, defending the trade-offs, and writing the Postgres and Python that
would actually back it up.

## Success looks like

- Can state the **dual-write problem** precisely and enumerate every failure
  ordering, without notes, in under 90 seconds.
- Can write the outbox table DDL and the `SELECT ... FOR UPDATE SKIP LOCKED`
  relay query from memory, and explain what each clause buys.
- Can explain why the pattern gives **at-least-once**, not exactly-once,
  delivery — and what the consumer side must do about it (idempotent consumer
  / inbox).
- Can argue **polling publisher vs. transaction log tailing (CDC)** and pick
  one for a given scenario with reasons.
- Can name the failure modes that bite in production: ordering, poison
  messages, outbox table bloat, relay lag, multiple relay instances.
- Can implement the whole thing in **SQLAlchemy 2.0 async + asyncpg** against
  **RabbitMQ**.
- Can configure RabbitMQ so neither half of the pipeline loses a message:
  publisher confirms plus `mandatory`, manual acks, bounded prefetch, quorum
  queues with a delivery limit and a dead-letter exchange.

## Constraints

- Broker is **RabbitMQ**, pinned 2026-09-10 (previously "queue-based, one of
  RabbitMQ / SQS / NATS"). Ack semantics, redelivery and dead-letter exchanges,
  rather than Kafka's partitioned log. SQS and NATS stay as one-line contrasts
  for interview breadth, never as the worked example.
- Python stack is **SQLAlchemy 2.0 async + asyncpg**.
- Relay is a **polling publisher**, decided 2026-09-10 in Lesson 04 — the
  replication slot's cost lands on the primary, and Debezium's reference
  deployment is Kafka-shaped. CDC stays in the material as the comparison, not
  as the worked example. See `learning-records/0004-*`.
- Ordering target is **per-aggregate, not global**, decided 2026-09-10 in
  Lesson 05. Delivered by hash-sharding the relay, one queue per shard, and
  single active consumer. Global total order is taught as available-and-refused,
  with its price stated. See `learning-records/0005-*`.
- Health metric is **age of the oldest unpublished row, grouped by shard** —
  not backlog count, which cannot separate busy from stuck. Poison messages are
  bounded on both sides: the quorum-queue delivery limit plus an at-least-once
  DLX on the broker, and a max-attempt limit that **parks the whole aggregate**
  in the outbox. Retention is by daily partition and `DROP TABLE`, and the
  aggregate cursor is explicitly exempt. Decided 2026-09-10 in Lesson 06; see
  `learning-records/0006-*`.
- Starting point: solid on transactions and `BEGIN`/`COMMIT`; **new to
  `FOR UPDATE SKIP LOCKED`, `LISTEN`/`NOTIFY`, and logical decoding**.
- Depth is aimed at *explaining under questioning*, so lessons must build
  recall, not just recognition.

## Out of scope (for now)

- Kafka-specific concerns: partition keys, per-key ordering, the idempotent
  producer.
- Event sourcing as an alternative to outbox.
- Full saga orchestration — outbox is a building block for sagas, but sagas
  are their own topic.
