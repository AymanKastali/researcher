# Working notes

## Teaching preferences

**Everything about how a page looks now lives in `docs/agents/design-system.md`**
— dark theme, mobile responsiveness, the verified palette, the highlight.js
setup, and the boilerplate. It was moved there on 2026-09-11 when `assets/` was
hoisted to the repo root, because these rules were never topic-specific and
keeping two copies meant fixing everything twice. Read it before authoring.

**The teaching contract is `docs/agents/teaching-standard.md`** — this topic is
a `mattpocock-skills:teach` workspace, and that file records what the skill
requires of every lesson, what the quiz rules are, and how to check them
(`uv run python docs/agents/check-lessons.py`). Added 2026-09-11 at Ayman's
instruction that everything here adhere to the skill.

What is left here is about *this topic's* teaching, not the styling:

- **Code examples are Python**, per the standing repo convention. SQL, DDL, and
  config stay in their own languages. Verbatim excerpts quoted from a real
  source keep the source's language.
- **No code trees in the workspace.** Stated 2026-09-10, twice. The lessons and
  `RESOURCES.md` are the source of truth; a runnable project is not, and
  building one costs time and tokens Ayman would rather spend on the lessons.
  Ground claims in primary sources. If something genuinely cannot be settled
  any other way, ask first, run the smallest possible thing, keep the
  transcript in `evidence/`, and delete the harness.
- Goal is *recall under questioning*, not recognition. Lessons use one-attempt
  quizzes and free-recall prompts rather than re-reading. Do not soften this
  into review sheets.

## Workspace conventions

- Lessons: `lessons/NNNN-dash-case.html`, linking `../../../assets/lesson.css`
  and `../../../assets/quiz.js` — the shared assets at the **repo root**, not a
  topic-local copy. There is no `topics/*/assets/` any more.
- Reusable components live in the root `assets/`. Reuse before authoring
  anything new, and put anything a second page could use there rather than
  inline in a lesson.
- Markdown wraps at 80 columns (markdownlint MD013 is on in the editor). Long
  URLs go in reference-style link definitions at the bottom of the file.

## Teaching backlog

Sequenced by dependency, not importance:

1. ~~**Lesson 02 — the message relay.**~~ Delivered 2026-09-10. Outbox DDL,
   partial index, `FOR UPDATE SKIP LOCKED`, hold-the-lock vs. lease, and the
   high-water-mark cursor trap.
2. ~~**Lesson 03 — at-least-once and the idempotent consumer / inbox.**~~
   Delivered 2026-09-10. Three sources of duplicates, delivery vs. processing,
   the inbox table, the single-transaction boundary, commit-then-ack, and the
   broker comparison. Broker was never pinned down — taught comparatively
   instead, see `learning-records/0002-*`.
3. ~~**Lesson 04 — polling vs. CDC.**~~ Delivered 2026-09-10. CDC replaces the
   relay not the outbox, commit order as the one thing polling cannot buy, still
   at-least-once because the slot position is only checkpointed, and the
   replication slot as an availability liability on the primary. Decision:
   **polling**, see `learning-records/0004-*`.
4. ~~**Lesson 05 — ordering.**~~ Delivered 2026-09-10. The three requirements
   hiding behind one word, the four places order dies, the aggregate row lock as
   the reason per-aggregate order is cheap, hash-sharding plus single active
   consumer, and the version gate as the escape hatch. Interleaved retrieval
   over 02–03 in the quiz. Decision: **per-aggregate**, see
   `learning-records/0005-*`.
5. ~~**Lesson 06 — operating it.**~~ Delivered 2026-09-10. Age-not-count as the
   health metric with a per-shard `GROUP BY`, the poison row that stalls a shard
   and why skipping the row (rather than parking the aggregate) reintroduces
   Lesson 05's bug, the quorum-queue delivery limit and the DLX with its
   at-most-once hole, and retention across three tables of which only two age
   out. Second round of measured results. See `learning-records/0006-*`.
6. ~~**Lesson 07 — run it.**~~ Delivered 2026-09-10. Postgres and RabbitMQ in
   Docker, producer/relay/consumer as three real processes, `SIGKILL` in the
   crash window on both sides of the publish, the dual-write control that loses
   an order permanently, two relays over 500 rows, and a poll-interval latency
   sweep. Third measured round, and the first that runs Python. See
   `learning-records/0007-*`.
7. ~~**Lesson 08 — break it on purpose.**~~ Largely **absorbed 2026-09-10** by
   the caveat-closing pass, which ran the poison message, the delivery limit,
   the requeue probe and the sharded ordering experiment, and folded the
   results back into Lessons 05 and 06 rather than into a new lesson. Two of
   those results were corrections, not additions — see
   `learning-records/0008-*`.
