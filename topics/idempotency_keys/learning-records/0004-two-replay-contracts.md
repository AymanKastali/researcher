# "Replay the stored response" is one contract, and not the only one

Found while writing Lesson 03 on 2026-09-11, in AIP-155's *Stale success
responses* section. This revises material already delivered: Lessons 01 and 02
both state the rule as *replay the stored status code and body*, presented as
though it were the only option.

## The discrepancy

**Stripe promises the bytes.** The stored status code and body are returned
unchanged, and `Idempotent-Replayed: true` marks the replay so a client can
tell.

**Google explicitly permits the current state instead:**

> In some unusual situations, it may not be possible to return an identical
> success response. … it is permissible to substitute the historical success
> response with a similar response that reflects more current data.

AWS lands in the same place without framing it as a contract at all — *"the
result might contain updated information, such as the current creation
status."*

So there are two promises in circulation:

1. **Byte-identical replay** — the second call returns exactly what the first
   did, whatever has happened since.
2. **Idempotent effect** — the second call performs no further action, but the
   body may reflect the world as it is now.

Both satisfy "the operation happened once". Only the first satisfies a client
that diffs the replay against its original.

## Implications

- **Lessons 01 and 02 are not wrong, but they are narrower than they sound.**
  They teach contract (1) — which is the right default, and is what the stored
  `response_body` column implements. Lesson 03 names the choice rather than
  going back to amend them.
- **It sharpens the `500` material in Lesson 02.** Under contract (1) a cached
  `500` is frozen and can be permanently wrong, which is why the repair must
  arrive by webhook. Under contract (2) that specific failure mode is at least
  partially avoidable, because the body is recomputed. No source makes this
  connection; it is an inference and should be offered as one.
- **The question to ask of any API, including one being designed in an
  interview:** on a duplicate, do you promise the old bytes or the current
  truth? Not noticing there was a choice is the tell.
- `RESOURCES.md`'s note on AIP-155 called it *"thin on failure cases"*. Still
  true for the reused-id-with-different-parameters case, but it is the only
  source examined that addresses the staleness of a replayed body, so the entry
  has been amended rather than left to imply the page has nothing.
