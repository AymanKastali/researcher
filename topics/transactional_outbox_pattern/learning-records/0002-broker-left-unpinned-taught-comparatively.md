# Broker left unpinned, so Lesson 03 teaches all three comparatively

**Status:** superseded by
[0003-broker-pinned-to-rabbitmq.md](0003-broker-pinned-to-rabbitmq.md) on
2026-09-10, when Ayman pinned the broker. Kept because the comparative insight
below is still the reason Lesson 03 reads the way it does.

Lesson 02 ended by asking Ayman to name his broker — RabbitMQ, SQS or NATS —
because the dedup mechanics differ. He asked for the next lesson without
answering. Rather than block, Lesson 03 (2026-09-10) closed the RESOURCES gap
on all three and teaches the comparison.

## What this bought

Researching all three surfaced the insight the lesson is now built on, which a
single-broker lesson would have hidden: **every one of these mechanisms
deduplicates the publish, inside a time window, and none deduplicates
redelivery.** RabbitMQ has no core dedup; SQS FIFO gives five minutes; NATS
gives two. Seeing three windows side by side is what makes "the window is
smaller than your outage" obvious. One broker in isolation reads as a feature
you can lean on.

## Implications

- Do not re-ask for the broker as a blocker. It is now an *upgrade*: if Ayman
  names one, rewrite Lesson 03's broker table as a single concrete
  configuration and keep the comparison as a sidenote. The lesson footer
  already offers this.
- Interview framing favours the comparative version anyway — an interviewer may
  ask about whichever broker *they* run. Only switch to single-broker if the
  mission changes from interview prep to shipping a specific system.
- The same question will recur for Lesson 06 (dead-letter queues are also
  broker-specific). Expect to answer it the same way unless he pins it down.

## Untested

Whether the four-row comparison table exceeds working memory for a lesson whose
main point is the transaction boundary. If Lesson 03's recall practice shows the
broker details crowding out commit-then-ack, split the table into a reference
document and cut it from the lesson.