8. **Lesson 08 — failover, and the dead-letter hop.** What is left of the old
   item 7, and it is the sharpest unobserved claim in the course. Kill the
   quorum-queue leader under load and check for loss, duplicates and ordering
   violations; and chase down why a counted-out message left the queue without
   arriving on a bound DLQ. Neither is set up any more — the harness was
   deleted 2026-09-10 (see the working rule below), so this item now costs a
   rebuild. `evidence/06-delivery-limit.txt` is the transcript to start from.

**Working rule established this session.** When a doc states a guarantee, find
the sentence that says *when it applies*. Both corrections this session were
sitting in plain text on pages the course had already cited: single active
consumer guarantees one consumer but not one message in flight, and the
delivery limit counts `reject` but not `nack`.

### Debts carried by Lesson 02

- Batch size (100) is still a sane starting point, not a measured number. The
  poll interval half is now grounded: the latency *shape* is measured (p50 =
  half the interval, p95 = the interval). Throughput per batch size is not.
- ~~Approach B's SQL needs `claimed_at` / `claimed_by`, which the lesson's DDL
  does not include.~~ **Closed 2026-09-10.** The lesson now ships the
  `ALTER TABLE` beside the claim query and says why the columns stay out of the
  main DDL. Approach B was written and the columns exist in the schema it ran
  against, but it was never run as an experiment.

### Debts carried by Lesson 03

- Inbox retention is named as a problem and deferred to Lesson 06. The lesson
  states the rule (keep rows longer than your maximum plausible redelivery
  delay) but gives no number, because none of the broker docs provides one.
- The "reinvent the outbox for external side effects" point at the end is
  compressed into two bullets. If Ayman pulls on it, it is probably its own
  lesson rather than an expansion of this one.
- ~~Broker dedup windows are quoted loosely.~~ **Sourced 2026-09-10.** SQS FIFO
  is a fixed *"5-minute deduplication interval"*; NATS JetStream's two minutes
  is a configurable **default**. The sidenote now quotes both and marks which
  is which.
- ~~aio-pika's default for `mandatory` is **unverified**.~~ **Verified
  2026-09-10:** aio-pika 10.0.1 declares `mandatory: bool = True` on
  `Exchange.publish` — the *opposite* of the AMQP protocol default the lesson
  quotes. Lesson 03 now states both and keeps the "set it explicitly" advice
  for the right reason: never rely on a client default for a durability
  property. `pamqp.commands.Basic.Ack` also confirmed (pamqp 4.0.0).
- ~~None of the Python in Lessons 02–03 has been executed.~~ **Closed** by
  Lesson 07 and by the runs transcribed in `evidence/`.

### Debts carried by Lesson 04

- ~~**debezium.io returns 403 to the fetch tool.**~~ **Routed around
  2026-09-10.** The rendered site still refuses; the AsciiDoc source in the
  `debezium/debezium` GitHub repo fetches fine. Both claims verified verbatim
  there — *"The SMT automatically filters out `DELETE` operations"* and
  *"updates to records in an outbox table are not allowed"*. Use the raw
  GitHub route for any future Debezium citation.
- ~~**How Debezium reaches RabbitMQ was not checked.**~~ **Answered
  2026-09-10: it does not.** RabbitMQ is not in Debezium Server's sink list.
  Lesson 04 now states this as a decision rather than hedging. The opposite
  risk now applies — do not let it harden into "CDC is impossible here"; it is
  possible, it just costs Kafka or a bridge you write and operate.
- ~~The `LISTEN`/`NOTIFY` middle option is one sidenote.~~ **Promoted
  2026-09-10** to a real section, grounded in the PostgreSQL NOTIFY page
  (transactional delivery, duplicate collapsing, 8000-byte payload, the full
  queue failing the *commit*). A `LISTEN`-woken relay was written but never
  benchmarked against the polling one.
- Still no numbers on WAL growth rate or the threshold at which polling stops
  paying. The latency half is measured; keep the rest argued from mechanism.

### Debts carried by Lesson 05

- ~~**The lesson runs SQL but still not Python.**~~ Closed by Lesson 07.
- ~~**The relay's SQL shard function and the publisher's Python shard function
  must agree**, and they did not.~~ **Fixed 2026-09-10.** The two-hash version
  is gone. The lesson now ships a stored generated column —
  `shard smallint GENERATED ALWAYS AS (hashtext(aggregate_id) & 3) STORED` —
  and the publisher reads it. One implementation, in the place that sees every
  insert. Note the bitmask instead of `%`: `hashtext` returns a signed int and
  `abs()` of the most negative one overflows; masking costs you a power-of-two
  shard count.
- **`hashtext()` is an internal function.** Immutable and stable within a major
  version (verified: `provolatile = 'i'`), but absent from the documented
  function list. Flagged in a sidenote; do not let it harden into a
  recommendation without the caveat attached.
- **No number for shard count.** Eight is a placeholder. The trade-off (more
  shards = finer parallelism, more queues, more consumers) is argued from
  mechanism, consistent with the other gaps.
