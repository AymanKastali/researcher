# Deferring a foreign call turns it into a transactional outbox

Closed on 2026-09-11, while writing Lesson 04. Rewritten the same day to stand
on its own after the topic-independence rule (see
[[0001-what-this-topic-may-assume]]); the insight is unchanged, the framing is
no longer about a second course.

## The observation

Brandur's idempotency-key design defers the receipt email by inserting a row
into `staged_jobs` inside the atomic phase, justified as:

> because we're using a transactionally-staged job drain, we get a guarantee
> that the operation commits along with the rest of the transaction.

A separate process — he calls it *the enqueuer* — moves those rows to the real
queue after the transaction commits.

That construct has a name outside this article: the **transactional outbox**. A
table written in the same transaction as the business state, drained to its real
destination by a separate process after the commit. Brandur never uses the term,
which is exactly why it is worth writing down — recognising it means the reader
can go and find the substantial literature on the drain half, which this article
does not supply.

## The generalisation worth keeping

Both the idempotency key and the staged-jobs table answer one question:
**what do you do when a unit of work spans something your transaction cannot
roll back?**

The shared answer is *commit the record of intent before attempting the
irreversible thing*. The two mechanisms then differ in what they do with it:

- The staged row makes the irreversible thing **retryable** — it is still there
  after a crash, so a drain can try again.
- The idempotency key makes the retry **safe** — it gives the operation a name
  the far side also recognises, so the duplicate collapses instead of executing
  twice.

Neither is sufficient alone. A drain without a key duplicates; a key without a
durable record of intent loses the work. Lesson 04 needs both, which is why the
staged-jobs section sits after the phase machine rather than replacing it.

## Implications

- **Brandur's Kafka note is the strongest evidence in the lesson.** His warning
  that emitting to Kafka is *"tempting to treat… as part of atomic operations"*
  but is not, is the dual-write problem stated by someone who arrived at it from
  idempotency keys rather than from messaging. Two independent routes to the
  same conclusion are worth more than either alone.
- **Name the pattern, teach it in place.** Lesson 04 spends three sentences
  defining the transactional outbox where the staged-jobs table appears. That is
  the right depth here: enough that the term is usable in an interview, not so
  much that the lesson turns into a different lesson.
- **The drain is at-least-once and the lesson must say so**, or the reader walks
  away thinking staging the email guaranteed it is sent once.
