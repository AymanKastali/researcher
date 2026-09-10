# The duplicate the outbox manufactures says `redelivered=False`

Recorded 2026-09-10 in Lesson 07, the first session in this workspace that runs
Python rather than reasoning about it. Postgres 17.11 and RabbitMQ 4.3.5 in
Docker, producer / relay / consumer as three real processes, SQLAlchemy 2.0.52
+ asyncpg 0.31.0 + aio-pika 10.0.1.

## The finding

> The duplicate a crashed relay produces arrives at the consumer with
> `redelivered=False`. To the broker it is not a redelivery at all — it is a
> fresh publish of a message it has never seen, carrying an application-level
> `message_id` RabbitMQ attaches no meaning to. `redelivered` only ever covers
> the broker's own half: a delivery that was un-acked and handed out again.
>
> So a consumer that branches on `redelivered` to decide whether to deduplicate
> is broken, and broken in the silent direction. The relay-side duplicate — the
> one the outbox actually manufactures — sails straight past it.

This is not in any doc read across seven lessons. The RabbitMQ confirms page
warns that *"consumers must be prepared to handle redeliveries"*, which reads
as though `redelivered` is the signal to watch. Measurement says the opposite
for the duplicate this pattern is specifically about.

## The second insight: what the outbox actually does

Watching the crash window sharpened a sentence that was previously vague:

> The outbox does not eliminate the duplicate. The relay still cannot commit to
> Postgres and to the broker atomically — that is the dual-write problem one
> layer down, and it is unkillable. What the outbox does is **move the problem
> to a place where you have a transaction to fight it with.**

Measured: two deliveries, one shipment.

## What was measured, not read

- **End to end in 166 ms**, most of it the poll wait.
- **The crash window produces exactly the predicted disagreement.** `SIGKILL`
  between the confirm and the `published_at` update: row `unpublished=t`, one
  inbox row, one shipment. Restart, republish, inbox absorbs it.
- **The same crash without an outbox loses the order permanently.** Two orders
  paid, one shipment, and nothing anywhere records that a message was owed.
  Lesson 01's argument, in eight lines of output.
- **Two unsharded relays, 500 rows, 500 confirms — not 501.**
- **Polling latency has a shape, not a number**: p50 is half the poll interval
  and p95 is the poll interval, at 50 ms, 200 ms and 1 s alike. This closes the
  latency half of a gap Lesson 04 left open, and reframes the CDC trade: you
  are trading database load for latency at an exchange rate you set.

## Why this changes how the course should run

Six lessons argued from mechanism and primary sources; this one contradicted
the intuitive reading of a doc within an hour of starting a container. The
`redelivered` finding would never have arrived by reasoning, because the
reasoning was *already done* and had reached a comfortable wrong answer.

The runnable project should be promoted out of the scratchpad and into the
workspace, so later lessons start from a running pipeline rather than a blank
container. That converts Lesson 08 (poison messages, delivery limit, DLX) from
an argument into an experiment.

## Revisit when

The project is promoted and sharding is actually run. Per-aggregate order is
still the largest claim in the course with no observation behind it — the
two-relay experiment was deliberately scoped to `SKIP LOCKED` and says nothing
about order.
