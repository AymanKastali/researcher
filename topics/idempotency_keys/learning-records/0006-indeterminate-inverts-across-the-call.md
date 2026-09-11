# "Indeterminate" means retry on one side of a call and stop on the other

Noticed on 2026-09-11 while writing Lesson 04, by putting two sourced rules next
to each other. Neither source makes the comparison; the inversion is the
workspace's own reading and is flagged as such in the lesson.

## The two rules

**Stripe, to clients** (taught in Lesson 01, and the most quotable line in the
topic): a `500` or a timeout is *indeterminate* — the client cannot know whether
the server received the request — therefore **retry it with the same key**.

**Brandur, to callers of a non-idempotent API** (Lesson 04):

> Indeterminate errors like a connection reset or timeout will have to be marked
> as failed.

Same evidence — a timeout, no information — and the opposite instruction.

## Why both are right

The advice never depended on the error at all. It depended on a property of the
*far side*: whether it can absorb a duplicate.

| Far side accepts an idempotency key | Indeterminate means |
|---|---|
| Yes | Retry. The duplicate collapses. |
| No | Mark failed, escalate. A retry is a coin-flip between a lost operation and a doubled one. |

The only exception Brandur allows is an error that *"tell us explicitly that
it's okay to retry"* — which is exactly the job of Stripe's
`Stripe-Should-Retry` header from Lesson 02. **Ambiguity is not permission.**

## Implications

- **This is the actual argument for building idempotency keys**, and it is not
  the one the course opened with. Lesson 01 motivated keys by *your* client's
  retries. The stronger motivation is that every service which accepts a key
  deletes a permanently-errored state from somebody else's system. Brandur puts
  an exclamation mark on it: *"This is why you should implement idempotency
  and/or idempotency keys on all your services!"*
- **It reframes the course's own subject.** Lessons 01–03 teach how to be a
  server receiving a key. Lesson 04 is the first time the reader is the *client*
  sending one, and the rules they learned as a server apply to them unchanged —
  including that the outbound key must be derived from something stable, because
  a freshly generated one differs on the retry and buys nothing.
- **Open and unresolved:** no source examined says what to do when the far side
  is non-idempotent and the operation *must* happen. "Mark it failed and get a
  human" is the honest answer and is what the lesson says, but it is an
  admission rather than a design. If Ayman pushes, concede it.
