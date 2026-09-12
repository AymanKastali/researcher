# Network Idempotency and Idempotency Keys

A study guide, built from primary sources.

**Scope.** This is an educational deep dive for someone studying backend system
design. It is not an implementation guide for a particular feature or framework.
It moves from the algebraic origin of the word "idempotent", through what HTTP
actually promises, to the architectural lifecycle of an idempotency key, and
finally to the hard part: what happens when two requests carrying the same key
arrive at the same instant.

**Sourcing.** Every substantive claim below is tied to a source that was fetched
and read while writing this document. Definitions and normative statements are
quoted rather than paraphrased. Specifications and first-party documentation are
kept visibly separate from practitioner writing, and where two authorities
disagree — and they do, repeatedly, on retention windows and on status codes —
both are quoted rather than reconciled. Anything that could not be verified is
marked as such, here and in [§6](#6-what-could-not-be-verified).

---

## Contents

1. [Core Concepts](#1-core-concepts)
2. [The Lifecycle](#2-the-lifecycle)
3. [Concurrency and the Distributed Lock Problem](#3-concurrency-and-the-distributed-lock-problem)
4. [Deep-Dive Edge Cases](#4-deep-dive-edge-cases)
5. [Sources](#5-sources)
6. [What could not be verified](#6-what-could-not-be-verified)

---

## 1. Core Concepts

### 1.1 The algebraic origin

The word is older than computing by a century. It was coined by Benjamin Peirce,
Perkins Professor of Astronomy and Mathematics at Harvard, in *Linear Associative
Algebra*, to name a class of expressions in a hypercomplex algebra:

> 25. When an expression raised to the square or any higher power vanishes, it
> may be called nilpotent; but when, raised to a square or higher power, it gives
> itself as the result, it may be called idempotent.
>
> The defining equation of nilpotent and idempotent expressions are respectively
> Aⁿ = 0, and Aⁿ = A; but with reference to idempotent expressions, it will
> always be assumed that they are of the form
>
> A² = A,
>
> unless it be otherwise distinctly stated.

— Benjamin Peirce, *Linear Associative Algebra*, §25, p. 8. Quoted from the 1882
D. Van Nostrand edition, [scanned at the Internet
Archive](https://archive.org/details/linearassocalgeb00pierrich).

Two things are worth pinning down about that citation, because the "1870"
attribution is usually passed around without evidence. The same 1882 volume says
in its preface:

> Lithographed copies of this book were distributed by Professor Peirce among his
> friends in 1870. The present issue consists of separate copies extracted from
> The American Journal of Mathematics, where the work has at length been
> published.
>
> The body of the text has been printed directly from the lithograph with only
> slight verbal changes.

So: the work dates from **1870**, circulated privately as a lithograph; the
printed text quoted above is that lithograph "with only slight verbal changes",
issued as an extract from *The American Journal of Mathematics* and reprinted by
Van Nostrand in 1882. The 1870 lithograph itself is scanned at the Internet
Archive too, but as handwritten facsimile its OCR is unusable, so the wording
above is verified against the 1882 printing rather than the 1870 original.

Note also what Peirce is *not* saying. He is defining a property of an
**element** under multiplication (`A² = A`), not of a function. The form modern
programmers recite —

> f(f(x)) = f(x)

— is the same idea transposed to function composition: applying `f` to an
already-`f`'d value changes nothing further. `abs()`, `sorted()`, `max(x, 5)` and
`set()` are idempotent in this sense. `append()` and `x += 1` are not.

### 1.2 Idempotence of a function vs. idempotence of an effect

This is the distinction the rest of the document turns on, so it is worth
labouring.

**Idempotence of a function** is a property of a pure mapping from input to
output. It is checkable by inspection, it holds for all time, and it involves no
world outside the function.

**Idempotence of an effect over a network** is a property of a *system's state*
after a *message* is processed, possibly more than once, by a *remote party*,
across a channel that can lose, delay, duplicate and reorder. Nothing about it is
checkable by inspection. It is a property you have to *engineer*.

An analogy for each, with the caveat that neither analogy is the definition — the
definitions are quoted above and in §1.3.

- **A light switch is idempotent.** "Set the switch to `on`" leaves the room lit,
  whether you do it once or ten times. Flipping to `on` an already-`on` switch
  changes nothing. This is the function sense: the operation is *absolute*, it
  names a destination state rather than a delta. This is why HTTP `PUT` (replace
  the resource with this representation) is idempotent and `PATCH` (apply this
  change) generally is not.
- **A doorbell is not idempotent.** Each press produces another ring. The
  operation is a *delta*, not a destination. "Charge this card $20" is a
  doorbell.
- **An elevator call button is idempotent in effect, but only because someone
  built it that way.** The button is a doorbell physically — you can press it
  repeatedly — but the elevator controller keeps a *record* that a call for this
  floor in this direction is already outstanding, and drops the duplicate. The
  lamp stays lit; nothing new is scheduled. That record is the idempotency key.

The elevator is the accurate analogy for what this document is about. An
idempotency key does not make a non-idempotent operation idempotent. It adds a
**deduplication record** in front of it, and the record is what makes the
*observable effect* idempotent while the underlying operation stays exactly as
non-idempotent as it always was.

### 1.3 What HTTP actually promises

RFC 9110 is the current definition of HTTP semantics — an Internet Standard
(STD 97) that obsoletes RFC 7231 among others.

**Safe methods** ([RFC 9110
§9.2.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.1)):

> Request methods are considered "safe" if their defined semantics are
> essentially read-only; i.e., the client does not request, and does not expect,
> any state change on the origin server as a result of applying a safe method to
> a target resource. Likewise, reasonable use of a safe method is not expected to
> cause any harm, loss of property, or unusual burden on the origin server.
>
> [...]
>
> Of the request methods defined by this specification, the GET, HEAD, OPTIONS,
> and TRACE methods are defined to be safe.

**Idempotent methods** ([RFC 9110
§9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)). This is the
central definition of the whole subject, and the second sentence is the one
almost every vendor's documentation is quoting or paraphrasing:

> A request method is considered "idempotent" if the intended effect on the
> server of multiple identical requests with that method is the same as the
> effect for a single such request. Of the request methods defined by this
> specification, PUT, DELETE, and safe request methods are idempotent.

Three consequences fall straight out of that wording.

**(a) Safety and idempotence are different axes.** Every safe method is
idempotent, because a method that changes nothing trivially changes nothing twice
over. The converse fails: `DELETE` is idempotent but emphatically not safe. Put
another way, safe ⊂ idempotent.

| Method  | Safe | Idempotent | Source |
| --- | --- | --- | --- |
| GET     | yes | yes | [§9.2.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.1), [§9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2) |
| HEAD    | yes | yes | as above |
| OPTIONS | yes | yes | as above |
| TRACE   | yes | yes | as above |
| PUT     | no  | yes | [§9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2) |
| DELETE  | no  | yes | [§9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2) |
| POST    | no  | no  | not listed in [§9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2) |
| PATCH   | no  | no  | not listed in [§9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2); PATCH is defined in [RFC 5789](https://www.rfc-editor.org/rfc/rfc5789) |

**(b) The caveat that matters most: it is about the *intended effect on the
server*, not the response the client gets.** RFC 9110 is explicit that the
response may legitimately differ between the first request and the retry:

> Idempotent methods are distinguished because the request can be repeated
> automatically if a communication failure occurs before the client is able to
> read the server's response. For example, if a client sends a PUT request and
> the underlying connection is closed before any response is received, then the
> client can establish a new connection and retry the idempotent request. It
> knows that repeating the request will have the same intended effect, even if
> the original request succeeded, though the response might differ.

The classic demonstration is `DELETE`. `DELETE /orders/7` returns `204 No
Content` the first time and `404 Not Found` the second. The *responses* differ.
The *intended effect on the server* — that order 7 not exist — is identical. The
method is idempotent. A reader who defines idempotence as "returns the same
response" will conclude, wrongly, that `DELETE` is not idempotent.

The spec also licenses side effects that are not part of what was requested:

> Like the definition of safe, the idempotent property only applies to what has
> been requested by the user; a server is free to log each request separately,
> retain a revision control history, or implement other non-idempotent side
> effects for each idempotent request.

**(c) Idempotence is what licenses automatic retry — and its absence is what
forbids it.** RFC 9110 §9.2.2 continues:

> A client SHOULD NOT automatically retry a request with a non-idempotent method
> unless it has some means to know that the request semantics are actually
> idempotent, regardless of the method, or some means to detect that the original
> request was never applied.

and, for intermediaries:

> A proxy MUST NOT automatically retry non-idempotent requests. A client SHOULD
> NOT automatically retry a failed automatic retry.

That "unless it has some means to know that the request semantics are actually
idempotent, regardless of the method" is, in one clause, the entire justification
for the `Idempotency-Key` header. The header is the means.

**Why POST is not idempotent.** Not because of anything about tunnels or bodies,
but because [RFC 9110
§9.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.3) declines to
constrain what it does at all:

> The POST method requests that the target resource process the representation
> enclosed in the request according to the resource's own specific semantics.

The semantics are the resource's, not the method's. Because HTTP does not know
what a `POST` means, it cannot promise that doing it twice equals doing it once.
`PUT` and `DELETE` *can* be promised idempotent precisely because HTTP does
define what they mean, and both definitions are absolute rather than relative:
`PUT` names a destination state, `DELETE` names an absence. `POST` names nothing.

RFC 9110 even acknowledges that clients cheat here, and disapproves:

> Some clients take a riskier approach and attempt to guess when an automatic
> retry is possible. For example, a client might automatically retry a POST
> request if the underlying transport connection closed before any part of a
> response is received, particularly if an idle persistent connection was used.

### 1.4 Why method semantics alone are not enough

Suppose you obey RFC 9110 perfectly. You still have a problem, and it is not a
problem about HTTP. It is a problem about distributed systems, and it was
described precisely in 1983.

#### The ambiguous failure

Birrell and Nelson, describing the guarantees of the Cedar RPC system at Xerox
PARC, state the limit of what any request/response protocol can offer:

> It is this level of the RPC package that defines what semantics and guarantees
> we give for calls. We guarantee that if the call returns to the user then the
> procedure in the server has been invoked precisely once. Otherwise, an
> exception is reported to the user and the procedure will have been invoked
> either once or not at all — the user is not told which. If an exception is
> reported, the user does not know whether the server has crashed or whether
> there is a problem in the communication network.

— Andrew D. Birrell and Bruce Jay Nelson, *Implementing Remote Procedure Calls*,
Xerox PARC technical report [CSL-83-7, December
1983](http://www.bitsavers.org/pdf/xerox/parc/techReports/CSL-83-7_Implementing_Remote_Procedure_Calls.pdf),
p. 11. Published as ACM *Transactions on Computer Systems* 2(1), February 1984,
pp. 39–59.

"Either once or not at all — the user is not told which" is the whole problem in
nine words. This is the **ambiguous failure**, and no amount of correct HTTP
method selection removes it, because it is a property of the channel, not the
verb.

Maarten van Steen's companion material for *Distributed Systems* (4th ed.) makes
the same point about lost replies:

> The real issue
>
> What the client notices, is that it is not getting an answer. However, it
> cannot decide whether this is caused by a lost request, a crashed server, or a
> lost response.

— Tanenbaum & van Steen, *Distributed Systems*, 4th ed., Chapter 8 (Fault
Tolerance), slide 55, from the author-published slide set at
[distributed-systems.net](https://www.distributed-systems.net/index.php/books/ds4/).

And the same source states why *transparent* recovery is not merely hard but
impossible. Consider a server asked to update a document, with three events: `M`
(send the completion message), `P` (complete the processing), `C` (crash). The
slide enumerates the orderings —

> 1. M → P → C: Crash after reporting completion.
> 2. M → C → P: Crash after reporting completion, but before the update.
> 3. P → M → C: Crash after reporting completion, and after the update.
> 4. P → C(→ M): Update took place, and then a crash.
> 5. C(→ P → M): Crash before doing anything
> 6. C(→ M → P): Crash before doing anything

— under the heading "Why fully transparent server recovery is impossible". From
the client's side, cases 2 and 4 are indistinguishable from each other and from a
lost reply, yet in one the update happened and in the other it did not.

#### The three delivery semantics

Because the failure is ambiguous, a client must choose a policy, and the choice
is a trilemma. The Apache Kafka documentation states the three options in their
standard form:

> * *At most once* — Messages may be lost but are never redelivered.
> * *At least once* — Messages are never lost but may be redelivered.
> * *Exactly once* — Each message is processed once and only once.

— [Apache Kafka documentation, "Message Delivery
Semantics"](https://kafka.apache.org/documentation/#semantics), quoted from the
docs source at
[`docs/design/design.md`](https://github.com/apache/kafka/blob/trunk/docs/design/design.md).

Van Steen's slides give the RPC-side formulation of the first two:

> * At-least-once-semantics: The server guarantees it will carry out an operation
>   at least once, no matter what.
> * At-most-once-semantics: The server guarantees it will carry out an operation
>   at most once.

The engineering content of this trilemma is simple and unforgiving:

- **Don't retry** → at-most-once. You never double-charge, but you silently drop
  work whenever the network hiccups.
- **Retry** → at-least-once. You never drop work, but you double-charge whenever
  a response is lost rather than a request.
- **Exactly-once** is not a third delivery option you can select. Kafka's own
  documentation is unusually blunt about this:

> Many systems claim to provide "exactly-once" delivery semantics, but it is
> important to read the fine print, because sometimes these claims are misleading
> (i.e. they don't translate to the case where consumers or producers can fail,
> cases where there are multiple consumer processes, or cases where data written
> to disk can be lost).

The resolution, in every system that achieves it, is the same: **retry
(at-least-once delivery) plus deduplication at the receiver (so that the
*effect* occurs once)**. Kafka does exactly this, and describes the mechanism in
terms that should look extremely familiar:

> If a producer attempts to publish a message and experiences a network error, it
> cannot be sure if this error happened before or after the message was
> committed. This is similar to the semantics of inserting into a database table
> with an autogenerated key.
>
> Prior to 0.11.0.0, if a producer failed to receive a response indicating that a
> message was committed, it had little choice but to resend the message. This
> provides at-least-once delivery semantics since the message may be written to
> the log again during resending if the original request had in fact succeeded.
> Since 0.11.0.0, the Kafka producer also supports an idempotent delivery option
> which guarantees that resending will not result in duplicate entries in the
> log. To achieve this, the broker assigns each producer an ID and deduplicates
> messages using a sequence number that is sent by the producer along with every
> message.

A producer ID plus a sequence number, kept in a table at the receiver so
duplicates can be dropped. That is an idempotency key.

So did Birrell and Nelson's RPC, forty years earlier — their **call identifier**
is the direct ancestor of the header:

> The call identifier serves two purposes. It allows the caller to determine that
> the result packet is truly the result of his current call (not, for example, a
> much delayed result of some previous call), and it allows the callee to
> eliminate duplicate call packets (caused by retransmissions, for example). The
> call identifier consists of the calling machine identifier (which is permanent
> and globally unique), a machine-relative identifier of the calling process, and
> a sequence number.

and the deduplication table, including its expiry policy, is described in the
next paragraph:

> The RPCRuntime on a callee machine maintains a table giving the sequence number
> of the last call invoked by each calling activity. When a call packet is
> received, its call identifier is looked up in this table. The call packet can
> be discarded as a duplicate (possibly after acknowledgement) unless its
> sequence number is greater than that given in this table.

> If a connection is idle, the server machine may discard its state information
> after an interval, when there is no longer any danger of receiving retransmitted
> call packets (say, after five minutes), and it can do so without interacting
> with the caller machine.

Everything in §2 and §4 of this document is a re-derivation of those two
paragraphs for HTTP.

#### Why the key has to come from the client

The last piece of theory is the end-to-end argument, which answers the question
"couldn't the network layer just suppress duplicates for me?" with a firm no.
Saltzer, Reed and Clark:

> A property of some communication network designs is that a message or a part of
> a message may be delivered twice, typically as a result of time-out-triggered
> failure detection and retry mechanisms operating within the network. The
> network can provide the function of watching for and suppressing any such
> duplicate messages, or it can simply deliver them. One might expect that an
> application would find it very troublesome to cope with a network that may
> deliver the same message twice; indeed it is troublesome. Unfortunately, even
> if the network suppresses duplicates, the application itself may accidentally
> originate duplicate requests, in its own failure/retry procedures. These
> application level duplications look like different messages to the
> communication system, so it cannot suppress them; suppression must be
> accomplished by the application itself with knowledge of how to detect its own
> duplicates.

— J. H. Saltzer, D. P. Reed and D. D. Clark, ["End-to-End Arguments in System
Design"](https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.txt), ACM
*Transactions on Computer Systems* 2(4), November 1984, pp. 277–288; revised from
the Second International Conference on Distributed Computing Systems, Paris,
1981.

They then state the conclusion that makes the key the *client's* to generate:

> Thus the end-to-end argument again: if the application level has to have a
> duplicate-suppressing mechanism anyway, that mechanism can also suppress any
> duplicates generated inside the communication network, so the function can be
> omitted from that lower level.

TCP already deduplicates *segments*. It cannot deduplicate *intentions*. Only the
client knows that the `POST /charges` it is sending now is a retry of the one it
sent 30 seconds ago rather than a genuine second charge — the two are byte-identical
and the network has no way to tell them apart. So the client must say so, and the
way it says so is by attaching a stable identifier it chose before the first
attempt.

### 1.5 The `Idempotency-Key` header

The header is being standardised, but **is not yet an RFC**. The current revision
is
[`draft-ietf-httpapi-idempotency-key-header-07`](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07),
Jena & Dalal, IETF HTTPAPI Working Group, Standards Track, dated 15 October 2025
and expiring 18 April 2026. Its own boilerplate insists on how it should be
cited:

> Internet-Drafts are draft documents valid for a maximum of six months and may
> be updated, replaced, or obsoleted by other documents at any time. It is
> inappropriate to use Internet-Drafts as reference material or to cite them
> other than as "work in progress."

Treat everything in this subsection as work in progress. Real deployments — every
one of them older than the draft — differ from it in detail, as §3 and §4 show.

**Definition and syntax** (§2, §2.1):

> An idempotency key is a unique value generated by the client which the resource
> uses to recognize subsequent retries of the same request. The Idempotency-Key
> HTTP request header field carries this value.

> Idempotency-Key is an Item Structured Header [RFC8941]. Its value MUST be a
> String (Section 3.3.3 of [RFC8941]).

Being a Structured Field String means the value is **quoted** on the wire:

```
Idempotency-Key: "8e03978e-40d5-43e8-bc93-6894a57f9324"
```

That is the draft's own example (§2.2, §6). It is worth flagging that almost no
production deployment does this — Stripe's documented example is
`Idempotency-Key: KG5LxwFBepaKHyUD`, unquoted — which is one of several places
where the draft is describing where the working group wants to go rather than
where the industry is.

**Uniqueness** (§2.2):

> The idempotency key MUST be unique and MUST NOT be reused with another request
> with a different request payload.
>
> Uniqueness of the key MUST be defined by the resource owner and MUST be
> implemented by the clients of the resource. It is RECOMMENDED that a UUID
> [RFC4122] or a similar random identifier be used as an idempotency key.

**Expiry** (§2.3) — note how little the draft commits to:

> The resource MAY require time based idempotency keys to be able to purge or
> delete a key upon its expiry. The resource SHOULD define such expiration policy
> and publish it in the documentation.

**The idempotency fingerprint** (§2.4). This is the mechanism for detecting "same
key, different request", and the draft leaves the algorithm open:

> An idempotency fingerprint MAY be used in conjunction with an idempotency key
> to determine the uniqueness of a request. Such a fingerprint is generated from
> request payload data by the resource. An idempotency fingerprint generation
> algorithm MAY use one of the following or similar approaches to create a
> fingerprint.
>
> * Checksum of the entire request payload.
> * Checksum of selected element(s) in the request payload.
> * Field value match for each field in the request payload.
> * Field value match for selected element(s) in the request payload.
> * Request digest/signature.

Two properties of that list are worth noticing. The fingerprint is generated **by
the resource**, not the client — the client never sends it. And because it MAY be
"selected element(s)" rather than the whole payload, two implementations can
legitimately disagree about whether a given retry is "the same request".

**Client responsibilities** (§2.5.1):

> Clients of HTTP API requiring idempotency SHOULD understand the idempotency
> related requirements as published by the server and use appropriate algorithm
> to generate idempotency keys.
>
> Clients MAY choose to send an Idempotency-Key field with any valid value to
> indicate the user's intent is to only perform this action once. Without a
> priori knowledge, a general client cannot assume the server will respect this
> request.

**Resource responsibilities** (§2.5.2):

> Resources MUST publish a idempotency related specification. This specification
> MUST include expiration related policy if applicable. A resource is responsible
> for managing the lifecycle of the idempotency key.
>
> For each request, a server SHOULD:
>
> * Identify idempotency key from the HTTP Idempotency-Key request header field.
> * Generate idempotency fingerprint if required.
> * Enforce idempotency (see below)

**Enforcement** (§2.6) — the three-way branch that §2 of this document expands
into a lifecycle:

> * First time request (idempotency key and fingerprint has not been seen)
>
>   The resource SHOULD process the request normally and respond with an
>   appropriate response and status code.
>
> * Duplicate request (idempotency key and fingerprint has been seen)
>
>   Retry
>
>   The request was retried after the original request completed. The resource
>   SHOULD respond with the result of the previously completed operation, success
>   or an error. See Error Scenarios for details on errors.
>
>   Concurrent Request
>
>   The request was retried before the original request completed. The resource
>   SHOULD respond with a resource conflict error. See Error Scenarios for
>   details.

Note that a **failed** original is replayed too — "success or an error". §4.7
returns to why that is contentious.

**Error handling** (§2.7). Three defined scenarios, all `SHOULD`, none `MUST`:

| Scenario | Status | Draft's wording |
| --- | --- | --- |
| Header missing on an operation that requires it | `400 Bad Request` | "the resource SHOULD reply with an HTTP 400 status code with body containing a link pointing to relevant documentation" |
| Key reused with a different payload | `422 Unprocessable Content` | "If there is an attempt to reuse an idempotency key with a different request payload, the resource SHOULD reply with a HTTP 422 status code" |
| Retry arrives while the original is still running | `409 Conflict` | "If the request is retried, while the original request is still being processed, the resource SHOULD reply with an HTTP 409 status code with body containing problem description" |

The draft's `422` example body:

> ```
> HTTP/1.1 422 Unprocessable Content
> Content-Type: application/problem+json
> Content-Language: en
> {
>   "type": "https://developer.example.com/idempotency",
>   "title": "Idempotency-Key is already used",
>   "detail": "This operation is idempotent and it requires
>   correct usage of Idempotency Key. Idempotency Key MUST not be
>   reused across different payloads of this operation.",
> }
> ```

and its `409`:

> ```
> HTTP/1.1 409 Conflict
> Content-Type: application/problem+json
> Content-Language: en
> {
>   "type": "https://developer.example.com/idempotency",
>   "title": "A request is outstanding for this Idempotency-Key",
>   "detail": "A request with the same Idempotency-Key for the
>   same operation is being processed or is outstanding.",
> }
> ```

The draft then states which of these the client may simply repeat:

> Clients MUST correct the requests (with the exception of 409 where no
> correction is required) before performing a retry operation, or the resource
> MUST fail the request and return one of the above errors.

The status codes line up with RFC 9110's own definitions, though neither was
written with idempotency in mind. [RFC 9110
§15.5.10](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.10):

> The 409 (Conflict) status code indicates that the request could not be
> completed due to a conflict with the current state of the target resource. This
> code is used in situations where the user might be able to resolve the conflict
> and resubmit the request.

"Might be able to resolve the conflict and resubmit" is a good fit for "wait, then
retry the same key". [RFC 9110
§15.5.21](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.21):

> The 422 (Unprocessable Content) status code indicates that the server
> understands the content type of the request content (hence a 415 (Unsupported
> Media Type) status code is inappropriate), and the syntax of the request
> content is correct, but it was unable to process the contained instructions.

A fingerprint mismatch is exactly that: well-formed content the server refuses to
act on.

**Security considerations** (§5) are short but load-bearing, and §4.9 returns to
them:

> * Injection attacks - When the resources does not validate the idempotency key
>   in the client request and performs a idempotent cache lookup, there can be
>   security attacks (primarily in the form of injection), compromising the
>   server.
> * Data leaks-When an idempotency implementation allows low entropy keys,
>   attackers MAY determine other keys and use them to fetch existing idempotent
>   cache entries, belonging to other clients.

with the recommended mitigation:

> * On the resource, implement a unique composite key as the idempotent cache
>   lookup key. For example, a composite key MAY be implemented by combining the
>   idempotency key sent by the client with other client specific attributes
>   known only to the resource.

**Two errata in the draft itself**, verified against the source documents, which
are a useful reminder that a draft is a draft:

1. §1 says "Per [RFC9110], the methods OPTIONS, HEAD, GET, PUT and DELETE are
   idempotent". RFC 9110 §9.2.2 says "PUT, DELETE, and safe request methods", and
   §9.2.1 lists the safe methods as "GET, HEAD, OPTIONS, and TRACE". The draft
   omits **TRACE**.
2. Its normative references are stale. It cites **RFC 8941** for Structured
   Fields, which was [obsoleted by RFC
   9651](https://www.rfc-editor.org/rfc/rfc9651.txt) in September 2024, and
   **RFC 7231** for the definition of "resource" and for `IMF-fixdate`, which was
   [obsoleted by RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.txt) in June
   2022 — the very document it cites elsewhere.

### 1.6 The vendor-neutral RPC formulation

The same design exists outside HTTP. Google's API Improvement Proposals state it
as a request field rather than a header, and the normative bullets are tighter
than the IETF draft's.

> The most important purpose for request IDs is to provide idempotency
> guarantees: allowing the same request to be issued more than once without
> subsequent calls having any effect. In the event of a network failure, the
> client can retry the request, and the server can detect duplication and ensure
> that the request is only processed once.

> * Providing a request ID **must** guarantee idempotency.
> * If a duplicate request is detected, the server **should** return the response
>   for the previously successful request, because the client most likely did not
>   receive the previous response.
> * APIs **may** choose any reasonable timeframe for honoring request IDs.
> * The `request_id` field **must** be provided on the request message to which
>   it applies (and it **must not** be a field on resources themselves).
> * Request IDs **should** be optional.
> * Request IDs **should** be able to be UUIDs, and **may** allow UUIDs to be the
>   only valid format. The format restrictions for request IDs **must** be
>   documented.

— [AIP-155: Request identification](https://google.aip.dev/155), state
"Approved", created 2019-05-06, changelog entries through 2024-01-08.

Two of those bullets are quietly important. "APIs **may** choose any reasonable
timeframe" is a specification *declining* to pick a retention window, which is why
§4.3 finds five different answers in the wild. And "**must not** be a field on
resources themselves" is a real design constraint: the key identifies *a request*,
not *a thing*, and storing it on the created resource conflates the two.

AIP-155 also carries an escape hatch that the payments vendors do not:

> In some unusual situations, it may not be possible to return an identical
> success response. For example, a duplicate request to create a resource may
> arrive after the resource has not only been created, but subsequently updated;
> because the service has no other need to retain the historical data, it is no
> longer feasible to return an identical success response.
>
> In this situation, the method may return the current state of the resource
> instead. In other words, it is permissible to substitute the historical success
> response with a similar response that reflects more current data.

This is a genuine, citable fork in the design space, and it is not cosmetic:

- **Replay the stored original response.** Stripe: "Stripe's idempotency works by
  saving the resulting status code and body of the first request made for any
  given idempotency key". Square: "the endpoint returns the response as the first
  successful CreatePayment response".
- **Return current state.** AIP-155, above. PayPal, explicitly: "PayPal provides
  the status of a request at the current time and not the status of the original
  request."

A client that assumes the first and is talking to a server that does the second
will misread a subsequently-modified resource as the original outcome.

---

## 2. The Lifecycle

### 2.1 The shape of the problem

Before the diagram, fix the vocabulary. Three of these terms are Brandur Leach's,
from his write-up of how Stripe-style keys are built on Postgres — **practitioner
writing**, not normative, but the vocabulary is good and widely borrowed.

| Term | Meaning | Source |
| --- | --- | --- |
| **Idempotency key** | "a unique value generated by the client which the resource uses to recognize subsequent retries of the same request" | [draft-07 §2](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07#section-2) (spec) |
| **Idempotency fingerprint** | a checksum or field-match over the request payload, "generated from request payload data by the resource" | [draft-07 §2.4](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07#section-2.4) (spec) |
| **Key record** | the server-side row holding key, fingerprint, state, and the stored response | implied by draft-07 §2.6; concrete schema in [brandur.org](https://brandur.org/idempotency-keys) (practitioner) |
| **Foreign state mutation** | "calling out and manipulating data on another system" — a side effect you cannot roll back | [brandur.org](https://brandur.org/idempotency-keys) (practitioner) |
| **Atomic phase** | "a set of local state mutations that occur in transactions between foreign state mutations" | [brandur.org](https://brandur.org/idempotency-keys) (practitioner) |
| **Recovery point** | "a name of a check point that we get to after having successfully executed any atomic phase **or** foreign state mutation" | [brandur.org](https://brandur.org/idempotency-keys) (practitioner) |

### 2.2 Sequence flow: the happy path, with a lost response

This is the case the whole mechanism exists for. The operation *succeeds*; the
*response* is lost; the client retries; the server replays.

```
 CLIENT                      API / HANDLER                 KEY STORE           EFFECT STORE
   │                              │                            │                    │
   │ (0) generate key             │                            │                    │
   │     k = uuid4()              │                            │                    │
   │     store k with the         │                            │                    │
   │     *intent*, before         │                            │                    │
   │     any request              │                            │                    │
   │                              │                            │                    │
   │ (1) POST /charges            │                            │                    │
   │     Idempotency-Key: k       │                            │                    │
   │     {amount: 2000, ...}      │                            │                    │
   ├─────────────────────────────>│                            │                    │
   │                              │ (2) fingerprint = H(body)  │                    │
   │                              │                            │                    │
   │                              │ (3) ATOMIC CLAIM           │                    │
   │                              │     insert (k, fp,         │                    │
   │                              │       state=IN_FLIGHT)     │                    │
   │                              │     IF NOT EXISTS          │                    │
   │                              ├───────────────────────────>│                    │
   │                              │<─── claimed (row created) ─┤                    │
   │                              │                            │                    │
   │                              │ (4) execute the operation  │                    │
   │                              ├────────────────────────────┼───────────────────>│
   │                              │<───────── charge ch_1 ─────┼────────────────────┤
   │                              │                            │                    │
   │                              │ (5) COMMIT: effect + key record together        │
   │                              │     state=COMPLETE, status=200, body={ch_1}     │
   │                              ├═══════════════════════════>│═══════════════════>│
   │                              │                            │                    │
   │ (6) 200 OK {ch_1}            │                            │                    │
   │<─ ─ ─ ─ ─ ─ ─ ─ X            │      ✗ RESPONSE LOST       │                    │
   │   (never arrives)            │                            │                    │
   │                              │                            │                    │
   │ ── timeout ──                │                            │                    │
   │ ── backoff + jitter ──       │                            │                    │
   │                              │                            │                    │
   │ (7) POST /charges            │                            │                    │
   │     Idempotency-Key: k       │   ← SAME key, SAME body    │                    │
   │     {amount: 2000, ...}      │                            │                    │
   ├─────────────────────────────>│                            │                    │
   │                              │ (8) lookup k               │                    │
   │                              ├───────────────────────────>│                    │
   │                              │<── found, state=COMPLETE ──┤                    │
   │                              │                            │                    │
   │                              │ (9) fingerprint matches?   │                    │
   │                              │     yes → replay           │                    │
   │                              │                            │                    │
   │                              │     NO CALL TO EFFECT STORE ─────────── ✗       │
   │                              │                            │                    │
   │ (10) 200 OK {ch_1}           │                            │                    │
   │      Idempotent-Replayed: true                            │                    │
   │<─────────────────────────────┤                            │                    │
   │                              │                            │                    │
   │  ── one charge exists ──     │                            │                    │
   │                              │                            │                    │
   │  ... later ...               │                            │                    │
   │                              │ (11) reaper deletes k after retention window    │
   │                              │                            │                    │
```

Legend: `───>` request/read, `═══>` transactional commit, `─ ─>` response,
`✗` failure or omission.

### 2.3 Step-by-step

**(0) The client generates the key — before the first attempt, not during the
retry.** This is the step most often got wrong, and getting it wrong silently
disables the entire mechanism. If the key is generated inside the retry loop, each
attempt carries a different key and every attempt is a fresh operation. The key
must be bound to the *user's intent* and must survive process restart if the
client can restart.

Stripe on generation:

> A client generates an idempotency key, which is a unique key that the server
> uses to recognize subsequent retries of the same request. How you create unique
> keys is up to you, but we suggest using V4 UUIDs, or another random string with
> enough entropy to avoid collisions. Idempotency keys are up to 255 characters
> long. Avoid using sensitive data (for example, email addresses or personal
> identifiers) as idempotency keys.

— [Stripe API reference, "Idempotent
requests"](https://docs.stripe.com/api/idempotent_requests).

Stripe's error-handling page names the two strategies and, importantly, licenses
the non-random one:

> There are two common strategies for generating idempotency keys:
>
> * Use an algorithm that generates a token with enough randomness, like UUID v4.
> * Derive the key from a user-attached object, like the ID of a shopping cart.
>   This provides a relatively straightforward way to protect against double
>   submissions.

— [Stripe, "Advanced error handling"](https://docs.stripe.com/error-low-level).

The second strategy is stronger than the first in one specific way: a UUID stored
only in the retrying process's memory is lost if that process dies, whereas a key
derived from the cart ID is reconstructible by *any* process. It is weaker in
another: the same cart legitimately checked out twice would collide.

The draft agrees on the recommendation and on the reason:

> It is RECOMMENDED that a UUID [RFC4122] or a similar random identifier be used
> as an idempotency key.

**(1) The request carries the key in a header.** The header is a request header;
it is not part of the body, not part of the URL, and — per AIP-155 — "**must
not** be a field on resources themselves". Vendors differ on the spelling and,
sharply, on the length budget:

| Vendor / spec | Field | Max length | Source |
| --- | --- | --- | --- |
| IETF draft-07 | `Idempotency-Key` (Structured Field String, quoted) | not specified | [draft-07 §2.1](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07#section-2.1) |
| Stripe | `Idempotency-Key` | 255 | [Stripe API ref](https://docs.stripe.com/api/idempotent_requests) |
| Adyen | `idempotency-key` | 64 | [Adyen, API idempotency](https://docs.adyen.com/development-resources/api-idempotency/) |
| Square | `idempotency_key` (body field) | 45 | [Square, CreatePayment](https://developer.squareup.com/reference/square/payments-api/create-payment) |
| PayPal | `PayPal-Request-Id` | 38 single-byte characters | [PayPal, Idempotency](https://developer.paypal.com/api/rest/reference/idempotency/) |
| Google AIP-155 | `request_id` (proto field) | "Restricted to 36 ASCII characters" — comment in the illustrative proto only, not a normative bullet | [AIP-155](https://google.aip.dev/155) |

A bare UUIDv4 is 36 characters, which fits everywhere. This is not a
coincidence — it is the reason the recommendation is universal.

Square adds a caveat everyone else omits:

> Note: The number of allowed characters might be less than the stated maximum,
> if multi-byte characters are used.

**(2) The server computes the fingerprint.** Per draft-07 §2.4 this is done *by
the resource*, over the request payload, by any of checksum-of-all,
checksum-of-some, field-match-of-all or field-match-of-some. The fingerprint's
only job is to catch the case in §4.1: same key, different request.

**(3) The atomic claim.** This is the step that decides whether the whole design
is correct, and §3 is devoted to it. Conceptually: *insert a record for this key
in the `IN_FLIGHT` state, but only if no record for this key exists, and do the
existence check and the insert as one indivisible operation.* If the insert
succeeds, this request owns the key and proceeds. If it fails because the row
already exists, this request is a duplicate and branches to step (8).

The critical property is that "check whether it exists" and "create it" are **one
operation**, not two. A read-then-write is a race, and §3.1 shows exactly how it
loses.

**(4) Execute the operation.** Nothing about this step is special, except that it
is the only step that is allowed to be slow, and therefore the only step during
which a concurrent duplicate can arrive.

**(5) Persist the response atomically with the effect.** The effect (the charge
row) and the key record's transition to `COMPLETE` with the stored status and body
must commit **together**. If they commit separately there is a window in which the
effect exists but the key record does not say so, and a retry landing in that
window will execute the effect a second time. In a single relational database this
is one transaction. Across a database and a third party it is not possible at all,
which is what §4.6 is about.

Stripe describes what is stored:

> Stripe's idempotency works by saving the resulting status code and body of the
> first request made for any given idempotency key, regardless of whether it
> succeeds or fails. Subsequent requests with the same key return the same result,
> including 500 errors.

Note "regardless of whether it succeeds or fails" and "including 500 errors".
That is a deliberate and contestable choice; §4.7 takes it apart.

**(6) The response is lost.** Everything so far was correct and the client still
does not know it. Brandur's taxonomy of where this can happen:

> Consider a call between any two nodes. There are a variety of failures that can
> occur:
>
> The initial connection could fail as the client tries to connect to a server.
> The call could fail midway while the server is fulfilling the operation, leaving
> the work in limbo.
> The call could succeed, but the connection break before the server can tell its
> client about it.

and the consequence:

> Any one of these leaves the client that made the request in an uncertain
> situation. In some cases, the failure is definitive enough that the client knows
> with good certainty that it's safe to simply retry it. For example, a total
> failure to even establish a connection to the server. In many others though, the
> success of the operation is ambiguous from the perspective of the client, and it
> doesn't know whether retrying the operation is safe. A connection terminating
> midway through message exchange is an example of this case.

— Brandur Leach, ["Designing robust and predictable APIs with
idempotency"](https://stripe.com/blog/idempotency), Stripe blog, 22 February
2017. **Practitioner writing** on a vendor blog.

This is Birrell and Nelson's "either once or not at all — the user is not told
which", restated for HTTP thirty-four years later.

**(7) The client retries — same key, same body, after backoff with jitter.** The
"same body" half is not optional; §4.1 covers what happens if it changes. On the
backoff:

> It's usually recommended that clients follow something akin to an exponential
> backoff algorithm as they see errors. The client blocks for a brief initial wait
> time on the first failure, but as the operation continues to fail, it waits
> proportionally to 2^n, where n is the number of failures that have occurred. By
> backing off exponentially, we can ensure that clients aren't hammering on a
> downed server and contributing to the problem.

> Furthermore, it's also a good idea to mix in an element of randomness. If a
> problem with a server causes a large number of clients to fail at close to the
> same time, then even with back off, their retry schedules could be aligned
> closely enough that the retries will hammer the troubled server. This is known
> as the thundering herd problem.
>
> We can address thundering herd by adding some amount of random "jitter" to each
> client's wait time.

— same source. Jitter matters more than usual here, because idempotency-key
retries are *correlated by construction*: every client that lost a response to the
same incident will retry on the same schedule.

Stripe's documentation gives the rule that makes network errors the easy case:

> This class of errors is where the value of idempotency keys and request retries
> is most obvious. When intermittent problems occur, clients are usually left in a
> state where they don't know whether or not the server received the request. To
> get a definitive answer, they should retry such requests with the same
> idempotency keys and the same parameters until they're able to receive a result
> from the server.

**(8)–(9) Lookup and fingerprint check.** The key is found in state `COMPLETE`.
The fingerprint is recomputed from the new request and compared. Match → replay.
Mismatch → §4.1.

**(10) Replay the stored response — without touching the effect store.** The
handler does not run. This is the entire point: the second request produces no
second effect. Stripe marks replays so clients can tell:

> To identify a previously executed response that's being replayed from the
> server, look for the header `Idempotent-Replayed: true`.

Note that `Idempotent-Replayed` is documented on Stripe's error-handling page,
**not** on its API reference page for idempotent requests, and it is not in the
IETF draft at all. It is a Stripe extension, and a useful one — it is the only way
a client can distinguish "this ran now" from "this ran earlier".

**(11) Expiry.** The record is eventually deleted. §4.3 is about how long "eventually"
has to be, and it is a longer discussion than it looks.

### 2.4 The key record as a state machine

The draft implies three states without naming them; AWS's own Lambda Powertools
implementation names them. The transitions:

```
                       (3) atomic claim SUCCEEDS
    ┌───────────────┐ ─────────────────────────────> ┌──────────────┐
    │   no record   │                                │  IN_FLIGHT   │
    └───────────────┘ <───────────────────────────── └──────────────┘
            ▲            lease expires, record                │
            │            reclaimed (§4.5)                     │ (5) handler returns;
            │                                                 │     effect + response
            │ retention window elapses;                       │     commit together
            │ reaper deletes the record (§4.3)                ▼
            │                                         ┌──────────────┐
            └──────────────────────────────────────── │   COMPLETE   │
                                                      └──────────────┘
```

And the read path, for a request whose atomic claim **failed** because a record
already exists:

| Existing record's state | Fingerprint | Server does | Status |
| --- | --- | --- | --- |
| `IN_FLIGHT` | (not checked) | refuse; tell the client to retry later | `409` (draft-07, Stripe) / `422` or `409` (Adyen) |
| `COMPLETE` | matches | replay the stored status and body; **do not run the handler** | the stored status |
| `COMPLETE` | differs | refuse; the client has a key-reuse bug | `422` (draft-07) / `400` (AWS) |

An **expired** record is not a fourth case. It is deleted, so the claim in step (3)
succeeds and the operation runs again as if the key had never been seen — which is
why §4.3 matters more than its dryness suggests.

The `IN_FLIGHT` state is the whole reason this is hard. If operations were
instantaneous it would not exist, and an idempotency key would be a cache lookup.

### 2.5 Illustrative sketch

*Written for this guide. Not a quotation from any source, and not production
code — it omits error handling, transaction retry, observability and expiry.* Its
only job is to make the atomicity of step (3) and step (5) concrete.

```python
import hashlib
import json

CONFLICT = "another request with this key is in flight"
MISMATCH = "this key was used with a different payload"


def fingerprint(body: dict) -> str:
    """The resource computes this; the client never sends it.
    draft-07 §2.4 permits a checksum over the whole payload."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def handle(db, account_id, key, body, operation):
    scope = (account_id, key)          # §4.2: keys are scoped, never global
    fp = fingerprint(body)

    # --- Step 3: the atomic claim. -----------------------------------------
    # One statement. The existence check and the insert cannot be separated,
    # or two concurrent requests can both observe "absent" and both proceed.
    claimed = db.insert_if_absent(
        scope, {"fingerprint": fp, "state": "IN_FLIGHT"}
    )

    if not claimed:
        record = db.get(scope)

        if record["fingerprint"] != fp:
            return 422, {"error": MISMATCH}          # draft-07 §2.7

        if record["state"] == "IN_FLIGHT":
            return 409, {"error": CONFLICT}          # draft-07 §2.7

        # Replay. The handler is NOT invoked.
        return record["status"], record["body"]

    # --- Steps 4 and 5: execute, then commit effect and record TOGETHER. ---
    # If these two commits can be separated, a retry landing in the gap
    # executes the operation a second time.
    with db.transaction() as tx:
        status, response = operation(tx, body)
        tx.update(scope, {
            "state": "COMPLETE", "status": status, "body": response,
        })

    return status, response
```

Everything interesting is in `insert_if_absent` and in the single `with
db.transaction()` block. §3 is about the first; §4.6 is about what happens when
`operation` reaches outside the database and the second becomes impossible.

---

## 3. Concurrency and the Distributed Lock Problem

### 3.1 The race, precisely

Step (3) of the lifecycle looks innocuous until you write it as two operations:

```
   REQUEST A                                    REQUEST B
   (key = k)                                    (key = k)
       │                                            │
  t₀   │ SELECT * FROM keys WHERE key = k           │
       │ → not found                                │
       │                                       t₁   │ SELECT * FROM keys WHERE key = k
       │                                            │ → not found        ← STILL not found
  t₂   │ INSERT (k, IN_FLIGHT)                      │
       │                                       t₃   │ INSERT (k, IN_FLIGHT)
       │                                            │
  t₄   │ charge the card  ──────> $20               │
       │                                       t₅   │ charge the card  ──────> $20
       │                                            │
       ▼                                            ▼
                        TWO CHARGES
```

Both requests observed "absent" because both read before either wrote. This is a
plain time-of-check-to-time-of-use bug, and it is not fixed by making the window
smaller. A duplicate submit from a double-clicked button, two load-balanced
retries arriving on different application servers, or a client retrying on a
timeout while the original is still running will all produce it. Note especially
that **the two requests may be handled by different processes on different
machines**, so a mutex, a language-level lock or a per-process cache cannot help.

The requirement is therefore: *the check and the claim must be a single
indivisible operation in a store that both requests can see.* There are three
families of answer. Two are good. One is popular and worse.

### 3.2 Mechanism A — atomic conditional insert (the recommended answer)

Collapse check-and-claim into one statement, and let the storage engine's
uniqueness machinery arbitrate. Exactly one request wins; the loser is told it
lost.

**PostgreSQL.** A `UNIQUE` index on the key column makes a second insert fail.
The documentation states the guarantee for the upsert form explicitly:

> ON CONFLICT DO UPDATE guarantees an atomic INSERT or UPDATE outcome; provided
> there is no independent error, one of those two outcomes is guaranteed, even
> under high concurrency. This is also known as UPSERT — "UPDATE or INSERT".

— [PostgreSQL 17 documentation, `INSERT`, "ON CONFLICT
Clause"](https://www.postgresql.org/docs/17/sql-insert.html).

"Even under high concurrency" is the phrase doing the work. `INSERT ... ON
CONFLICT DO NOTHING` combined with `RETURNING` tells you in one round trip
whether you claimed the key or someone else already had it.

**DynamoDB.** The same primitive, spelled as a condition expression. The
atomicity is stated for the operations themselves:

> DynamoDB provides four operations for basic create, read, update, and delete
> (CRUD) functionality. All these operations are atomic.

and the conditional form:

> DynamoDB optionally supports conditional writes for these operations. A
> conditional write succeeds only if the item attributes meet one or more
> expected conditions. Otherwise, it returns an error.

> Conditional writes check their conditions against the most recently updated
> version of the item.

— [AWS, "Working with items and attributes in
DynamoDB"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html).

The exact idiom for "insert only if absent" is named in the `PutItem` reference:

> To prevent a new item from replacing an existing item, use a conditional
> expression that contains the `attribute_not_exists` function with the name of
> the attribute being used as the partition key for the table. Since every record
> must contain that attribute, the `attribute_not_exists` function will only
> succeed if no matching item exists.

— [AWS, `PutItem` API
reference](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_PutItem.html).

The loser is told, by name:

> When a conditional `PutItem`, `UpdateItem`, or `DeleteItem` operation fails its
> condition, it returns a `ConditionalCheckFailedException`.

AWS also documents *why* this makes retries safe, in language that maps directly
onto the ambiguous failure of §1.4:

> For example, suppose that you issue an `UpdateItem` request to increase the
> `Price` of an item by 3, but only if the `Price` is currently 20. After you send
> the request, but before you get the results back, a network error occurs, and
> you don't know whether the request was successful. Because this conditional
> write is idempotent, you can retry the same `UpdateItem` request, and DynamoDB
> updates the item only if the `Price` is currently 20.

**Redis.** `SET key value NX` is the same compare-and-set insert:

> **NX** — Only set the key if it does not already exist.

and the caller learns it lost from the return value:

> Null reply in the following two cases. — The key doesn't exist and
> XX/IFEQ/IFDEQ was specified. The key was not created. — The key exists, and NX
> was specified [...] The key was not set. Simple string reply: OK: The key was
> set.

— [Redis, `SET`](https://redis.io/docs/latest/commands/set/), available since
Redis 1.0.0; `NX` added in 2.6.12.

A caveat worth recording because it is widely misquoted: **the `SET` page makes
no explicit atomicity claim.** The guarantee has to be sourced from the
transactions page instead:

> All the commands in a transaction are serialized and executed sequentially. A
> request sent by another client will never be served in the middle of the
> execution of a Redis Transaction. This guarantees that the commands are
> executed as a single isolated operation.

— [Redis, "Transactions"](https://redis.io/docs/latest/develop/using-commands/transactions/).

### 3.3 Mechanism A in the wild: AWS Lambda Powertools

AWS ships a first-party implementation of this exact design, which is useful
because the code is readable and the docs explain the reasoning.

The claim is a conditional write, and the docs say so while explaining a cost
optimisation:

> **Old boto3 versions can increase costs.** For cost optimization, we use a
> conditional `PutItem` to always lock a new idempotency record. If locking
> fails, it means we already have an idempotency record saving us an additional
> `GetItem` call.

— [Powertools for AWS Lambda (Python),
Idempotency](https://docs.powertools.aws.dev/lambda/python/latest/utilities/idempotency/).

The condition expression itself, from
`aws_lambda_powertools/utilities/idempotency/persistence/dynamodb.py` (comments
are the library authors'), is a three-way "claim if nobody holds this, or the
holder's claim has gone stale":

> ```
> # Conditions to successfully save a record:
>
> # The idempotency key does not exist:
> #    - first time that this invocation key is used
> #    - previous invocation with the same key was deleted due to TTL
> idempotency_key_not_exist = "attribute_not_exists(#id)"
>
> # The idempotency record exists but it's expired:
> idempotency_expiry_expired = "#expiry < :now"
>
> # The status of the record is "INPROGRESS", there is an in-progress expiry timestamp, but it's expired
> inprogress_expiry_expired = " AND ".join(
>     [
>         "#status = :inprogress",
>         "attribute_exists(#in_progress_expiry)",
>         "#in_progress_expiry < :now_in_millis",
>     ],
> )
>
> condition_expression = (
>     f"{idempotency_key_not_exist} OR {idempotency_expiry_expired} OR ({inprogress_expiry_expired})"
> )
> ```

The loser's path is the `ConditionalCheckFailedException`, translated into a
domain error:

> ```
> except ClientError as exc:
>     error_code = exc.response.get("Error", {}).get("Code")
>     if error_code == "ConditionalCheckFailedException":
>         ...
>         raise IdempotencyItemAlreadyExistsError() from exc
> ```

and when the existing record is still running:

> **Handling concurrent executions with the same payload**
>
> This utility will raise an `IdempotencyAlreadyInProgressError` exception if you
> receive multiple invocations with the same payload while the first invocation
> hasn't completed yet.

> This is a locking mechanism for correctness. Since we don't know the result
> from the first invocation yet, we can't safely allow another concurrent
> execution.

The record states are `INPROGRESS`, `COMPLETED` and `EXPIRED`, per the source
constant:

> `STATUS_CONSTANTS = MappingProxyType({"INPROGRESS": "INPROGRESS", "COMPLETED": "COMPLETED", "EXPIRED": "EXPIRED"})`

— `aws_lambda_powertools/utilities/idempotency/persistence/datarecord.py`. Note
that the docs page's own class diagram writes `COMPLETE` and its sample DynamoDB
table writes `IN_PROGRESS`; the three spellings on one documentation page
disagree, and the code constant is the one to trust.

Two further details from the same page, both of which anticipate §3.5 and §4.5:

> By default, we expire idempotency records after an hour (3600 seconds). After
> that, a transaction with the same payload will not be considered idempotent.

> By default, we protect against concurrent executions with the same payload
> using a locking mechanism. However, if your Lambda function times out before
> completing the first invocation it will only accept the same request when the
> idempotency record expire.
>
> If a second invocation happens after this timestamp, and the record is marked
> as INPROGRESS, we will run the invocation again as if it was in the EXPIRED
> state.

That last paragraph is a **lease**, and it is the same lease whose expiry
Kleppmann's critique is about. The difference — the reason it is defensible here
and not in Redlock — is developed in §3.6.

### 3.4 Mechanism B — serialise the transaction

The other good answer keeps the claim in the same database as the effect but
leans on isolation rather than a uniqueness constraint. PostgreSQL's
`SERIALIZABLE` level is defined by the standard such that

> any concurrent execution of a set of Serializable transactions is guaranteed to
> produce the same effect as running them one at a time in some order

— [PostgreSQL 17 documentation, "Transaction
Isolation"](https://www.postgresql.org/docs/17/transaction-iso.html).

Brandur Leach's Postgres implementation of Stripe-style keys — **practitioner
writing**, but the most detailed public account of the mechanism — combines both:
a unique index *and* a serialisable transaction *and* a lock column.

> We've made `idempotency_key` unique, but across `(user_id, idempotency_key)` so
> that it's possible to have the same idempotency key for different requests as
> long as it's across different user accounts.

> `locked_at`: A field that indicates whether this idempotency key is actively
> being worked. The first API request that creates the key will lock it
> automatically, but subsequent retries will also set it to make sure that
> they're the only request doing the work.

> At first glance this code might not look like it's safe from having two
> concurrent requests come in in close succession and try to the lock the same
> key, but it is because the atomic phase is wrapped in a `SERIALIZABLE`
> transaction. If two different transactions both try to lock any one key, one of
> them will be aborted by Postgres.

and the summary of the race:

> Two requests try to create an idempotency key at the same time: A UNIQUE
> constraint in the database guarantees that only one request can succeed. One
> goes through, and the other gets a `409 Conflict`.

— Brandur Leach, ["Implementing Stripe-like Idempotency Keys in
Postgres"](https://brandur.org/idempotency-keys), 27 October 2017. (The typo "try
to the lock the same key" is in the original.)

Note that `locked_at` is a lease here too, and Brandur's code checks its age
rather than merely its presence:

> ```
> # Only acquire a lock if the key is unlocked or its lock has expired
> # because the original request was long enough ago.
> if key.locked_at && key.locked_at > Time.now - IDEMPOTENCY_KEY_LOCK_TIMEOUT
>   halt 409, JSON.generate(wrap_error(Messages.error_request_in_progress))
> end
> ```

### 3.5 Mechanism C — an external distributed lock, and why it is the weaker answer

The tempting third design is: before doing anything, grab a lock named after the
idempotency key from a lock service — Redis, ZooKeeper, etcd — do the work,
release it. The Redis documentation offers the single-instance recipe:

> The command `SET resource-name anystring NX EX max-lock-time` is a simple way to
> implement a locking system with Redis.
>
> A client can acquire the lock if the above command returns OK (or retry after
> some time if the command returns Nil), and remove the lock just using DEL. The
> lock will be auto-released after the expire time is reached.

— [Redis, `SET`](https://redis.io/docs/latest/commands/set/), "Patterns".

and Redlock for the multi-node case:

> We propose an algorithm, called Redlock, which implements a DLM which we
> believe to be safer than the vanilla single instance approach.

— [Redis, "Distributed Locks with
Redis"](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/).
(Note: the once-canonical `redis.io/topics/distlock` URL now redirects to the
docs index, and the `develop/use-cases/patterns/distributed-locks/` path 404s;
the `develop/clients/patterns/` path above is the live one as of September 2026.)

**The problem is that a lock lease can expire while its holder is still running.**
Martin Kleppmann's critique states it plainly:

> In this example, the client that acquired the lock is paused for an extended
> period of time while holding the lock – for example because the garbage
> collector (GC) kicked in. The lock has a timeout (i.e. it is a lease), which is
> always a good idea (otherwise a crashed client could end up holding a lock
> forever and never releasing it). However, if the GC pause lasts longer than the
> lease expiry period, and the client doesn't realise that it has expired, it may
> go ahead and make some unsafe change.

and closes the obvious escape route:

> You cannot fix this problem by inserting a check on the lock expiry just before
> writing back to storage. Remember that GC can pause a running thread at any
> point, including the point that is maximally inconvenient for you (between the
> last check and the write operation).

> And if you're feeling smug because your programming language runtime doesn't
> have long GC pauses, there are many other reasons why your process might get
> paused. Maybe your process tried to read an address that is not yet loaded into
> memory, so it gets a page fault and is paused until the page is loaded from
> disk. [...] Whatever. Your processes will get paused.

> If you still don't believe me about process pauses, then consider instead that
> the file-writing request may get delayed in the network before reaching the
> storage service. Packet networks such as Ethernet and IP may delay packets
> arbitrarily, and they do: in a famous incident at GitHub, packets were delayed
> in the network for approximately 90 seconds.

> Even in well-managed networks, this kind of thing can happen. You simply cannot
> make any assumptions about timing, which is why the code above is fundamentally
> unsafe, no matter what lock service you use.

— Martin Kleppmann, ["How to do distributed
locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html),
8 February 2016. **Expert practitioner writing**, not a specification — though
Kleppmann is the author of *Designing Data-Intensive Applications* and the post
came out of the research for it.

Applied to our problem: request A claims key `k`, holds the lock, stalls for 40
seconds in a GC pause; the 30-second lease expires; request B claims `k`
legitimately and charges the card; A wakes up, still believing it holds the lock,
and charges the card again. **Two charges, with a correctly implemented lock.**

**His fix is fencing tokens:**

> The fix for this problem is actually pretty simple: you need to include a
> fencing token with every write request to the storage service. In this context,
> a fencing token is simply a number that increases (e.g. incremented by the lock
> service) every time a client acquires the lock.

> Client 1 acquires the lease and gets a token of 33, but then it goes into a long
> pause and the lease expires. Client 2 acquires the lease, gets a token of 34
> (the number always increases), and then sends its write to the storage service,
> including the token of 34. Later, client 1 comes back to life and sends its
> write to the storage service, including its token value 33. However, the storage
> server remembers that it has already processed a write with a higher token
> number (34), and so it rejects the request with token 33.

> Note this requires the storage server to take an active role in checking tokens,
> and rejecting any writes on which the token has gone backwards.

and his specific charge against Redlock:

> However, this leads us to the first big problem with Redlock: it does not have
> any facility for generating fencing tokens. The algorithm does not produce any
> number that is guaranteed to increase every time a client acquires a lock.

He also supplies the frame for deciding how much machinery the problem deserves:

> **Efficiency:** Taking a lock saves you from unnecessarily doing the same work
> twice (e.g. some expensive computation). If the lock fails and two nodes end up
> doing the same piece of work, the result is a minor increase in cost [...]
>
> **Correctness:** Taking a lock prevents concurrent processes from stepping on
> each others' toes and messing up the state of your system. If the lock fails and
> two nodes concurrently work on the same piece of data, the result is a corrupted
> file, data loss, permanent inconsistency, the wrong dose of a drug administered
> to a patient, or some other serious problem.
>
> Both are valid cases for wanting a lock, but you need to be very clear about
> which one of the two you are dealing with.

An idempotency key on a payments endpoint is unambiguously a **correctness** lock.
His conclusion for that case:

> On the other hand, if you need locks for correctness, please don't use Redlock.
> Instead, please use a proper consensus system such as ZooKeeper [...] (At the
> very least, use a database with reasonable transactional guarantees.) And please
> enforce use of fencing tokens on all resource accesses under the lock.

### 3.6 The other side: antirez's reply, and where the two actually converge

Fairness requires the rebuttal. Salvatore Sanfilippo (antirez), Redis's author,
replied within days.

> Martin's analysis of the algorithm concludes that Redlock is not safe. It is
> great that Martin published an analysis, I asked for an analysis in the original
> Redlock specification here [...] So thank you Martin. However I don't agree with
> the analysis.

— Salvatore Sanfilippo, ["Is Redlock safe?"](http://antirez.com/news/101),
February 2016. (The page carries only a relative timestamp; February 2016 is
computed from it and corroborated by his reference to Kleppmann's post as
"yesterday".)

On fencing tokens he makes three points. The first is that the demand is
self-undermining:

> Most of the times when you need a distributed lock system that can guarantee
> mutual exclusivity, when this property is violated you already lost. Distributed
> locks are very useful exactly when we have no other control in the shared
> resource. In his analysis, Martin assumes that you always have some other way to
> avoid race conditions when the mutual exclusivity of the lock is violated. I
> think this is a very strange way to reason about distributed locks with strong
> guarantees, it is not clear why you would use a lock with strong properties at
> all if you can resolve races in a different way.

The second is that a store capable of enforcing monotonic tokens is already
strong enough to make the lock redundant:

> If your data store can always accept the write only if your token is greater
> than all the past tokens, than it's a linearizable store. If you have a
> linearizable store, you can just generate an incremental ID for each Redlock
> acquired, so this would make Redlock equivalent to another distributed lock
> system that provides an incremental token ID with every new lock.

The third is the one that matters most for this document, because it is
**precisely the idempotency-key pattern**:

> Each Redlock is associated with a large random token [...] What do you do with a
> unique token? For example you can implement Check and Set. When starting to work
> with a shared resource, we set its state to '`<token>`', then we operate the
> read-modify-write only if the token is still the same when we write.

> However even if you happen to agree with Martin about the fact the above is very
> useful, the bottom line is that a unique identifier for each lock can be used
> for the same goals, but is much more practical in terms of not requiring strong
> guarantees from the store.

On the GC-pause trace, he argues that Redlock's re-check of the clock after
acquisition bounds the damage:

> Note steps 1 and 3. Whatever delay happens in the network or in the processes
> involved, after acquiring the majority we *check again* that we are not out of
> time. The delay can only happen after steps 3, resulting into the lock to be
> considered ok while actually expired, that is, we are back at the first problem
> Martin identified of distributed locks where the client fails to stop working to
> the shared resource before the lock validity expires. Let me tell again how this
> problem is common with *all the distributed locks implementations*[.]

And he concedes the clock point:

> However I think Martin is right that Redis and Redlock implementations should
> switch to the monotonic time API provided by most operating systems in order to
> make the above issues less of a problem.

**Redis's own documentation has since conceded further.** The live Redlock page
carries a "Disclaimer about consistency" that adopts Kleppmann's recommendation
outright:

> Please consider thoroughly reviewing the Analysis of Redlock section at the end
> of this page. Martin Kleppman's article and antirez's answer to it are very
> relevant. If you are concerned about consistency and correctness, you should pay
> attention to the following topics:

> **You should implement fencing tokens.** This is especially important for
> processes that can take significant time and applies to any distributed locking
> system. Extending locks' lifetime is also an option, but don´t assume that a
> lock is retained as long as the process that had acquired it is alive.

> **Redis is not using monotonic clock for TTL expiration mechanism.** That means
> that a wall-clock shift may result in a lock being acquired by more than one
> process.

— [Redis, "Distributed Locks with
Redis"](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/).
(The page spells the name "Kleppman" in the disclaimer and "Kleppmann" in the
analysis section; both are reproduced as written.)

**Where the two actually agree** is the useful conclusion. Kleppmann: the storage
server must "take an active role in checking tokens". Antirez: "we operate the
read-modify-write only if the token is still the same when we write". Both say
*the resource that holds the effect must itself check something before applying
the write.* They differ only on whether that something must be **monotonic** (a
fencing token, which also handles late writes from a stale holder) or may be a
**unique identity** (a check-and-set on a random token, which handles duplicates
but not ordering).

### 3.7 The synthesis: prefer a compare-and-set in the store that holds the effect

Everything above converges on one design rule, and it is the answer to "how do
high-scale companies handle two identical keys arriving at the same instant":

> **They do not take a lock. They make the key's creation itself the atomic
> operation, in the same store that holds the effect, so that winning the race and
> recording the effect are the same commit.**

This is strictly better than an external lock for four reasons, each traceable to
a source above:

1. **No lease to expire.** A unique-constraint violation or a
   `ConditionalCheckFailedException` is a decision made by the storage engine at
   write time, not a promise made to a client earlier that may have gone stale.
   Kleppmann's entire GC-pause argument is about the gap between *being told you
   hold the lock* and *performing the write*; a conditional write has no such gap
   because the two are one operation.
2. **No second system to be partitioned from.** An external lock service adds a
   component that can be unreachable while the database is fine, and vice versa.
   Adyen documents what it costs to depend on a separate consistent store for
   this: "In the unlikely event that this data store should become unavailable,
   the API returns an HTTP 503 – Service Unavailable status with the error code
   703".
3. **It is a fencing token, for free, in the only place that matters.** The key
   record *is* the token, and the store that holds the effect *is* the store that
   checks it — which is exactly what both Kleppmann and antirez say the resource
   must do.
4. **It composes with the commit of the effect.** Step (5) requires the effect and
   the key record to become durable together. If the key lives in the same
   transactional store as the effect, that is one transaction. If it lives in an
   external lock service, it cannot be.

The external lock has a legitimate but narrower role: as an *efficiency*
optimisation in Kleppmann's sense — avoiding wasted duplicate work before you get
to the database — layered on top of, never instead of, the conditional write.

### 3.8 What the vendors actually do when two identical keys collide

Every vendor documents this case, and **no two of them answer it the same way.**
This table is the single most useful artefact in this document, because the
disagreement is real and load-bearing.

| Vendor | Documented behaviour for a same-key request while the first is in flight | Status code | Retryable? |
| --- | --- | --- | --- |
| **IETF draft-07** | "the resource SHOULD reply with an HTTP 409 status code with body containing problem description" | `409` | yes — "with the exception of 409 where no correction is required" |
| **Stripe** | "If incoming parameters fail validation, or the request conflicts with another request that's executing concurrently, we don't save the idempotent result because no API endpoint initiates the execution. You can retry these requests." | `409 Conflict` — "The request conflicts with another request (perhaps due to using the same idempotent key)" | yes, explicitly |
| **Adyen** | "If you submit a duplicate request before the first request has completed, the API returns an HTTP 422 – Unprocessable Entity or HTTP 409 - Conflict status with the error code 704: 'request already processed or in progress'." | `422` **or** `409`, error code `704` | yes — signalled by a `transient-error: true` response header |
| **PayPal** | "When you send two simultaneous API requests with same `PayPal-Request-Id` header, PayPal processes the first request and might fail the second request." | not stated | not stated |
| **AWS Lambda Powertools** | "This utility will raise an `IdempotencyAlreadyInProgressError` exception if you receive multiple invocations with the same payload while the first invocation hasn't completed yet." | n/a (exception) | yes — "If you receive `IdempotencyAlreadyInProgressError`, you can safely retry the operation." |
| **Square** | **nothing documented** — neither the CreatePayment reference nor the idempotency guide addresses the concurrent case | — | — |
| **AWS EC2 client tokens** | **nothing documented** — the idempotency page addresses only completed requests | — | — |

Three things are worth drawing out of that table.

**Nobody blocks.** Not one vendor documents holding the second request open until
the first finishes and then replaying its response — which is what a naive "just
take a lock and wait" design would do. Every one of them **fails fast and tells
the client to retry**. That is the practical consequence of §3.5: waiting means
holding a lease, and a lease you hold is a lease that can expire under you.

**Stripe's rule is subtler than it looks.** The concurrent-conflict response is
deliberately *not* stored as the idempotent result:

> We save results only after the execution of an endpoint begins. If incoming
> parameters fail validation, or the request conflicts with another request that's
> executing concurrently, we don't save the idempotent result because no API
> endpoint initiates the execution. You can retry these requests.

— [Stripe API reference, "Idempotent
requests"](https://docs.stripe.com/api/idempotent_requests).

If the 409 *were* stored, the key would be permanently poisoned: every subsequent
retry would replay a 409 and the client could never learn the real outcome. The
rule "only results from requests that actually began executing are stored" is what
keeps the key usable.

**PayPal's "might fail" is the weakest guarantee on the list**, and it is worth
noticing that a vendor documented it that way rather than promising more.

---

## 4. Deep-Dive Edge Cases

### 4.1 Same key, different payload

The draft's answer is `422`, via the fingerprint of §1.5:

> If there is an attempt to reuse an idempotency key with a different request
> payload, the resource SHOULD reply with a HTTP 422 status code with body
> containing a link pointing to relevant documentation.

Stripe's:

> The idempotency layer compares incoming parameters to those of the original
> request and errors if they're not the same to prevent accidental misuse.

> Sending the same idempotency with different parameters produces an error
> indicating that the new request didn't match the original.

AWS's, across two services, using one consistent error name:

> If you retry a successful request using the same client token, but one or more
> of the parameters are different, other than the Region or Availability Zone, the
> retry fails with an `IdempotentParameterMismatch` error.

— [AWS, "Ensuring idempotency in Amazon EC2 API
requests"](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Run_Instance_Idempotency.html).

> If you submit a request with the same client token but a change in other
> parameters within the 10-minute idempotency window, DynamoDB returns an
> `IdempotentParameterMismatch` exception.

— [AWS, `TransactWriteItems`](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html)
(HTTP status 400).

Square's is deliberately hedged:

> If you use the same idempotency key but change the CreatePayment request (for
> example, specify a different payment amount), you get an error indicating that
> you used the idempotency key previously. Note that this behavior might vary
> depending on the API.

**The authorities disagree on the status code.** The IETF draft says `422`. AWS
returns HTTP `400`. Stripe's documentation describes the error without pinning a
code to it on the idempotency page. If you are writing a client, do not assume
`422`.

**Why detect it at all?** Because the alternative is worse in both directions. If
you ignored the payload and replayed on key alone, a client with a key-reuse bug
would silently receive someone else's answer — the $5 charge response for a $500
request. If you ignored the key and executed, you would have no idempotency at
all. Failing loudly is the only option that surfaces the client bug.

**A design trap in the fingerprint.** draft-07 §2.4 permits fingerprinting either
"the entire request payload" or "selected element(s)". Whole-payload checksums are
brittle in practice: a client that re-serialises its JSON with different key
ordering, adds a `client_timestamp` field, or upgrades a library that changes
float formatting will produce a different fingerprint for a semantically identical
retry — and get a `422` on a request that should have replayed. Fingerprinting the
semantically significant fields is more forgiving, at the cost of missing changes
to the fields you excluded. The specification takes no position; this is left to
the implementer, and the choice is a real one.

### 4.2 Key scoping

A key is never global. draft-07 §5 makes this a **security** requirement, not
merely a hygiene one:

> On the resource, implement a unique composite key as the idempotent cache lookup
> key. For example, a composite key MAY be implemented by combining the
> idempotency key sent by the client with other client specific attributes known
> only to the resource.

because otherwise:

> Data leaks-When an idempotency implementation allows low entropy keys, attackers
> MAY determine other keys and use them to fetch existing idempotent cache
> entries, belonging to other clients.

Concretely: if keys are global and a client sends `Idempotency-Key: 1`, it
receives whatever response the previous sender of `1` got. That is a
cross-tenant data disclosure, reachable by guessing.

The observed scopes differ substantially:

| Scope dimension | Who does it | Source |
| --- | --- | --- |
| Per user/account | Brandur's schema: `UNIQUE (user_id, idempotency_key)` | [brandur.org](https://brandur.org/idempotency-keys) (practitioner) |
| Per company account | Adyen: "Keys are stored at a company account level. The system checks that the idempotency keys are unique to the company account." | [Adyen](https://docs.adyen.com/development-resources/api-idempotency/) |
| Per region | Adyen: "If you are targeting multiple regional endpoints simultaneously, idempotency keys will not be checked for duplication in other regions." | [Adyen](https://docs.adyen.com/development-resources/api-idempotency/) |
| Per region (AWS "regional idempotency") | EC2: "a request with the same client token can complete only once within a Region. However, the exact same request, with the same client token, can be used to launch instances in a different Region." | [AWS EC2](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Run_Instance_Idempotency.html) |
| Per availability zone (AWS "zonal idempotency") | EC2: "a request with the same client token can complete only once within each Availability Zone in a Region" | [AWS EC2](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Run_Instance_Idempotency.html) |
| Per API call type | PayPal: "The `PayPal-Request-Id` header value must be unique for both each request and an API call type. For example, authorize payment and capture authorized payment." | [PayPal](https://developer.paypal.com/api/rest/reference/idempotency/) |
| Per function + payload hash | Powertools: "By default, this is a combination of (a) Lambda function name, (b) fully qualified name of your function, and (c) a hash of the entire payload" | [Powertools](https://docs.powertools.aws.dev/lambda/python/latest/utilities/idempotency/) |

Two consequences a reader should internalise. **Regional scoping means retrying
against a different region is not idempotent** — AWS says so outright, and so does
Adyen. A client with region failover in its retry policy can duplicate an
operation while following every rule correctly. And **per-endpoint scoping means
the same key on `/authorize` and `/capture` are different keys**, which is usually
what you want but occasionally surprising.

Also note the Powertools default: the key is *derived from the payload hash*
rather than supplied by the client. That is a genuinely different design — it
deduplicates identical payloads automatically, but it cannot distinguish "the same
request retried" from "two legitimately identical requests", which is precisely
the distinction a client-supplied key exists to express. It is a reasonable
default for event processing and a poor one for payments.

### 4.3 Retention and expiry

**No authority agrees with any other**, and the specification explicitly declines
to choose:

> APIs **may** choose any reasonable timeframe for honoring request IDs.

— [AIP-155](https://google.aip.dev/155).

> The resource MAY require time based idempotency keys to be able to purge or
> delete a key upon its expiry. The resource SHOULD define such expiration policy
> and publish it in the documentation.

— [draft-07 §2.3](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07#section-2.3).

| Source | Documented window |
| --- | --- |
| **Stripe** (API reference) | "You can remove keys from the system automatically after they're at least 24 hours old." |
| **Stripe** (error handling page) | "as long as the second request occurs within 24 hours from when you first receive the key (keys expire out of the system after 24 hours)" |
| **Adyen** | "Idempotency keys are valid for a period of 7 to 14 days after first submission." |
| **AWS DynamoDB `TransactWriteItems`** | "A client request token is valid for 10 minutes after the first request that uses it is completed." |
| **AWS Lambda Powertools** | "By default, we expire idempotency records after an hour (3600 seconds)." — configurable, "There is no limit on how long this expiration window can be set to." |
| **AWS EC2 client tokens** | **not documented** (see §6) |
| **PayPal** | **not documented globally**: "To determine whether your API supports it and for information about how long the server stores the ID, see the reference for your API." |
| **Square** | **not documented** on either the CreatePayment reference or the idempotency guide |
| **Brandur** (practitioner) | recommends ~72 hours: "even if a bug is deployed on Friday that errors a large number of valid requests, an app could still keep a record of them throughout the weekend and onto Monday" |
| **Birrell & Nelson, 1983** | "say, after five minutes" for RPC call-identifier state |

Note that **Stripe's own two pages phrase it differently** — "can remove ... after
they're at least 24 hours old" (a floor on when pruning may begin) versus "keys
expire out of the system after 24 hours" (a ceiling on validity). These are not
the same statement. Both are quoted above rather than reconciled.

**The rule that generates all of these numbers** is: *retention must exceed the
client's maximum retry horizon.* If a client's retry policy can fire a final
attempt 36 hours after the first, and the server prunes at 24, the final retry
finds no record and **executes the operation a second time**. Stripe states the
consequence explicitly:

> We generate a new request if a key is reused after the original is pruned.

An expired key is not an error. It is *indistinguishable from a key never seen*,
and therefore silently executes. This is the single most dangerous property of the
whole mechanism, because the failure is invisible from both sides: the client
believes it retried idempotently, the server believes it received a new request,
and a second charge exists. The retention window and the client's retry schedule
are one design, and they are usually owned by two different teams.

Adyen's 7–14 days is interesting precisely because it is a *range* rather than a
number: the guarantee is a floor of 7 days, with actual pruning somewhere up to
14. A client should plan against the floor.

### 4.4 Non-deterministic handlers, and why replay is stored rather than recomputed

If the handler's response depends on anything that changes — current time, a
sequence number, a rate limit counter, a random ID — then "run it again and return
the same answer" is impossible. This is why every implementation **stores the
response body** rather than re-deriving it.

> Stripe's idempotency works by saving the resulting status code and body of the
> first request made for any given idempotency key.

The two exceptions are documented and deliberate. AIP-155:

> In some unusual situations, it may not be possible to return an identical
> success response. For example, a duplicate request to create a resource may
> arrive after the resource has not only been created, but subsequently updated
> [...] In this situation, the method may return the current state of the resource
> instead.

PayPal, which takes that option as its default:

> PayPal provides the status of a request at the current time and not the status
> of the original request.

And AWS, which is candid that even a "same effect" replay can differ in its
response envelope:

> Although multiple identical calls using the same client request token produce
> the same result on the server (no side effects), the responses to the calls
> might not be the same. If the `ReturnConsumedCapacity` parameter is set, then
> the initial `TransactWriteItems` call returns the amount of write capacity units
> consumed in making the changes. Subsequent `TransactWriteItems` calls with the
> same client token return the number of read capacity units consumed in reading
> the item.

— [AWS, `TransactWriteItems`](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html).

EC2 says the same in one sentence:

> With an idempotent request, if the original request completes successfully, any
> subsequent retries complete successfully without performing any further actions.
> However, the result might contain updated information, such as the current
> creation status.

All of which is RFC 9110 §9.2.2's caveat again, from the other end: idempotence is
about the effect on the server, "though the response might differ".

### 4.5 The crashed holder: what happens to an `IN_FLIGHT` record

If the server dies after claiming the key and before completing, the record sits
in `IN_FLIGHT` forever and the key is bricked — every retry gets a `409` and the
operation can never complete. So the in-flight state needs a **lease**, and every
real implementation has one.

Powertools:

> By default, we protect against concurrent executions with the same payload using
> a locking mechanism. However, if your Lambda function times out before
> completing the first invocation it will only accept the same request when the
> idempotency record expire.
>
> If a second invocation happens after this timestamp, and the record is marked as
> INPROGRESS, we will run the invocation again as if it was in the EXPIRED state.
> This means that if an invocation expired during execution, it will be quickly
> executed again on the next retry.

Brandur:

> ```
> # Only acquire a lock if the key is unlocked or its lock has expired
> # because the original request was long enough ago.
> if key.locked_at && key.locked_at > Time.now - IDEMPOTENCY_KEY_LOCK_TIMEOUT
> ```

and on the error path he releases it deliberately:

> For either type of error, we try to unlock the idempotency key before finishing
> so that another request has a chance to retry with it.

**This is exactly the lease-expiry hazard of §3.5, and it does not disappear
because the lease lives in your own database.** If the original holder was merely
paused rather than dead — a long GC pause, a stalled syscall, a delayed packet —
it can wake after the lease expires and complete its work alongside the second
attempt. The reason this is *tolerable* here and not in the Redlock case is that
the final commit of step (5) is itself conditional: the awakened holder's write
targets a record whose state it no longer owns, and a conditional update
(`UPDATE ... WHERE state = 'IN_FLIGHT' AND lease_id = ?`) rejects it. The lease is
an optimisation for liveness; the conditional write is what provides safety. Get
those two backwards and the lease becomes the safety mechanism, which is the
mistake Kleppmann is warning about.

**Nobody documents how long "in flight" may last.** Powertools ties it to the
Lambda timeout; Brandur uses a constant; Stripe, Adyen, PayPal and Square state
no figure. This is a genuine gap in the public record rather than an oversight in
this document — see §6.

### 4.6 Third-party side effects: why the atomic commit stops working

Step (5) of the lifecycle assumed the effect and the key record could commit
together. The moment the handler calls a *foreign* system, they cannot.

> To shore up our backend, it's key to identify where we're making **foreign state
> mutations**; that is, calling out and manipulating data on another system. This
> might be creating a charge on Stripe, adding a DNS record, or sending an email.

> The reason that the local vs. foreign distinction matters is that unlike a local
> set of operations where we can leverage an ACID store to roll back a result that
> we didn't like, once we make our first foreign state mutation, we're committed
> one way or another. We've pushed data into a system beyond our own boundaries and
> we shouldn't lose track of it.

— Brandur Leach, [brandur.org](https://brandur.org/idempotency-keys),
**practitioner writing**.

His structural answer is to break the handler into **atomic phases** separated by
foreign calls, and to record a **recovery point** after each:

> An **atomic phase** is a set of local state mutations that occur in transactions
> between foreign state mutations. We say that they're atomic because we can use an
> ACID-compliant database like Postgres to guarantee that either all of them will
> occur, or none will.

> Atomic phases should be safely committed **before** initiating any foreign state
> mutation. If the call fails, our local state will still have a record of it
> happening that we can use to retry the operation.

> A **recovery point** is a name of a check point that we get to after having
> successfully executed any atomic phase **or** foreign state mutation. Its purpose
> is to allow a request that's being retried to jump back to the point in the
> lifecycle just before the last attempt failed.

> All requests will initially get a recovery point of `started`, and after any
> request is complete (again, through either a success or definitive error) it'll
> be assigned a recovery point of `finished`.

The second half of the answer is that the foreign call must itself be idempotent,
which is why **you pass your own idempotency key downstream**:

> Some foreign state mutations are idempotent by nature (e.g. adding a DNS
> record), some are not idempotent but can be made idempotent with the help of an
> idempotency key (e.g. charge on Stripe, sending an email), and some operations
> are not idempotent, most often because a foreign service hasn't designed them
> that way and doesn't provide a mechanism like an idempotency key.

That third category is the hard one. If a downstream service offers no key, no
amount of care upstream makes the composite operation idempotent — which is the
end-to-end argument of §1.4 biting from the other direction. The honest options
are to make the call *observable* (query the downstream for whether your operation
happened, using a correlation ID you chose) or to accept at-least-once and
reconcile afterwards.

### 4.7 Which failures to store, and which to free the key

This is the most contested design point in the whole subject, and the sources
genuinely conflict.

**Store everything, including failures.** The IETF draft:

> The resource SHOULD respond with the result of the previously completed
> operation, success or an error.

Stripe:

> Stripe's idempotency works by saving the resulting status code and body of the
> first request made for any given idempotency key, regardless of whether it
> succeeds or fails. Subsequent requests with the same key return the same result,
> including 500 errors.

> As with user errors, the idempotency layer caches the result of POST mutations
> that result in server errors (specifically 500s, which are internal server
> errors), so retrying them with the same idempotency key usually produces the
> same result. The client can retry the request with a new idempotency key, but we
> advise against it because the original key may have produced side effects.

That last clause is the justification, and it is a good one: a 500 means the
outcome is **indeterminate**, so re-running under a *new* key risks a second
effect from an operation that may have half-succeeded.

**But not every failure gets stored.** Stripe carves out the ones that never
reached the handler:

> We save results only after the execution of an endpoint begins. If incoming
> parameters fail validation, or the request conflicts with another request that's
> executing concurrently, we don't save the idempotent result because no API
> endpoint initiates the execution. You can retry these requests.

and warns that the boundary is fuzzy:

> For a POST operation using an idempotency key, as long as an API method began
> execution, Stripe's API servers will cache the results of the request regardless
> of what they were. A request that returns a 400 sends back the same 400 if
> followed by a new request with the same idempotency key. Generate a fresh
> idempotency key when modifying the original request to get a successful result.
> This operation does contain some caveats. For example, a request that's rate
> limited with a 429 can produce a different result with the same idempotency key
> because rate limiters run before the API's idempotency layer. The same goes for
> a 401 that omitted an API key, or most 400s that sent invalid parameters. Even
> so, the safest strategy where 4xx errors are concerned is to always generate a
> new idempotency key.

So the operative principle is **not** "cache successes, free failures". It is:

> **Store the outcome of anything that may have had an effect. Free the key for
> anything that provably did not.**

A validation rejection, an auth failure, a rate-limit, and a concurrency conflict
all happen *before* the handler runs, so nothing happened, so the key stays
available. A 500 from inside the handler might have done anything, so it is
recorded.

Adyen classifies the same distinction as **transient** versus not, and signals it
in a header:

> The response will contain an HTTP header `transient-error` with the value
> `true`, which indicates that the request can be retried at a later time using
> the same idempotency key. If the API does not return a transient error header,
> or returns a header with a value of false, do not retry the request.

Stripe's equivalent is `Stripe-Should-Retry`, and its three-valued design is worth
noting because it admits ignorance:

> `Stripe-Should-Retry` set to true indicates that a client should retry the
> request. [...]
> `Stripe-Should-Retry` set to false means that a client should not retry the
> request because it won't have an additional effect.
> `Stripe-Should-Retry` not set in the response indicates that the API can't
> determine whether or not it can retry the request. Clients should fall back to
> other properties of the response (like the status code) to make a decision.

Neither header is in the IETF draft. Both exist because a status code alone is not
enough information, which is itself a comment on the draft's completeness.

### 4.8 A key gives you effectively-once *effect*, never exactly-once *execution*

This is the conceptual payoff, and it should be stated flatly.

The handler may run more than once. That is not a bug to be engineered away; it is
forced by §1.4 — the client cannot distinguish a lost request from a lost
response, so it must retry, and a retry may arrive after a crashed first attempt
left partial work behind. Van Steen's six orderings of `M`, `P`, `C` show there is
no protocol that avoids it.

What the key buys is that the *externally observable effect* occurs once. The
charge row exists once. The email is sent once — if the email provider honours a
key. The instance is launched once, within its region.

The distinction is not pedantic. It dictates that:

- **Handlers must be written to tolerate partial re-execution**, because they will
  get it. Anything done before the crash must be either rolled back by the
  transaction or made idempotent in its own right.
- **"Exactly-once" in vendor marketing means this**, not what it says. Kafka's own
  documentation is the model of honesty here: "Many systems claim to provide
  'exactly-once' delivery semantics, but it is important to read the fine print".
- **The composite is only as idempotent as its weakest foreign call** (§4.6).

Kafka's actual mechanism is the clearest statement of the pattern, because it
names both halves: at-least-once delivery on the wire, deduplication at the
receiver, producing the appearance of once.

> To achieve this, the broker assigns each producer an ID and deduplicates
> messages using a sequence number that is sent by the producer along with every
> message.

That is Birrell and Nelson's call identifier, Stripe's `Idempotency-Key`, AWS's
`ClientRequestToken`, PayPal's `PayPal-Request-Id` and Google's `request_id`. Five
names, one mechanism, and it has not changed since 1983.

### 4.9 Security, briefly

Three concerns, all first-party sourced.

**Low-entropy keys leak other clients' responses.** draft-07 §5, quoted in §4.2.
The mitigation is the composite lookup key — scope by account — plus validating
the key's format before using it as a lookup.

**Keys as injection vectors.** draft-07 §5:

> Injection attacks - When the resources does not validate the idempotency key in
> the client request and performs a idempotent cache lookup, there can be security
> attacks (primarily in the form of injection), compromising the server.

The remedy is stated as a positive obligation:

> * Establish a fixed format for the idempotency key and publish the key's
>   specification.
> * Always validate the key as per its published specification before processing
>   any request.

**Keys should not carry data.** Stripe:

> Avoid using sensitive data (for example, email addresses or personal
> identifiers) as idempotency keys.

Keys appear in logs, traces, error reports and support tickets. A key derived from
an email address puts that address in all of them. Note the tension with the
"derive the key from a user-attached object" strategy Stripe itself recommends —
derive from an *opaque internal id* like a cart ID, not from a natural identifier.

### 4.10 When not to use one

Worth stating because it is the most common misuse. A key is unnecessary where the
method already carries the guarantee. Stripe:

> All POST requests accept idempotency keys. Don't send idempotency keys in GET
> and DELETE requests because it has no effect. These requests are idempotent by
> definition.

Adyen:

> The Adyen API supports idempotency on POST requests (other request types such as
> GET, DELETE and PUT are idempotent by definition).

Both are appealing directly to RFC 9110 §9.2.2. A key on a `PUT` adds a row, a
lookup and a failure mode in exchange for a guarantee the method already makes.

The genuinely marginal case is `PATCH`, which is not idempotent in general but
often is in practice (a `PATCH` that sets fields to absolute values behaves like a
scoped `PUT`; one that increments does not). RFC 9110 §9.2.2's clause — "unless it
has some means to know that the request semantics are actually idempotent,
regardless of the method" — is what licenses treating such a `PATCH` as safe to
retry, and a key is how you would establish that for the ones that are not.

---

## 5. Sources

Fetched and read on 11 September 2026. Split by weight: a specification or a
vendor's own documentation is normative for that vendor's behaviour; practitioner
writing is argument and experience, and is labelled as such throughout the
document as well as here.

### Specifications and standards

| Source | Details | Used for |
| --- | --- | --- |
| [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) | Fielding, Nottingham & Reschke (eds.), IETF, STD 97, June 2022. Obsoletes RFC 2818, 7230–7233, 7235, 7538, 7615, 7694. | §9.2.1 safe methods; §9.2.2 the definition of idempotent and the retry rules; §9.3.3 POST; §15.5.10 409; §15.5.21 422. The normative definition the whole subject rests on. |
| [draft-ietf-httpapi-idempotency-key-header-07](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07) | Jena & Dalal, IETF HTTPAPI WG, Standards Track **Internet-Draft**, 15 October 2025, expires 18 April 2026. Confirmed current revision via the [datatracker document page](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/); no `-08` exists. | Header syntax, uniqueness, expiry, the idempotency fingerprint, client and resource responsibilities, enforcement, and the 400/422/409 error scenarios. **Not an RFC** — cite as work in progress. |
| [RFC 9651: Structured Field Values for HTTP](https://www.rfc-editor.org/rfc/rfc9651.txt) | Nottingham & Kamp, IETF, September 2024. Obsoletes RFC 8941. | Establishing that the draft's normative reference to RFC 8941 is stale. |
| [AIP-155: Request identification](https://google.aip.dev/155) | Google API Improvement Proposals. State "Approved", created 2019-05-06, changelog entries through 2024-01-08. | The vendor-neutral RPC formulation; the MUST/SHOULD bullets on `request_id`; the "return the previous successful response" rule; the stale-success escape hatch; the deliberate refusal to specify a retention window. |
| [PostgreSQL 17 documentation — `INSERT`](https://www.postgresql.org/docs/17/sql-insert.html) | The PostgreSQL Global Development Group. | The `ON CONFLICT` atomicity guarantee "even under high concurrency" — the primary-source basis for mechanism A. |
| [PostgreSQL 17 documentation — Transaction Isolation](https://www.postgresql.org/docs/17/transaction-iso.html) | As above. | The definition of `SERIALIZABLE`, backing mechanism B. |

### Papers and textbooks

| Source | Details | Used for |
| --- | --- | --- |
| [*Linear Associative Algebra*](https://archive.org/details/linearassocalgeb00pierrich) | Benjamin Peirce. Lithographed and privately circulated 1870; printed as an extract from *The American Journal of Mathematics*; New Edition with addenda and notes by C. S. Peirce, D. Van Nostrand, New York, 1882. §25, p. 8. | The original definition of "idempotent", and its preface verifying the 1870 date and that the printed text follows the lithograph "with only slight verbal changes". |
| [*Implementing Remote Procedure Calls*](http://www.bitsavers.org/pdf/xerox/parc/techReports/CSL-83-7_Implementing_Remote_Procedure_Calls.pdf) | Andrew D. Birrell & Bruce Jay Nelson. Xerox PARC CSL-83-7, December 1983. Published as ACM *Transactions on Computer Systems* 2(1), February 1984, pp. 39–59. | "Either once or not at all — the user is not told which": the canonical statement of the ambiguous failure. Also the **call identifier**, the direct ancestor of the idempotency key, and its five-minute retention. |
| [*End-to-End Arguments in System Design*](https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.txt) | J. H. Saltzer, D. P. Reed & D. D. Clark. ACM *TOCS* 2(4), November 1984, pp. 277–288; revised from the Second International Conference on Distributed Computing Systems, Paris, April 1981. | "Suppression must be accomplished by the application itself with knowledge of how to detect its own duplicates" — why the key must be client-generated and why no lower layer can substitute. |
| [*Distributed Systems*, 4th ed. — Chapter 8, Fault Tolerance](https://www.distributed-systems.net/index.php/books/ds4/) | Andrew S. Tanenbaum & Maarten van Steen, 2023. Quoted from the **author-published companion slide set** (`allslides.zip`) at distributed-systems.net, not the book body — see §6. | At-least-once vs at-most-once semantics; "it cannot decide whether this is caused by a lost request, a crashed server, or a lost response"; the six M/P/C orderings showing transparent recovery is impossible. |

### First-party vendor documentation

| Source | Details | Used for |
| --- | --- | --- |
| [Stripe API reference — Idempotent requests](https://docs.stripe.com/api/idempotent_requests) | Stripe. No version stamp on the section. | Key generation and the 255-char limit; saving status code and body; the ≥24-hour pruning language; "we save results only after the execution of an endpoint begins" and the concurrent-conflict rule. |
| [Stripe — Advanced error handling](https://docs.stripe.com/error-low-level) | Stripe. No version stamp. | The content/network/server error taxonomy; `Idempotent-Replayed: true`; `Stripe-Should-Retry`; 409 Conflict; which 4xx/5xx are retryable; the flat "keys expire out of the system after 24 hours". |
| [Adyen — API idempotency](https://docs.adyen.com/development-resources/api-idempotency/) | Adyen. No date stamp. | 64-char key; company-account and per-region scope; the 7–14 day validity range; error 704 returned as 422 **or** 409; the `transient-error` header; error 703 when the idempotency store is unavailable. |
| [PayPal — Idempotency](https://developer.paypal.com/api/rest/reference/idempotency/) | PayPal. Page states "Last updated: August 11, 2026". | `PayPal-Request-Id`; the 38-character limit; per-API-call-type scope; "returns the latest status of the previous request"; "processes the first request and might fail the second request"; no global retention window. |
| [Square — CreatePayment](https://developer.squareup.com/reference/square/payments-api/create-payment) and [Idempotency](https://developer.squareup.com/docs/build-basics/common-api-patterns/idempotency) | Square. No date stamps. | `idempotency_key` as a body field; min 1 / max 45 characters and the multi-byte caveat; replay-returns-first-response; the hedged same-key-different-body behaviour. |
| [AWS — Ensuring idempotency in Amazon EC2 API requests](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Run_Instance_Idempotency.html) | Amazon Web Services. | The client-token model; 64 ASCII characters (corroborated at [`RunInstances`](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RunInstances.html)); `IdempotentParameterMismatch`; **regional vs zonal** scope; "the result might contain updated information". |
| [AWS — Working with items and attributes in DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html) | Amazon Web Services. | "All these operations are atomic"; conditional writes and their evaluation against the most recent version; `ConditionalCheckFailedException`; the retry-a-conditional-write-after-a-network-error example. |
| [AWS — `PutItem` API reference](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_PutItem.html) and [Condition and filter expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html) | Amazon Web Services. | `attribute_not_exists(<partition key>)` as the insert-if-absent idiom; the formal function definition. |
| [AWS — `TransactWriteItems`](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html) and [DynamoDB Transactions: How it works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html) | Amazon Web Services. | `ClientRequestToken`; max length 36; the **10-minute** idempotency window (stated on both pages); `IdempotentParameterMismatch`; the admission that responses to replays may differ. |
| [Powertools for AWS Lambda (Python) — Idempotency](https://docs.powertools.aws.dev/lambda/python/latest/utilities/idempotency/) | Amazon Web Services, channel `latest`. Source constants from `aws_lambda_powertools/utilities/idempotency/persistence/{datarecord,dynamodb}.py`. | A complete first-party reference implementation: conditional `PutItem` to claim the key, the three-clause condition expression, `IdempotencyItemAlreadyExistsError` / `IdempotencyAlreadyInProgressError`, `INPROGRESS`/`COMPLETED`/`EXPIRED`, the 1-hour default expiry, and the in-progress lease. |
| [Redis — `SET`](https://redis.io/docs/latest/commands/set/) and [Transactions](https://redis.io/docs/latest/develop/using-commands/transactions/) | Redis. `SET` available since 1.0.0; `NX` since 2.6.12. | `NX` semantics and the null-reply signal on losing the race; the serialisation guarantee (which is on the transactions page, **not** the `SET` page). |
| [Redis — Distributed Locks with Redis](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/) | Redis. Live URL as of September 2026; the older `redis.io/topics/distlock` now redirects to the docs index. | The Redlock algorithm, its three claimed properties, the single-instance recipe, and — most importantly — the "Disclaimer about consistency" conceding that fencing tokens should be implemented and that Redis does not use a monotonic clock for TTL. |
| [Apache Kafka — Message Delivery Semantics](https://kafka.apache.org/documentation/#semantics) | Apache Software Foundation. Quoted from the docs source at [`docs/design/design.md`](https://github.com/apache/kafka/blob/trunk/docs/design/design.md). | The three delivery semantics; "read the fine print" on exactly-once claims; the producer ID + sequence number deduplication mechanism as an idempotency key by another name. |

### Practitioner writing

Argued from experience rather than normative. Useful and often more detailed than
the specifications, but a claim here does not carry a specification's weight.

| Source | Details | Used for |
| --- | --- | --- |
| [Designing robust and predictable APIs with idempotency](https://stripe.com/blog/idempotency) | Brandur Leach, Stripe blog, 22 February 2017. | The three-way taxonomy of network failures and the ambiguous-failure framing; exponential backoff, jitter and the thundering herd. |
| [Implementing Stripe-like Idempotency Keys in Postgres](https://brandur.org/idempotency-keys) | Brandur Leach, 27 October 2017. | Foreign state mutations, atomic phases and recovery points; a concrete key-record schema; the `UNIQUE (user_id, idempotency_key)` + `SERIALIZABLE` + `locked_at` serialisation mechanism; the ~72-hour retention recommendation. The most detailed public account of the mechanism. |
| [How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) | Martin Kleppmann, 8 February 2016. Author of *Designing Data-Intensive Applications*; the post arose from research for it. | The efficiency-vs-correctness distinction; why a lease can expire while its holder still runs (GC pauses, page faults, the 90-second GitHub network delay); fencing tokens; the critique of Redlock. |
| [Is Redlock safe?](http://antirez.com/news/101) | Salvatore Sanfilippo (antirez), February 2016 (page carries only a relative timestamp). | The counter-case: why fencing tokens presuppose a linearizable store, why a unique token plus check-and-set is the practical equivalent, the clock re-check argument, and his concession on monotonic clocks. |

---

## 6. What could not be verified

Stated plainly, because a confident sentence with nothing behind it is the one
failure this document should not contain.

1. **The EC2 client-token idempotency window is not documented anywhere I could
   find.** The [EC2 idempotency
   page](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/Run_Instance_Idempotency.html),
   its developer-guide mirror and the `RunInstances` API reference were fetched
   and searched for any duration wording; there is none. Figures circulating for
   this are not sourced here, and this document states no EC2 window. By contrast,
   DynamoDB's 10 minutes *is* documented, on two pages, and is stated.

2. **EC2 documents no behaviour for a retry arriving while the first request is
   still in flight.** Its retry-guidance table covers completed requests only.
   Square documents nothing on the concurrent case either. Both are recorded as
   silences in §3.8 rather than filled in.

3. **No vendor documents how long "in flight" may last** before the claim is
   considered stale. Powertools ties it to the Lambda timeout and Brandur uses a
   configurable constant, but Stripe, Adyen, PayPal and Square state no figure.
   §4.5 says so explicitly.

4. **Kleppmann's *Designing Data-Intensive Applications* is not quoted.** No
   verifiable public copy was available to quote from in this session, so nothing
   is attributed to it. His blog post, which is his own writing and publicly
   readable, is used instead and labelled as practitioner writing.

5. **Tanenbaum & van Steen is quoted from the author's companion slides, not the
   book body.** The 4th edition PDF is distributed free but only via a
   personalised email link, which was not used. The slide set (`allslides.zip`) is
   downloadable without any form from
   [distributed-systems.net](https://www.distributed-systems.net/index.php/books/ds4/)
   and is authored by van Steen, so the quotations in §1.4 are his words — but
   they are slide text for Chapter 8, not the chapter prose, and are cited that
   way.

6. **Peirce's §25 wording is verified against the 1882 printing, not the 1870
   lithograph.** The 1870 scan is a handwritten facsimile whose OCR is unusable.
   The 1882 preface states that the body "has been printed directly from the
   lithograph with only slight verbal changes", which is good evidence but is not
   the same as reading the 1870 text.

7. **antirez's post carries no absolute date** — only a relative timestamp. It is
   cited as February 2016, computed from that timestamp and corroborated by his
   description of Kleppmann's post (8 February 2016) as having appeared
   "yesterday".

8. **Bernstein & Newcomer on transaction processing was not consulted.** It was on
   the candidate list; no verifiable public copy was reachable, so it contributes
   nothing here and is not listed as a source.

9. **`Idempotent-Replayed` is Stripe-only and appears on one Stripe page.** It is
   documented on the error-handling page, not on the API reference for idempotent
   requests, and it is absent from the IETF draft. Treated as a vendor extension,
   not a convention.

10. **Square's key retention window and its exact error code for a payload
    mismatch are not documented** on either of the two pages consulted. §4.1 and
    §4.3 record the absence rather than supplying a number.
