# Mission: Idempotency Keys (HTTP APIs)

## Why

Ayman wants to hold his own on idempotency keys under questioning — in
interviews and in API design reviews. That means deriving the mechanism from the
failure it exists for, walking the server's algorithm step by step without
notes, and defending the awkward cases (concurrent retry, same key different
payload, cached failures) rather than hand-waving them.

The boundary this topic covers is **client→server**: a caller sends a `POST`,
the response never arrives, and the caller has to decide whether to send it
again. Everything here is about what the server must do so that the answer is
always "yes, safely."

## Success looks like

- Can state the **core problem** in one sentence: a client that gets no
  response cannot distinguish a lost request from a lost response, so it must
  either risk a duplicate or risk a loss.
- Can explain why `POST` is the method that needs a key, quoting RFC 9110's
  definition of idempotent and its rule about automatic retries.
- Can walk the **server algorithm step by step** from memory — claim, execute,
  record, replay — and name the status code for each of the three duplicate
  cases (409, 422, and the replayed original).
- Can say *why the claim and the work must share one transaction*, and state the
  general form: a marker is only trustworthy if it commits with what it marks.
- Can name three real APIs and how each shapes the key differently: Stripe's
  `Idempotency-Key` header, AWS's `ClientToken` parameter, Google's
  `request_id` field.
- Can defend the operational choices under pressure: key scope, expiry window,
  what gets stored, and whether a failure response is cached.

## Constraints

- Interview-depth, **recall not recognition**. Format and teaching conventions
  are in `NOTES.md`.
- Illustrative code is **Python**; DDL stays SQL; HTTP exchanges stay HTTP.
- **No runnable project.** Claims are grounded in primary sources — the IETF
  draft, RFC 9110, and vendor documentation — not in a harness built here.
- **This topic stands alone.** Assume no other topic in this repo has been read.
  Anything the lessons need — the dual-write problem, at-least-once delivery,
  the single-transaction boundary — is explained where it is used, not
  cross-referenced.

## Out of scope

- Broker-side deduplication. This topic is the client→server boundary; what a
  message consumer does with a duplicate is a different mechanism.
- Distributed locking as a general topic. The key's claim step touches it; the
  lesson stops at what that step needs.
- Exactly-once semantics as a theoretical subject (FLP, consensus). The
  practical version is the one being taught.
