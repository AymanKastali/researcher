# Network Idempotency Resources

Sources for this topic, split by weight. A specification or a vendor's own
documentation is normative for that vendor's behaviour; practitioner writing is
argument and experience and is labelled as such, here and on every page that
quotes it. All knowledge entries were fetched and read on 11 September 2026 while
writing `docs/research/idempotency-keys.md`; community entries were verified on
12 September 2026.

## Knowledge

### Specifications and standards

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
  Fielding, Nottingham & Reschke (eds.), IETF, STD 97, June 2022. The normative
  definition the whole subject rests on. Use for: §9.2.1 safe methods, §9.2.2 the
  definition of idempotent and the automatic-retry rules, §9.3.3 why POST promises
  nothing, §15.5.10 `409`, §15.5.21 `422`.
- [draft-ietf-httpapi-idempotency-key-header-07](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07)
  Jena & Dalal, IETF HTTPAPI WG, Standards Track **Internet-Draft**, 15 October
  2025, expires 18 April 2026. **Not an RFC** — its own boilerplate says to cite
  it only as "work in progress". Use for: header syntax, uniqueness, the
  idempotency fingerprint, client and resource responsibilities, and the
  400/422/409 error scenarios.
- [AIP-155: Request identification](https://google.aip.dev/155)
  Google API Improvement Proposals, state "Approved". Use for: the vendor-neutral
  RPC formulation, the MUST/SHOULD bullets on `request_id`, the "must not be a
  field on resources themselves" constraint, and the stale-success escape hatch
  that licenses returning current state instead of the stored response.
- [PostgreSQL 17 — `INSERT`](https://www.postgresql.org/docs/17/sql-insert.html)
  and [Transaction Isolation](https://www.postgresql.org/docs/17/transaction-iso.html)
  Use for: the `ON CONFLICT` atomicity guarantee "even under high concurrency",
  and the definition of `SERIALIZABLE`. These are the primary-source basis for
  both good answers to the race at the claim.

### Papers and textbooks

- [_Implementing Remote Procedure Calls_](http://www.bitsavers.org/pdf/xerox/parc/techReports/CSL-83-7_Implementing_Remote_Procedure_Calls.pdf)
  Birrell & Nelson, Xerox PARC CSL-83-7, December 1983; ACM TOCS 2(1), 1984.
  Use for: "either once or not at all — the user is not told which", and the
  **call identifier**, which is the idempotency key forty years early.
  **The single most important reading in this topic.**
- [_End-to-End Arguments in System Design_](https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.txt)
  Saltzer, Reed & Clark, ACM TOCS 2(4), November 1984. Use for: why duplicate
  suppression has to happen at the application and cannot be delegated downward —
  the argument that makes the key the client's to generate.
- [_Distributed Systems_, 4th ed.](https://www.distributed-systems.net/index.php/books/ds4/)
  Tanenbaum & van Steen, 2023. Free PDF via a personalised email link; the
  companion slide set (`allslides.zip`) downloads without a form. Use for:
  at-least-once vs at-most-once, and the six M/P/C orderings showing transparent
  server recovery is impossible. Chapter 8 is the relevant one.
  **Caveat:** this workspace quotes the author's slides, not the book body.
- [_Linear Associative Algebra_](https://archive.org/details/linearassocalgeb00pierrich)
  Benjamin Peirce; lithographed 1870, printed 1882, §25 p. 8. Use for: the
  original definition of "idempotent", a century before computing.

### First-party vendor documentation

- [Stripe — Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
  and [Advanced error handling](https://docs.stripe.com/error-low-level)
  Use for: key generation and the 255-character limit, storing status code and
  body "regardless of whether it succeeds or fails", the ≥24-hour pruning
  language, `Idempotent-Replayed`, `Stripe-Should-Retry`, and the rule that
  results are saved only once endpoint execution begins. The most complete public
  vendor account.
- [Adyen — API idempotency](https://docs.adyen.com/development-resources/api-idempotency/)
  Use for: the 7–14 day validity range, company-account and per-region scope,
  error 704 returned as `422` **or** `409`, and the `transient-error` header.
- [PayPal — Idempotency](https://developer.paypal.com/api/rest/reference/idempotency/)
  Use for: `PayPal-Request-Id`, per-API-call-type scope, and the contrarian
  choice to return current status rather than the original response.
- [AWS — EC2 API idempotency](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Run_Instance_Idempotency.html)
  Use for: `IdempotentParameterMismatch`, and **regional vs zonal** scope — the
  clearest published statement that retrying into another region is not idempotent.
- [AWS — DynamoDB items and attributes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html)
  and [`PutItem`](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_PutItem.html)
  Use for: conditional writes, `attribute_not_exists` as the insert-if-absent
  idiom, and `ConditionalCheckFailedException`.
- [Powertools for AWS Lambda (Python) — Idempotency](https://docs.powertools.aws.dev/lambda/python/latest/utilities/idempotency/)
  Use for: a complete, readable first-party reference implementation — the
  three-clause condition expression, the record states, the 1-hour default
  expiry, and the in-progress lease.
- [Redis — `SET`](https://redis.io/docs/latest/commands/set/) and
  [Distributed Locks with Redis](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)
  Use for: `NX` semantics, and the Redlock page's own "Disclaimer about
  consistency" conceding that fencing tokens should be implemented.
- [Apache Kafka — Message Delivery Semantics](https://kafka.apache.org/documentation/#semantics)
  Use for: the three delivery semantics stated plainly, the "read the fine print"
  warning on exactly-once claims, and producer ID + sequence number as an
  idempotency key by another name.

### Practitioner writing

Argued from experience rather than normative. Often more detailed than the
specifications, but a claim here does not carry a specification's weight.

- [Implementing Stripe-like Idempotency Keys in Postgres](https://brandur.org/idempotency-keys)
  Brandur Leach, 27 October 2017. The most detailed public account of the
  mechanism. Use for: foreign state mutations, atomic phases, recovery points, a
  concrete key-record schema, and the ~72-hour retention argument.
- [Designing robust and predictable APIs with idempotency](https://stripe.com/blog/idempotency)
  Brandur Leach, Stripe blog, 22 February 2017. Use for: the taxonomy of network
  failures, and exponential backoff, jitter and the thundering herd.
- [How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
  Martin Kleppmann, 8 February 2016. Use for: efficiency versus correctness
  locks, why a lease can expire while its holder still runs, and fencing tokens.
- [Is Redlock safe?](http://antirez.com/news/101)
  Salvatore Sanfilippo, February 2016. Use for: the counter-case. Read it
  directly after Kleppmann or not at all — the value is in the disagreement.

## Wisdom (Communities)

- [IETF HTTPAPI Working Group](https://datatracker.ietf.org/wg/httpapi/about/)
  The group actually standardising the `Idempotency-Key` header. Mailing list
  `httpapi@ietf.org` ([subscribe](https://www.ietf.org/mailman/listinfo/httpapi),
  [archive](https://mailarchive.ietf.org/arch/browse/httpapi/)), plus a
  [Zulip stream](https://zulip.ietf.org/#narrow/stream/httpapi) and a
  [GitHub organisation](https://github.com/ietf-wg-httpapi). Use for: watching the
  draft move, and reading the arguments behind clauses that look arbitrary. The
  archive is worth reading even if you never post.
- [Papers We Love](https://paperswelove.org/)
  A repository of computer science papers and a community that reads them, with
  more than fifty local chapters worldwide. Both Birrell & Nelson and the
  end-to-end paper are exactly its staple material. Use for: reading the founding
  papers with other people rather than alone, which is where the wisdom in this
  topic actually lives.
- [Lobsters — `distributed` tag](https://lobste.rs/t/distributed)
  Small, high-signal, heavily technical aggregator. Use for: following the
  argument when a new idempotency or consensus post circulates.
  **Note:** membership is invitation-only; the tag is readable without an account.

Record here if the learner opts out of communities — no preference has been
stated either way yet.

## Gaps

Areas the mission touches where the public record is thin. These are gaps in the
sources, not omissions from this workspace.

- **No vendor documents how long an in-flight claim may last** before it is
  treated as stale. Powertools ties it to the Lambda timeout and Brandur uses a
  configurable constant; Stripe, Adyen, PayPal and Square state no figure.
- **The EC2 client-token retention window is undocumented.** DynamoDB's ten
  minutes is stated on two pages; EC2's equivalent appears nowhere. Any figure
  circulating for it is unsourced.
- **Square documents nothing on the concurrent case** — neither the
  `CreatePayment` reference nor the idempotency guide addresses a retry arriving
  while the first request is still running. Its retention window is likewise
  unpublished.
- **No textbook treatment was quotable in-session.** Kleppmann's _Designing
  Data-Intensive Applications_ and Bernstein & Newcomer on transaction processing
  were both wanted and neither had a verifiable public copy to quote. If a copy
  becomes available, the concurrency lessons should be revisited against it.
