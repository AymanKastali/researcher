# The fingerprint is a check after the lookup, not part of it

Found while writing Lesson 02 on 2026-09-11, by reading
`draft-ietf-httpapi-idempotency-key-header-07` in full rather than in summary.
This is recorded because it is a place where the specification, read literally,
produces a broken implementation — and because Lesson 01 happened to get it
right without arguing for it.

## The discrepancy

§2.6 defines the two enforcement cases in terms of the *pair*:

> First time request (idempotency key and fingerprint has not been seen)
> Duplicate request (idempotency key and fingerprint has been seen)

Read as a lookup key, that means indexing on `(caller, key, fingerprint)`. But
§2.2 says the key `MUST NOT` be reused with a different payload, and §2.7
prescribes `422` when it is. Those cannot both hold: if the fingerprint is in
the lookup, a reused key with a changed payload *misses*, claims a fresh row,
and executes a second operation. The `422` case becomes unreachable.

The resolution is that §2.6 is describing the *outcome* of the check, not the
index. Look up on `(caller, key)`; compare the fingerprint afterwards.

## Implications

- **Lesson 01's schema was already correct** — primary key `(user_id, key)`,
  `request_hash` as an ordinary column — but for an unstated reason. Lesson 02
  now states it, and uses the near-miss as the teaching moment. Prior knowledge
  that was accidentally right is worth converting into knowledge that is
  defensibly right.
- **Do not present the draft as internally consistent.** It already carries the
  caveat that it is expired and `SHOULD`-heavy; this adds that a literal reading
  of one section contradicts two others. That strengthens rather than weakens
  the topic's honesty convention.
- **This reading is mine, not a cited correction.** No source examined says the
  draft is ambiguous here. If Ayman pushes on it, the honest framing is "the
  two sections only reconcile one way, and here is the failure the other way
  produces" — an argument from mechanism, not authority.
- Fingerprint scope is wider than the body: Brandur stores `request_method` and
  `request_path` alongside `request_params`. A body-only fingerprint misses a
  key replayed against a different endpoint.
