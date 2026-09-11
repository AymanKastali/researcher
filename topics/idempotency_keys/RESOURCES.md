# Idempotency Keys Resources

Every source below was fetched and read on 2026-09-11. Where a lesson quotes
one, the quote was taken from the fetched text, not from memory.

## Knowledge

### Specifications

- [RFC 9110 §9.2.2 — Idempotent Methods][rfc9110]
  The normative definition, and the only *standards-track* text in this topic.
  Use for: what "idempotent" means precisely; the list (`PUT`, `DELETE`, and
  the safe methods); and — the highest-value paragraph — the rule that a client
  *"SHOULD NOT automatically retry a request with a non-idempotent method unless
  it has some means to know that the request semantics are actually idempotent,
  regardless of the method."* An idempotency key is how you buy that "means".
  Also note the caveat that idempotency *"only applies to what has been
  requested by the user"* — a server may still log each request separately.

- [draft-ietf-httpapi-idempotency-key-header-07 — The Idempotency-Key HTTP
  Header Field][draft] (Jena & Dalal, October 2025)
  The closest thing to a spec for the header itself. Use for: the header
  definition, the three enforcement cases (§2.6), the error status codes (§2.7:
  400, 422, 409), the *idempotency fingerprint* concept (§2.4), and the
  security guidance on composite lookup keys (§5).
  **Where it stops being trustworthy:** it is an expired Internet-Draft, not an
  RFC. It expired 18 April 2026 and the datatracker lists it "Expired &
  archived". Cite it as the industry's written-down convention — *never* as a
  standard. Its requirements are `SHOULD`, not `MUST`, almost throughout.
  It is also **not internally consistent**: §2.6 describes a duplicate as
  "idempotency key and fingerprint has been seen", which read as a lookup key
  makes §2.7's `422` case unreachable. See `learning-records/0002`.
  Plain-text revision 07 is the copy to quote: [`.txt`][draft-txt].

### Vendor documentation (the real-world examples)

- [Stripe API Reference — Idempotent requests][stripe-api]
  The reference implementation everyone copies. Use for: the 24-hour window,
  the 255-character limit, the rule that the *status code and body* of the
  first request are saved *"regardless of whether it succeeds or fails"*, the
  parameter-comparison rule, and the `Idempotent-Replayed: true` response
  header. Also the line worth quoting at an interviewer: *"All `POST` requests
  accept idempotency keys. Don't send idempotency keys in `GET` and `DELETE`
  requests because it has no effect."*

