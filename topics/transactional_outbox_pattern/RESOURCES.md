# Transactional Outbox Resources

## Knowledge

### The pattern itself

- [Pattern: Transactional outbox — Chris Richardson][outbox]
  The canonical statement of the pattern, in Alexandrian pattern form (context
  / problem / forces / solution / resulting context). **Use for:** the
  vocabulary interviewers expect, and the explicit list of forces that rule out
  2PC.

- [Pattern: Polling publisher — microservices.io][polling]
  One of the two ways to get messages *out* of the outbox. Names the key
  drawback verbatim: "Tricky to publish events in order." **Use for:** the
  relay half of the pattern, and the polling-vs-CDC argument.

- [Pattern: Transaction log tailing — microservices.io][tailing]
  The other way out: tail the WAL. Benefits "No 2PC / Guaranteed to be
  accurate"; drawbacks "Requires database specific solutions / Tricky to avoid
  duplicate publishing." **Use for:** the CDC side of the same argument.

- [Life beyond Distributed Transactions — Pat Helland, CIDR 2007][helland]
  The intellectual ancestor. Argues that at scale you give up distributed
  transactions and build on *entities* plus *at-least-once messaging with
  idempotence*. **Use for:** the "why is 2PC off the table at all" question,
  and for sounding like you have read the field rather than a blog post.

### Postgres primitives

- [PostgreSQL docs: SELECT — The Locking Clause][pgselect]
  Primary source for `FOR UPDATE`, `NOWAIT`, and `SKIP LOCKED`. Contains the
  sentence worth memorising: *"Skipping locked rows provides an inconsistent
  view of the data, so this is not suitable for general purpose work, but can
  be used to avoid lock contention with multiple consumers accessing a
  queue-like table."* **Use for:** the relay's claim query, and for explaining
  exactly why `SKIP LOCKED` is safe *here* and nowhere else.

  Two further sentences from the same section, both verified 2026-09-10 and
  both used in Lesson 02: *"It is possible for a `SELECT` command running at the
  `READ COMMITTED` transaction isolation level and using `ORDER BY` and a
  locking clause to return rows out of order. This is because `ORDER BY` is
  applied first."* And: *"If a `LIMIT` is used, locking stops once enough rows
  have been returned to satisfy the limit (but note that rows skipped over by
  `OFFSET` will get locked)."* The first is the seed of the ordering lesson; the
  second is why an outbox must never paginate with `OFFSET`.

- [PostgreSQL docs: NOTIFY][pgnotify]
  The primary source for waking the relay without a replication slot, read
  2026-09-10 to promote Lesson 04's sidenote into a real section. The sentence
  that makes it safe: *"if a `NOTIFY` is executed inside a transaction, the
  notify events are not delivered until and unless the transaction is
  committed."* Three more worth having: identical channel+payload signals
  inside one transaction collapse to *"only one instance of the notification
  event"*; the payload *"must be shorter than 8000 bytes"*; and *"If this
  queue becomes full, transactions calling `NOTIFY` will fail at commit"* —
  which puts the failure on the business write, not the relay. **Use for:**
  the latency floor argument, and for why the fallback timer stays.

- [PostgreSQL docs: Concurrency Control (Ch. 13)][pgmvcc]
  Isolation levels and row-level locks. **Use for:** grounding claims about
  what a transaction does and does not see. §13.3.2 is the citation for lock
  duration — *"Row-level locks are released at transaction end or during
  savepoint rollback"* — and for the fact that claiming is not free: *"locking a
  row might cause a disk write, e.g., `SELECT FOR UPDATE` modifies selected rows
  to mark them locked."*

- [PostgreSQL docs: Sequence Manipulation Functions][pgseq]
  **Use for:** the high-water-mark cursor trap. *"the value obtained by
  `nextval` is not reclaimed for re-use if the calling transaction later
  aborts… PostgreSQL sequence objects cannot be used to obtain 'gapless'
  sequences."* Gaps are the documented half; the unpublished-but-lethal half is
  that `nextval` fires at insert rather than at commit, so id order is not
  commit order.