- ~~**Requeue position is unspecified.**~~ **Measured 2026-09-10: the head.**
  Publish 1–5, reject 1 once — prefetch 1 gives `1 1* 2 3 4 5`, prefetch 5
  gives `1 2 3 4 5 1*`. The requeued message returns to the front; what
  displaces it is the consumer's own in-flight prefetch window. This produced
  the session's biggest correction, and Lesson 05 now carries it: **single
  active consumer alone does not hold order under retries** — 15 violations
  across 12 aggregates at prefetch 20, zero at prefetch 1. See
  `learning-records/0008-*`.
- **The prefetch-1 fix has an unmeasured cost.** It removes pipelining on
  every ordered shard. More shards is the compensation and nobody has measured
  the trade.

### Debts carried by Lesson 06

- ~~**The parked-aggregate table is asserted, not built.**~~ **Built
  2026-09-10.** DDL and the anti-join claim query are now in the lesson, and
  both ran against the real relay. Still not benchmarked against the
  correlated version at volume.
- ~~**The partitioned DDL is a sketch** and nothing says how partitions get
  created.~~ **Answered 2026-09-10 from the PostgreSQL docs:** there is no
  built-in mechanism, the manual tells you to write a script, and an unmapped
  insert *errors*. For an outbox that is sharper than usual — the insert shares
  the business transaction, so a missing partition fails the **order**, not the
  relay. The lesson now says this and names the `DEFAULT` partition as a shock
  absorber. Still a sketch in the sense that no scheduled job exists here.
- **No retention numbers, again.** "Seven days" appears in one code sample as
  an illustration and must not harden into a recommendation. And the claim that
  the delivery limit *bounds* the redelivery window is now weaker than it
  looked — see the correction below; the limit does not count a polite `nack`.
- **The dead-letter hop is unresolved.** A counted-out message left the queue
  and never arrived on the bound DLQ. Either the setup is wrong or the
  at-most-once default dropped it. Lesson 06 records this as an open question;
  do not promise an interviewer that a counted-out message is retrievable
  until it is chased down.
- **The measured `DELETE` vs `DROP` timings are from a tiny fixture** (200k
  rows, container, no concurrent load). The lesson says out loud not to quote
  the ratio, only the shapes. Keep that caveat if the numbers are ever reused.

### Debts carried by Lesson 07

- ~~**The runnable project lives in a scratchpad, not the repo.**~~ **Resolved
  the other way, 2026-09-10.** It was promoted to `project/`, used to produce
  the corrections in Lessons 05 and 06, and then **deleted at Ayman's
  instruction** — the lessons and `RESOURCES.md` are the source of truth here,
  and a code tree is neither. What survives is `evidence/`: the five captured
  transcripts plus a README naming the environment and what was never run.
  Rebuild cost is real; do not promote a project again without asking.
- ~~**Sharding was deliberately not run.**~~ **Run 2026-09-10.** 460 events,
  23 aggregates, four shards, one active consumer per shard: zero ordering
  violations clean, and the negative results that mattered more — see the
  Lesson 05 debts above.
- ~~**One broker node.**~~ Now a **three-node cluster** with a quorum replica
  on each (`x-quorum-initial-group-size: 3`). **Failover is still not
  tested** — no experiment kills the queue leader under load, so "quorum
  queues survive losing a node" remains the vendor's claim, not ours. The
  delivery limit and the DLX are no longer unexercised; exercising them
  produced a correction to Lesson 06.
- **The latency numbers are one laptop, no network, no load.** The *shape*
  (p50 = half the interval, p95 = the interval) is arithmetic and safe to
  quote. The milliseconds are not.
- **`uv run` orphans its child.** Killing the `uv` parent leaves the Python
  process polling, which silently contaminated the first latency sweep. Any
  future experiment script must launch `.venv/bin/python` directly so `$!` is
  the real PID. Also: never `pkill -f` on a pattern that appears in the
  invoking shell's own command line — it kills the shell.
- **Docker Desktop's VM disk is full** (62.7 GB, ~17 MB free), so the
  `desktop-linux` context cannot start containers. The native Ubuntu engine
  (`docker -c default`) has ~200 GB and is what Lesson 07 ran on. Nothing of
  Ayman's was pruned. Worth mentioning to him if he hits it elsewhere.

### Candidate reference document

A printable **RabbitMQ outbox settings** cheat sheet — confirms, `mandatory`,
persistent + durable, quorum queues, prefetch, manual ack, delivery limit, DLX
— currently lives as a table inside Lesson 03 and a glossary section. Promote
it to `reference/` if it gets referred to a third time.

## Open questions to revisit

- ~~Which broker specifically?~~ **RabbitMQ**, answered 2026-09-10. Lesson 03
  and `MISSION.md` rewritten accordingly; see
  `learning-records/0003-broker-pinned-to-rabbitmq.md`. Lesson 06 can now treat
  dead-lettering concretely (DLX + quorum-queue delivery limit).
- Interview timeline unknown. If there is a date, spacing should be planned
  backwards from it.
