# Scope is a behavioural decision, not only a security control

Found while writing Lesson 03 on 2026-09-11, from the Amazon EC2 idempotency
page read in full. Recorded because the framing carried into this topic from
the draft — scope as a *security* recommendation — turns out to be the smaller
half of the idea, and the larger half is what an interviewer can actually
probe.

## What the sources say

The draft treats the composite lookup key purely as a defence, listed under
Security Considerations alongside injection:

> On the resource, implement a unique composite key as the idempotent cache
> lookup key. … combining the idempotency key sent by the client with other
> client specific attributes known only to the resource.

AWS treats the same column as a published product behaviour, with two named
modes (Regional and Zonal), and documents the consequence as intended:

> you can use the same request, including the same client token, in a different
> Region

The proof that Region is *scope* rather than *fingerprint* is the exception
inside their mismatch rule — parameters differing *"other than the Region or
Availability Zone"* raise `IdempotentParameterMismatch`.

## The generalisation

Every field of an incoming request is **scope**, **fingerprint**, or
**ignored**, and the same field can legitimately go in either of the first two:

- In the fingerprint → the same key with that field changed is a *key reuse*
  (`422` / `IdempotentParameterMismatch`).
- In the scope → the same key with that field changed is a *different
  operation*, and it executes.

So scope answers "what counts as the same request?", which is a product
question, not a security one. It happens to also be the access-control
boundary, which is why the two got conflated.

## Implications

- **Lesson 02's fingerprint material is incomplete without this.** The two
  concepts are a pair and should be taught as one decision with three buckets.
  The reference card now carries the three-bucket rule.
- **Scope has an availability price.** AWS recommends the *narrower* zonal
  scope because a regional one can fail when one Zone is unavailable. Wider
  scope = wider dependency. This is the answer to "why not scope globally?".
- **Scope has a time axis.** Stripe asks for keys unique *"within your account
  over the last 24 hours, at a minimum"* — account and window are two
  dimensions of one lookup, so Lesson 02's retention number is the temporal half
  of the scope rather than housekeeping. See [[0002-the-fingerprint-is-not-part-of-the-lookup-key]].
- **Which identity belongs in the scope column is unsettled.** No source
  examined chooses between account, user, organisation or API credential. The
  reasoning offered in Lesson 03 — scope on the boundary the *data* is drawn on,
  not on the credential, because credentials rotate and retries outlive them —
  is mine and is unsourced. If Ayman pushes, concede that immediately.