- [PostgreSQL docs: Logical Decoding Concepts (§47.2)][pglogical]
  The primary source for the CDC half of Lesson 04, and the page supplying both
  the argument for log tailing and the argument against it. At-least-once, from
  the horse's mouth: *"A logical slot will emit each change just once in normal
  operation. The current position of each slot is persisted only at checkpoint,
  so in the case of a crash the slot might return to an earlier LSN, which will
  then cause recent changes to be sent again when the server restarts."* And the
  liability: *"Replication slots persist across crashes and know nothing about
  the state of their consumer(s). They will prevent removal of required
  resources even when there is no connection using them… In extreme cases this
  could cause the database to shut down to prevent transaction ID wraparound. So
  if a slot is no longer required it should be dropped."*

- [PostgreSQL docs: Logical Decoding Output Plugins (§47.6)][pgplugin]
  **Use for:** the one guarantee polling cannot buy — *"Concurrent transactions
  are decoded in commit order, and only changes belonging to a specific
  transaction are decoded between the `begin` and `commit` callbacks."* Also
  *"Aborted transactions and their contents never get decoded"*, which is a wash
  against polling rather than an advantage, so do not over-claim it.

- [PostgreSQL docs: WAL configuration][pgwalconf] and
  [Replication configuration][pgreplconf]
  The cost side. `wal_level`: *"Finally, `logical` adds information necessary to
  support logical decoding… This parameter can only be set at server start"*,
  and it *"will increase the WAL volume."* `max_slot_wal_keep_size`: *"If
  `max_slot_wal_keep_size` is -1 (the default), replication slots may retain an
  unlimited amount of WAL files. Otherwise… the standby using the slot may no
  longer be able to continue replication due to removal of required WAL
  files."* Fill the disk, or break the slot.

- [PostgreSQL docs: Explicit Locking §13.3.5 — Advisory Locks][pgadvisory]
  **Use for:** the ordering lesson's rejected design, and for the
  vocabulary. *"PostgreSQL provides a means for creating locks that have
  application-defined meanings. These are called advisory locks, because the
  system does not enforce their use — it is up to the application to use them
  correctly."* On lifetime: *"Transaction-level lock requests… are automatically
  released at the end of the transaction, and there is no explicit unlock
  operation."* That lifetime is what makes them unusable inside a claim query —
  see the measured-results gap below.

- [PostgreSQL docs: Advisory Lock Functions §9.28.10][pgadvfn]
  The function reference. `pg_try_advisory_xact_lock` *"Obtains an exclusive
  transaction-level advisory lock if available. This will either obtain the lock
  immediately and return `true`, or return `false` without waiting if the lock
  cannot be acquired immediately."* And the key space: *"identified either by a
  single 64-bit key value or two 32-bit key values (note that these two key
  spaces do not overlap)."*

- [PostgreSQL docs: Routine Vacuuming (§24.1)][pgvacuum]
  **Use for:** why an outbox bloats, and why the obvious cleanup does not fix
  it. The mechanism: *"an `UPDATE` or `DELETE` of a row does not immediately
  remove the old version of the row… The space it occupies must then be
  reclaimed for reuse by new rows, to avoid unbounded growth of disk space
  requirements."* The sentence that condemns a retention `DELETE`: plain
  `VACUUM` *"will not return the space to the operating system, except in the
  special case where one or more pages at the end of a table become entirely
  free and an exclusive table lock can be easily obtained"* — and a retention
  job frees pages at the front. `VACUUM FULL` does return it but *"requires an
  `ACCESS EXCLUSIVE` lock on the table it is working on, and therefore cannot be
  done in parallel with other use of the table."*

