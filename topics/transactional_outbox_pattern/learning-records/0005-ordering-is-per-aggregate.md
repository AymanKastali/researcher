# Ordering is per-aggregate, and the aggregate row lock is why

**Status:** active, with one correction. The decision below stands, but its
claim that single active consumer completes the guarantee was measured false and
is corrected in
[0008-two-guarantees-that-were-not-guarantees.md](0008-two-guarantees-that-were-not-guarantees.md).
Read both.

Decided 2026-09-10 in Lesson 05. The mission names ordering as a production
failure mode Ayman must be able to argue, and three earlier lessons had deferred
to it. The lesson had to end in a specified design, not a list of options.

## The decision

**Per-aggregate ordering**, delivered by three changes that each close one of
the places order dies:

1. Hash the aggregate id into a shard; each relay worker owns fixed shards. One
   aggregate has exactly one owner, by arithmetic, with no coordination.
2. The shard is the routing key; one queue per shard.
3. `x-single-active-consumer` on those queues, and a sequential handler loop.

Global total order is taught as **available and refused**, with its price stated
out loud: one publisher, one queue, one consumer, no concurrency anywhere.

## The insight worth keeping

This is the one to carry into a room:

> Writes to one aggregate already serialise, because they contend on that
> aggregate's row. That is the definition of an aggregate — a consistency
> boundary. Inside it, id order *is* commit order. Global order has no such row
> to contend on, which is exactly why it is unbuyable and per-aggregate order is
> nearly free.

It explains the whole trade-off from a single mechanism, rather than asserting
that per-aggregate ordering is "usually enough" and hoping nobody asks why.

The stated precondition matters as much as the claim: it holds only if writes to
the aggregate genuinely touch a shared row. Handlers that append events for
order 42 without ever locking order 42 get ordering from nothing.

## What was measured, not read

First experiments run in this workspace — PostgreSQL 17.11 in a throwaway
container. Full results in the RESOURCES gaps; the two that changed the lesson:

- **The advisory-lock claim query is wrong, and the plan says so.**
  `pg_try_advisory_xact_lock` in a `WHERE` clause is evaluated on every
  candidate row, before `LIMIT` applies, and the locks are held to commit.
  `LIMIT 1` over six rows took two locks; a concurrent worker claimed nothing.
  The design was going into the lesson as the recommended fix until it was run.
  It is now the lesson's trap callout, with the plan quoted.
- **Sequence order diverges from commit order, observably.** A row inserted
  first became visible second, and a poll in the gap saw only the later event.
  Lesson 02 asserted this from the `nextval` docs; it is now demonstrated.

## Why running things changed the lesson

Worth remembering as a working practice, not just a fact about this topic: the
rejected design was plausible, cited a real primitive, and would have survived
review. Ten minutes in a container killed it. Future lessons should prefer a
container to a confident paragraph wherever the claim is mechanical.

## Revisit when

Delta events start dominating the traffic — the version gate stops applying and
the ordering machinery has to carry the whole load. Or when shard count needs to
change under live traffic, which the current design handles only by draining.
