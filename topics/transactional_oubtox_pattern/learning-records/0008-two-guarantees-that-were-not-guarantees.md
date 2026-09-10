# Two guarantees that turned out not to be guarantees

Recorded 2026-09-10, working through "fix all caveats recorded — I want this
topic to be fully authentic and valid". The session split into measurement
against a throwaway harness (PostgreSQL 17.11 and a three-node RabbitMQ 4.3.5
cluster) and verification against primary sources. Two of the results are
corrections to things this course was teaching. The harness has since been
deleted at Ayman's instruction — the lessons and `RESOURCES.md` are the source
of truth for this topic, and a code tree is not one. Its captured output lives
in `evidence/`.

## Correction 1: single active consumer does not preserve order under retries

Lesson 05's ladder ended at *shard the relay, one queue per shard, single
active consumer*, and treated that as the per-aggregate ordering guarantee.
Measured over 460 events across 23 aggregates:

| Configuration | Ordering violations |
|---|---|
| Sharded, SAC, prefetch 20, no failures | 0 |
| The same, 5% of first deliveries requeued | **15, across 12 aggregates** |
| The same, prefetch 1 | 0 |

> Single active consumer guarantees **one consumer**. It does not guarantee
> **one message in flight**. Order needs both, and nothing in the RabbitMQ
> consumers or prefetch documentation says so.

The mechanism came from asking the broker a smaller question first. The docs
say only that *"any redelivery can change order"*. Publishing 1–5 into an
empty queue and rejecting message 1 once gives:

```
prefetch=1   ->  1  1* 2  3  4  5
prefetch=2   ->  1  2  1* 3  4  5
prefetch=5   ->  1  2  3  4  5  1*
```

The requeued message goes back to the **head**. What displaces it is the
consumer's own prefetch buffer — messages already handed out, which the broker
will not take back. So the displacement *is* the prefetch window, and prefetch
1 restores the guarantee. That prediction was made from the five-message probe
and then confirmed on the full pipeline, which is the strongest form this
workspace has produced.

## Correction 2: the delivery limit does not count a polite nack

Lesson 06 taught "let the broker count" — a poison message hits the
quorum-queue delivery limit and gets dead-lettered. Measured with
`x-delivery-limit: 3` and a DLX bound:

- consumer calls `message.nack(requeue=True)`: **12 deliveries and still
  going** when the run was stopped
- same message returned by closing the channel: **4 deliveries, then removed**

The docs agree, in a sentence easy to read past:

> *"Unlimited explicit returns (via `nack` or AMQP 1.0 `modify` with
> `delivery_failed=false`) are allowed without counting toward the delivery
> limit."*

The counter moves for *"`reject`, AMQP 1.0 `modify` with
`delivery_failed=true`, or channel termination with pending messages"*.

So the retry loop written by reflex — `except Exception: await
message.nack(requeue=True)` — is precisely the shape the delivery limit will
never end. `reject` and `nack` are not interchangeable, and the difference is
a liveness property, not a style choice.

**Unresolved:** in the same run the counted-out message left the queue and did
not appear on the bound dead-letter queue. Recorded as an open question in
Lesson 06 rather than smoothed over.

## What else closed, and how

Not everything needed a container. Roughly half the recorded caveats were
unread sources rather than unrun code:

- **RabbitMQ is not a Debezium Server sink.** The sink list has thirteen
  entries and RabbitMQ is not among them, which turns Lesson 04's hedged
  "check what your platform supports" into a decision.
- **debezium.io's 403 is routable.** The rendered site refuses the fetch tool;
  the AsciiDoc source in the `debezium/debezium` repo does not.
- **aio-pika defaults `mandatory=True`**, the opposite of the AMQP protocol
  default the lesson quotes. Set it explicitly anyway — the point is not
  relying on a client default for a durability property.
- **PostgreSQL has no built-in partition creation**, and for an outbox a
  missing partition fails the *business transaction*, not the relay.
- **`NOTIFY` is transactional**, which is what makes the doorbell safe.

## Why this changes how the course should run

Six lessons argued from mechanism. Lesson 07 ran the code. This session did
both, and the pattern in the two corrections is the same: **the design was
right and the operational detail underneath it was wrong.** Sharding and SAC
are correct; they are just not sufficient. The delivery limit is real; it just
does not see the call most people make. Neither error would have been caught by
more reasoning, because the reasoning was sound — the gap was between a
component's advertised purpose and its actual trigger condition.

The lesson for future sessions: when a doc states a guarantee, find the
sentence that says *when it applies*. Both corrections here were sitting in
plain text on pages this course had already cited.

## Revisit when

Failover is run — a quorum replica on all three nodes now exists and no
experiment kills the leader. And when the dead-letter hop is chased down; a
counted-out message vanishing instead of landing on a bound DLQ is either a
setup error or a real at-most-once loss, and the course should know which.