- [PostgreSQL docs: Table Partitioning (§5.12)][pgpartition]
  **Use for:** the retention design that removes the work instead of scheduling
  it. *"Dropping an individual partition using `DROP TABLE`, or doing `ALTER
  TABLE DETACH PARTITION`, is far faster than a bulk operation. These commands
  also entirely avoid the `VACUUM` overhead caused by a bulk `DELETE`."* The
  cost, which bounds how fine you can partition: *"Too many partitions can mean
  longer query planning times and higher memory consumption during both query
  planning and execution"*, with the planner *"generally able to handle
  partition hierarchies with up to a few thousand partitions fairly well."*

- [Pattern: Idempotent consumer — microservices.io][idempotent]
  The consumer half of the pattern, and the source of the exact key an
  interviewer expects: *"Make a consumer idempotent by having it record the IDs
  of processed messages in the database… Since the `(subscriberId, messageID)`
  is the table's primary key the `INSERT` will fail if the message has been
  already processed successfully."* **Use for:** the inbox table, and for
  justifying the composite key.

### RabbitMQ (the broker, pinned 2026-09-10)

- [RabbitMQ: Consumer Acknowledgements and Publisher Confirms][rmqconfirms]
  **The single highest-value page in this topic** — both halves of the delivery
  guarantee are specified here. No core deduplication at all, and the docs put
  the burden on you explicitly: *"consumers must be prepared to handle
  redeliveries and otherwise be implemented with idempotence in mind."* The
  `redelivered` caveat: *"a consumer can receive a message that was previously
  delivered to another consumer."* Auto-ack: *"should be considered unsafe."*
  Prefetch: *"the max number of unacknowledged deliveries that are permitted on
  a channel"*, with *"values in the 100 through 300 range"* suggested. And the
  trap — *"For unroutable messages, the broker will issue a confirm once the
  exchange verifies a message won't route to any queue."*

- [RabbitMQ: Publishers][rmqpublishers]
  The other half of the unroutable trap: *"the publisher set the `mandatory`
  message property to `false` (this is the default), the message is discarded."*
  Also the retry guidance that the outbox exists to make safe: *"Messages that
  were not confirmed should be considered undelivered after a period of time.
  Those messages can be republished if it's safe to do so for the
  application."*

- [RabbitMQ: Queues][rmqqueues]
  **The primary source for Lesson 05**, and unusually honest about its own
  limits. The guarantee: *"A queue is an ordered collection of messages
  providing FIFO semantics"* and *"When publishing on a single channel, messages
  are enqueued in publishing order in every queue they are routed to"* — note
  the scope, one channel, which two relay workers void. Then the "When messages
  can be reordered" section: *"Multiple active consumers on the same queue: the
  broker still dequeues in FIFO, but any redelivery can change order."* And the
  remedy, under "Preserving message order": use a stream, or *"use a queue with
  a single active consumer."*

- [RabbitMQ: Consumers][rmqconsumers]
  **Use for:** single active consumer, and the caveat that makes it
  insufficient on its own. *"Single Active Consumer (SAC) makes it possible to
  only have one consumer at a time consuming from a queue. If the active
  consumer is cancelled or disconnects, another registered consumer takes its
  place."* Enabled with `x-single-active-consumer`, supported on classic and
  quorum queues; an AMQP 0-9-1 client attempting it on a stream *"will not
  work."* The sentence that stops people over-claiming it: *"once dispatched,
  concurrent processing of deliveries will result in a natural race condition
  between the threads doing the processing."*

- [RabbitMQ: Quorum Queues][rmqquorum]
  **The primary source for Lesson 06.** Poison-message handling and the DLQ
  story. *"Quorum queues keep track of the number of unsuccessful (re)delivery
  attempts and expose it in the 'x-delivery-count' header."* *"Starting with
  RabbitMQ 4.0, the delivery limit for quorum queues defaults to 20."* *"When a
  message has been redelivered more times than the limit the message will be
  dropped (removed) or dead-lettered (if a DLX is configured)."* On disabling
  it: *"The value of `-1` disables the limit altogether. It is not recommended
  that users disable this limit as repeated requeues can threaten the stability
  of a queue or RabbitMQ cluster."* And the sentence that makes the DLX unsafe
  by default: *"`at-most-once` remains the default dead-letter-strategy for
  quorum queues"*, against *"Quorum queues support a safer form of
  dead-lettering that uses `at-least-once` guarantees for the message transfer
  between queues."*

  **Re-read 2026-09-10, and it overturned a claim Lesson 06 was making.** The
  page distinguishes *which* returns the counter counts. It increments for
  *"`reject`, AMQP 1.0 `modify` with `delivery_failed=true`, or channel
  termination with pending messages"* — but *"Unlimited explicit returns (via
  `nack` or AMQP 1.0 `modify` with `delivery_failed=false`) are allowed
  **without counting toward the delivery limit**."* Confirmed by measurement
  (fourth round, below): 12 polite nacks against a limit of 3 and still
  cycling. **Use for:** the correction in Lesson 06, and as the reason
  `reject` and `nack` are not interchangeable in a consumer's error handler.

- [RabbitMQ: Dead Letter Exchanges][rmqdlx]
  **Use for:** what happens to a message you give up on. Four dead-letter
  conditions, of which the last is ours: *"The message is returned more times to
  a quorum queue than the delivery-limit."* The triage data: an `x-death` header
  array carrying queue, reason, count, time and routing keys, *"ordered by
  recency, that is the most recent dead-lettering event is recorded in the first
  array element."* The warning worth volunteering in an interview:
  *"Dead-lettered messages are re-published without publisher confirms turned on
  internally. Therefore using DLX in a clustered RabbitMQ environment is not
  guaranteed to be safe. Messages can be lost if the target queue is not
  available to accept messages."* And on configuration: *"Hardcoded x-arguments
  are strongly recommended against since they cannot be updated without
  redeploying applications and deleting the queue before it can be redeclared,
  while policies can be updated at any moment."* Cycle protection exists but has
  an escape clause: *"RabbitMQ will detect a cycle and drop the message if there
  was no rejection in the entire cycle."*

- [aio-pika — Publisher Confirms tutorial][aiopika]
  The async client for the SQLAlchemy-async stack. Confirms are on by default
  (`publisher_confirms=True`), `exchange.publish()` returns the confirmation,
  and the documented pattern checks `isinstance(confirmation, Basic.Ack)` and
  catches `DeliveryError` / `TimeoutError`. **Caveat:** the default value of
  `mandatory` was *not* verified — lesson code sets it explicitly.

### Other brokers — contrast only

Kept for interview breadth, not for the worked example. The unifying finding:
each deduplicates the **publish**, inside a **time window** shorter than a real
outage, and none deduplicates redelivery.

- [Exactly-once processing in Amazon SQS][sqsfifo]
  `MessageDeduplicationId` over a five-minute interval: *"If you retry the
  `SendMessage` action within the 5-minute deduplication interval, Amazon SQS
  doesn't introduce any duplicates into the queue."* Note the verb — *sends*.

- [Amazon SQS standard queues][sqsstandard]
  The contrast case, and duplicates as documented behaviour rather than
  failure: *"Standard queues ensure at-least-once message delivery, but due to
  the highly distributed architecture, more than one copy of a message might be
  delivered, and messages may occasionally arrive out of order."*

- [NATS JetStream: Streams][natsstreams]
  `Nats-Msg-Id` with a two-minute default window: *"For two minutes after a
  message is stored, the server turns away a second message that carries the
  same `Nats-Msg-Id` header."*

### Production implementations to read

- [Debezium: Outbox Event Router][debezium]
  The reference log-tailing (CDC) implementation. Shows the *shape* a
  battle-tested outbox table takes: `id uuid`, `aggregatetype`, `aggregateid`,
  `type`, `payload jsonb` — aggregate type selects the topic, aggregate id
  becomes the message key (hence per-aggregate ordering), and the table is
  treated as append-only: inserts only, deletes filtered out, updates a
  configuration error. **Use for:** designing the table columns, and for the CDC
  option even though our broker is queue-based.
  **Sourcing, resolved 2026-09-10.** debezium.io still returns 403 to the fetch
  tool, but the doc *source* is public AsciiDoc — see [the router page in the
  repo][dbzoutboxsrc] — and it confirms both claims verbatim: *"The SMT
  automatically filters out `DELETE` operations on an outbox table"* and *"All
  changes in an outbox table are expected to be `INSERT` operations. That is, an
  outbox table functions as a queue; updates to records in an outbox table are
  not allowed."* Quote either with confidence.

- [Debezium Server: sink types][dbzserver]
  Read 2026-09-10 to answer "could we run Debezium without Kafka and point it
  at RabbitMQ?". The sinks are Kinesis, Google Cloud Pub/Sub, Pub/Sub Lite,
  HTTP Client, Pulsar, Azure Event Hubs, Redis Streams, NATS Streaming, NATS
  JetStream, Apache Fluss, Apache Kafka, Pravega, Infinispan. **RabbitMQ is not
  one of them.** **Use for:** closing the CDC-versus-polling argument for this
  stack in a single sentence — the cheap escape hatch does not exist, so CDC
  here means adopting Kafka or building and operating a bridge.

- [Debezium: PostgreSQL connector][dbzpostgres]
  **Use for:** what operating CDC is actually like. The section titled "WAL disk
  space consumption" is the honest summary: a quiet captured database sharing a
  server with a busy one never advances its slot, so WAL grows anyway; idle AWS
  RDS instances hit the same thing via invisible system-table writes. The fix is
  manufactured traffic — `heartbeat.interval.ms` plus `heartbeat.action.query`
  and a heartbeat table added to the publication. Same 403 caveat as above.

## Wisdom (Communities)

Not yet discussed with Ayman — candidates to propose when a question comes up
that needs real-world calibration rather than a documented answer:

- r/ExperiencedDevs and r/softwarearchitecture — for "did you actually run this
  in prod" sanity checks on relay design.
- The Debezium community (Zulip) — highest concentration of people who have
  operated outbox-at-scale.

## Gaps

- **No high-trust Python-specific source yet.** The SQLAlchemy 2.0 async docs
  cover session mechanics, and aio-pika's docs cover confirms, but nobody
  authoritative has written the outbox in that stack. Lesson code is derived
  from the pattern + primary docs, not copied. ~~The **Python** has still never
  been executed~~ — closed 2026-09-10 by Lesson 07, which runs producer, relay
  and consumer as real processes against containers. The *source* gap stands:
  there is still no authoritative reference implementation in this stack, only
  a working one of our own, since deleted at Ayman's instruction. What it
  produced is transcribed in `evidence/`.
- ~~**No strong source yet on queue-broker specifics.**~~ Closed 2026-09-10 —
  see "Queue brokers" above. Remaining sub-gap: none of the three docs states a
  redelivery *rate* in practice, so the lesson argues from mechanism rather than
  from measured duplicate volume.
- **No measured numbers** on where a polling relay stops scaling. Blog posts
  claim ~10k jobs/min; unverified, do not repeat as fact. Lesson 04 leans on
  this gap when it says polling's latency floor is a reason to *revisit* the
  decision — there is no number attached to "outgrow". **Partly closed
  2026-09-10:** the *latency* half now has measured numbers (third round
  below). The *throughput ceiling* half is still open.
- **First measured results in this workspace**, obtained 2026-09-10 against
  PostgreSQL 17.11 in Docker while writing Lesson 05. Three findings, all
  reproducible, none of them from a doc:
    1. `pg_try_advisory_xact_lock` in a claim query's `WHERE` is evaluated on
       every candidate row, not just the returned ones. `EXPLAIN ANALYZE` with
       `LIMIT 1` over a six-row backlog: `Bitmap Heap Scan … actual rows=6`
       under `Filter: pg_try_advisory_xact_lock(...)`, two advisory locks held,
       one row returned. A concurrent second worker claimed **zero** rows.
    2. Sequence order really does diverge from commit order: a row inserted
       first by a slow transaction became visible *second*, and a poll in the
       gap saw only the later event. This confirms Lesson 02's trap by
       observation rather than by inference from the `nextval` docs.
    3. The fix is the aggregate row lock. With an `UPDATE orders …` before the
       outbox insert, the second transaction waited on
       `Lock / transactionid` and ids came out in commit order. This is the
       mechanism Lesson 05 is built on.
  The container was removed afterwards; the SQL is reproducible from the
  lesson. Nothing here supersedes a doc — treat it as measurement, and re-run
  before quoting on a different major version.

- **Second measured round**, obtained 2026-09-10 for Lesson 06, same
  PostgreSQL 17.11 image. Five findings:
    1. **A poison row at the head of a shard stops the shard.** With
       `ORDER BY id` and no attempt filter, consecutive polls return the
       identical two rows. `SKIP LOCKED` does not help — it skips rows another
       transaction holds *at that instant*, and nobody holds the row between
       attempts.
    2. **The obvious fix reintroduces Lesson 05's bug.** With
       `AND attempts < 10`, the relay would publish `shipped` for the aggregate
       whose `paid` was skipped, while the healthy aggregate published
       `paid -> shipped`. The correct unit to skip is the aggregate, not the
       row; a `NOT EXISTS` anti-join on the same fixture drained the healthy
       aggregate and published nothing for the poisoned one.
    3. **The `published_at` update doubles the heap.** 200,000 rows: 52 MB of
       heap after insert, **106 MB** after one `UPDATE` each. Then deleting 91%
       of rows and running a plain `VACUUM` left the total relation size
       unchanged at **119 MB** for 17,996 live rows. `VACUUM FULL` took it to
       24 kB.
    4. **Bloat is invisible to every latency metric.** On that 106 MB table the
       claim query touched **104 buffers** and the per-shard lag query
       **13** — both scan only the backlog through the partial index. This is
       the reason bloat is found by a full disk rather than by an alert.
    5. **Partitioning is close to free for the claim query, and much cheaper
       for retention.** `DROP TABLE` on a 60 MB / 200k-row daily partition:
       **9 ms**, no vacuum, space returned. The equivalent `DELETE` plus the
       `VACUUM` it requires: **122 ms + 29 ms**, space not returned. On
       identical data (200k rows, 500 unpublished) the claim query cost **203
       buffers partitioned versus 202 flat**, gaining a `Merge Append` over
       each partition's local partial index (both children verified
       `indpred IS NOT NULL`). Do not quote the ratios — small fixture. Quote
       the shapes: `DELETE` is linear in rows and makes dead tuples, `DROP` is
       an unlink and makes none.

- **Third measured round — the first that runs Python**, 2026-09-10 for
  Lesson 07. Postgres 17.11 and RabbitMQ 4.3.5 (Erlang 27) in Docker; Python
  3.13, SQLAlchemy 2.0.52, asyncpg 0.31.0, aio-pika 10.0.1. Producer, relay and
  consumer as three real processes. Five findings:
    1. **The pipeline works end to end.** Business commit → broker confirm →
       consumer side effect in **166 ms**, most of it the poll wait.
    2. **The crash window is real and it produces a duplicate.** `SIGKILL`
       between the confirm and the `published_at` update leaves the row
       `unpublished=t` while the consumer already holds one inbox row and one
       shipment. The restarted relay re-claims and republishes; the inbox
       absorbs it. Final state: **two deliveries, one shipment.**
    3. **The duplicate arrives with `redelivered=False`.** To the broker it is a
       fresh publish of a message it has never seen — `message_id` is an
       application property RabbitMQ attaches no meaning to. A consumer that
       deduplicates only when `redelivered` is true is silently broken. This is
       the sharpest finding of the round and is not stated in any doc read so
       far.
    4. **Same crash, no outbox, permanent loss.** Committing the order and then
       publishing, killed in between: order committed, no message anywhere,
       nothing to retry. Two orders paid, one shipment. Lesson 01's argument,
       measured.
    5. **Two unsharded relays over 500 rows: 500 confirms, not 501.** Split
       200 / 300, zero duplicate shipments — `SKIP LOCKED` under real
       concurrency. Says nothing about *order*; the relays were unsharded on
       purpose.
  And the latency shape, 120 events trickled one per 50 ms, commit to
  consumer commit:

  | Poll interval | p50 | p95 | max |
  |---|---|---|---|
  | 50 ms | 34 ms | 63 ms | 74 ms |
  | 200 ms | 118 ms | 216 ms | 220 ms |
  | 1 s | 558 ms | 1007 ms | 1040 ms |

  **p50 is half the poll interval and p95 is the poll interval**, at every
  setting — uniform arrivals against a fixed cycle. Publish and consume are
  single-digit milliseconds and vanish into the noise. Quote the shape, which
  is arithmetic and portable; do not quote the milliseconds, which are one
  laptop with no network. A first attempt at this sweep was contaminated by
  orphaned relay processes (`uv run` leaves the child alive when the parent is
  killed) and reported 1 s and 200 ms as identical — re-run against direct
  interpreter PIDs before trusting any repeat.

- ~~**How Debezium reaches RabbitMQ is unverified.**~~ **Closed 2026-09-10.**
  Debezium Server's sink list is Kinesis, Google Cloud Pub/Sub, Pub/Sub Lite,
  HTTP Client, Pulsar, Azure Event Hubs, Redis Streams, NATS Streaming, NATS
  JetStream, Apache Fluss, Apache Kafka, Pravega and Infinispan. **RabbitMQ is
  not among them.** So for this stack CDC means adopting Kafka + Kafka Connect,
  writing a custom sink, or bridging from the HTTP sink and owning delivery
  semantics across the bridge. Lesson 04 now says this outright instead of
  deferring to "check what your platform supports".

- ~~**debezium.io returns 403 to the fetch tool.**~~ **Worked around
  2026-09-10.** The rendered site still refuses, but the documentation *source*
  is public AsciiDoc in the `debezium/debezium` repo and fetches fine from
  `raw.githubusercontent.com` under
  `documentation/modules/ROOT/pages/…`. Both the Outbox Event Router claims and
  the Debezium Server sink list above came from there. Use that route for any
  future Debezium citation.

- **Fourth round — grounding the caveats**, 2026-09-10. Motivated by "fix all
  caveats recorded"; a mix of measurement against a throwaway harness
  (PostgreSQL 17.11 + a three-node RabbitMQ 4.3.5 cluster, since deleted —
  transcripts in `evidence/`) and primary-source verification. Findings:
    1. **A requeued message returns to the head of the queue, and the
       displacement is the prefetch window.** Publish 1–5, reject 1 once:
       prefetch 1 gives `1 1* 2 3 4 5`, prefetch 2 gives `1 2 1* 3 4 5`,
       prefetch 5 gives `1 2 3 4 5 1*`. Quorum and classic behave the same at
       the extremes. This retires the "requeue position is unspecified" debt
       carried by Lessons 05 and 06 — the docs' *"any redelivery can change
       order"* is true, but the cause is in-flight deliveries, not queue
       position.
    2. **Single active consumer does not preserve order under retries.** 460
       events, 23 aggregates, sharded relays, one active consumer per shard:
       0 violations clean, **15 violations across 12 aggregates** with 5% of
       first deliveries requeued, and **0 again at prefetch 1**. The
       recommended configuration in Lesson 05 was incomplete; prefetch 1 is the
       other half of the guarantee.
    3. **`basic.nack(requeue=true)` does not count toward the quorum-queue
       delivery limit.** Limit 3, DLX bound: 12 polite nacks and still
       cycling; the same message returned by closing the channel instead was
       counted out after 4 deliveries. The docs agree — *"Unlimited explicit
       returns (via `nack` …) are allowed without counting toward the delivery
       limit"*, while the counter moves for *"`reject` … or channel
       termination with pending messages"*. **Lesson 06 previously taught the
       opposite**, so this is a correction, not an addition.
    4. **Unresolved:** in that same run the counted-out message left the queue
       but never arrived on the bound dead-letter queue. Recorded as an open
       question rather than a claim.
    5. **Per-aggregate order is not global order, measured.** The clean sharded
       run showed **185 inversions** when checked for global outbox-id order
       while showing zero per-aggregate violations.
    6. **Verified library claims.** aio-pika 10.0.1 defaults `mandatory=True`
       on `Exchange.publish` (`aio_pika/exchange.py`, `abc.py`) — the opposite
       of the AMQP protocol default quoted in Lesson 03, and worth saying out
       loud. `pamqp.commands.Basic.Ack` imports (pamqp 4.0.0).
    7. **No built-in partition creation in PostgreSQL.** *"Inserting data into
       the parent table that does not map to one of the existing partitions
       will cause an error"* and *"it might be wise to write a script that
       generates the required DDL automatically"*. For an outbox this is
       sharper than usual: the insert shares the business transaction, so a
       missing partition fails the order, not the relay.
    8. **`NOTIFY` is transactional**, notifications collapse per
       channel+payload within a transaction, payloads are under 8000 bytes, and
       a full queue makes *"transactions calling `NOTIFY` fail at commit"*.
       Enough to promote Lesson 04's one-line sidenote into a real section.
    9. **Broker dedup windows sourced.** SQS FIFO: a fixed *"5-minute
       deduplication interval"*. NATS JetStream: two minutes, and configurable.

[outbox]: https://microservices.io/patterns/data/transactional-outbox.html
[polling]: https://microservices.io/patterns/data/polling-publisher.html
[tailing]: https://microservices.io/patterns/data/transaction-log-tailing.html
[helland]: https://ics.uci.edu/~cs223/papers/cidr07p15.pdf
[pgselect]: https://www.postgresql.org/docs/current/sql-select.html
[pgmvcc]: https://www.postgresql.org/docs/current/mvcc.html
[pgseq]: https://www.postgresql.org/docs/current/functions-sequence.html
[idempotent]: https://microservices.io/patterns/communication-style/idempotent-consumer.html
[rmqconfirms]: https://www.rabbitmq.com/docs/confirms
[sqsstandard]: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html
[natsstreams]: https://docs.nats.io/nats-concepts/jetstream/streams
[rmqpublishers]: https://www.rabbitmq.com/docs/publishers
[rmqquorum]: https://www.rabbitmq.com/docs/quorum-queues
[aiopika]: https://github.com/mosquito/aio-pika/blob/master/docs/source/rabbitmq-tutorial/7-publisher-confirms.md
[debezium]: https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html
[sqsfifo]: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-exactly-once-processing.html
[pglogical]: https://www.postgresql.org/docs/current/logicaldecoding-explanation.html
[pgplugin]: https://www.postgresql.org/docs/current/logicaldecoding-output-plugin.html
[pgwalconf]: https://www.postgresql.org/docs/current/runtime-config-wal.html
[pgreplconf]: https://www.postgresql.org/docs/current/runtime-config-replication.html
[dbzpostgres]: https://debezium.io/documentation/reference/stable/connectors/postgresql.html
[pgadvisory]: https://www.postgresql.org/docs/current/explicit-locking.html
[pgadvfn]: https://www.postgresql.org/docs/current/functions-admin.html
[rmqqueues]: https://www.rabbitmq.com/docs/queues
[rmqconsumers]: https://www.rabbitmq.com/docs/consumers
[rmqdlx]: https://www.rabbitmq.com/docs/dlx
[pgvacuum]: https://www.postgresql.org/docs/current/routine-vacuuming.html
[pgpartition]: https://www.postgresql.org/docs/current/ddl-partitioning.html
[pgnotify]: https://www.postgresql.org/docs/17/sql-notify.html
[dbzserver]: https://raw.githubusercontent.com/debezium/debezium/main/documentation/modules/ROOT/pages/operations/debezium-server.adoc
[dbzoutboxsrc]: https://raw.githubusercontent.com/debezium/debezium/main/documentation/modules/ROOT/pages/transformations/outbox-event-router.adoc
