# Broker pinned to RabbitMQ

Ayman answered "rabbitmq" on 2026-09-10, after Lesson 03 had already shipped
broker-comparatively. **This supersedes `0002-broker-left-unpinned-taught-
comparatively.md`**, whose stated plan — rewrite Lesson 03's four-row table as
one concrete configuration and demote the comparison to a sidenote — was
executed the same day.

## What changed in the material

Pinning the broker made Lesson 03 *shorter and sharper*, not longer, because
RabbitMQ offers no deduplication at all. The four-row "which broker dedups
what" table collapsed to a single quoted sentence putting the burden on the
consumer, and the space went to configuration that actually bites.

The genuinely new material the pin unlocked, none of which a comparative lesson
could have carried:

- **Unroutable messages are confirmed anyway.** The exchange confirms once it
  verifies the message routes nowhere, and `mandatory` defaults to false, so it
  is discarded. A relay without `mandatory=True` marks every row published
  while the broker bins the messages — an outbox reporting 100% delivery into
  nothing. This is now the lesson's headline trap and replaced a quiz question.
- Auto-ack is documented as unsafe; it converts at-least-once to at-most-once.
- Quorum queues, `x-delivery-count`, delivery-limit 20 by default since 4.0,
  and the fact that without a DLX the default outcome is silent deletion.

## Implications

- Lesson 02's `broker.publish` placeholder is now filled in by Lesson 03's
  aio-pika snippet. If Lesson 02 is ever revised, do not re-introduce a naive
  publish call — the confirm-and-mandatory pair is part of the pattern's
  correctness on this broker, not an implementation detail.
- Lesson 06 (operating it) gets concrete too: the DLQ discussion is now
  RabbitMQ dead-letter exchanges plus the delivery limit, not a generic survey.
- SQS and NATS stay in the material as one-sentence contrasts for interview
  breadth. Do not delete them; an interviewer may run either.

## Unverified

aio-pika's default for `mandatory` on `Exchange.publish()` could not be
confirmed from its docs. Lesson code sets it explicitly, which is the right
advice regardless — but do not state the default as fact.