- [Stripe — Advanced error handling][stripe-errors]
  The retry semantics, and sharper than the reference page. Use for: the
  ambiguity argument (*"clients are usually left in a state where they don't
  know whether or not the server received the request"*), the `409 Conflict`
  definition, the distinction between errors cached by the idempotency layer
  and errors raised *before* it (rate limiting, auth, most validation), and
  `Stripe-Should-Retry`. The advice to treat a `500` as **indeterminate** is
  the most quotable sentence in the topic.
  The single most valuable passage in this topic is the reconciliation
  paragraph: *"While the idempotency-cached response to those requests won't
  change, we'll try to fire webhooks for any new objects created as part of
  Stripe's reconciliation."* No other source admits that the cached response
  can be permanently wrong, or that the repair must arrive out of band. It is
  the spine of Lesson 02's hardest section.

- [Amazon EC2 — Ensuring idempotency in API requests][aws]
  The same pattern under a different name, which is why it is here. Use for:
  `ClientToken` as a *request parameter* rather than a header; the
  `IdempotentParameterMismatch` error; and the unusually explicit treatment of
  **key scope** — EC2 keys are scoped Regionally or Zonally, so the same token
  legitimately launches two instances in two Regions.
  Promoted to the primary source for Lesson 03. It is the **only** document
  examined that treats scope as a published product decision with named modes
  rather than a security footnote, and the single most useful sentence in the
  topic for that purpose is the exception buried in its mismatch rule:
  parameters differing *"other than the Region or Availability Zone"* raise an
  error — which is the proof that Region is scope and not fingerprint. It also
  prices scope honestly: regional idempotency *"could fail"* if one Zone is
  unavailable, and they recommend the narrower zonal mode. See
  `learning-records/0003`.

- [Google AIP-155 — Request Identification][aip155]
  The third shape: `request_id` as a field in the request message, 36 ASCII
  characters, UUID recommended. Use for the one-line justification of
  replay-the-response: *"the client most likely did not receive the previous
  response."* Thin on failure cases — it does not address a reused id with
  different parameters.
  **Revised 2026-09-11:** its *Stale success responses* section is the one place
  any source admits that a replayed body need not be the original one — *"it is
  permissible to substitute the historical success response with a similar
  response that reflects more current data."* That contradicts the
  byte-identical replay taught from Stripe in Lessons 01–02, and the two are
  different contracts rather than one being wrong. See `learning-records/0004`.

### Engineering write-ups

- [Brandur Leach — Implementing Stripe-like Idempotency Keys in Postgres][brandur]
  (27 October 2017). The most detailed public account of the *implementation*,
  from someone who built Stripe's. Use for: the `idempotency_keys` table and
  its columns (`locked_at`, `recovery_point`, `request_params`,
  `response_code`, `response_body`); the vocabulary of **atomic phases**,
  **foreign state mutations** and **recovery points**; the reaper process; and
  the ~72-hour retention argument (*long enough that a Friday-night bug is
  still recoverable on Monday*).
  Promoted to the primary source for Lesson 04, which it carries almost alone —
  no specification or vendor page examined addresses what happens when the work
  inside the key's transaction cannot be rolled back. The sections that matter
  are "Foreign state mutations" through "Designing atomic phases", and "Murphy in
  action", which walks eight distinct failures one at a time and is the best
  interview rehearsal in the topic. Two passages have no counterpart anywhere
  else: the warning that emitting to Kafka only *feels* atomic (the dual-write
  problem, reached from the direction of a `POST` handler — see
  `learning-records/0005`), and the rule that indeterminate errors against a
  **non-idempotent** API *"will have to be marked as failed"*, which inverts the
  advice Stripe gives clients (`learning-records/0006`).
  **Caveats:** it is a blog post, not documentation, and it is from 2017 — the
  Postgres and Ruby specifics have aged even where the design has not. Its
  MongoDB example is specifically out of date: multi-document transactions
  arrived in 4.0 the following year, though the structural claim (no atomicity ⇒
  no atomic phase) stands.

- [Brandur Leach — Designing robust and predictable APIs with idempotency][stripe-blog]
  (Stripe blog, 22 February 2017). The conceptual companion. Thinner than it
  looks; the Postgres piece above supersedes it for most purposes.

## Wisdom (Communities)

Not yet raised with Ayman, and not proposed unprompted. Candidates when the
question is a design judgement rather than a fact:

- [IETF HTTP APIs working group (httpapi) mailing list][httpapi-wg] — where the
  draft above was argued over. The archive is the place to find out *why* the
  draft says `SHOULD` where you expected `MUST`.
- [r/ExperiencedDevs][reddit] — for "how did you scope/expire keys in
  practice", which no specification answers.

## Gaps

Deliberately recorded rather than filled:

- **No measured numbers anywhere in this topic.** Every window quoted (24
  hours, 72 hours) is a vendor's or an author's choice, not a derived one. Do
  not let them harden into recommendations.
- **No primary source on lock contention** for the claim step at volume.
  Brandur's `locked_at` design is argued from mechanism only.
- **No source covers the key's interaction with a load balancer or multiple
  application regions** beyond AWS's Regional/Zonal note. If Ayman asks "what
  if my two data centres have separate databases", the honest answer is that no
  source here settles it.
- **The draft's `Idempotency-Key` is a Structured Field String** (§2.1), which
  means the quotes in `Idempotency-Key: "8e03…"` are part of the syntax. No
  vendor examined here actually sends it that way — Stripe's own example omits
  the quotes. Worth flagging if precision ever matters.

[rfc9110]: https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2
[draft]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
[draft-txt]: https://www.ietf.org/archive/id/draft-ietf-httpapi-idempotency-key-header-07.txt
[stripe-api]: https://docs.stripe.com/api/idempotent_requests
[stripe-errors]: https://docs.stripe.com/error-low-level
[aws]: https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html
[aip155]: https://google.aip.dev/155
[brandur]: https://brandur.org/idempotency-keys
[stripe-blog]: https://stripe.com/blog/idempotency
[httpapi-wg]: https://mailarchive.ietf.org/arch/browse/httpapi/
[reddit]: https://www.reddit.com/r/ExperiencedDevs/
