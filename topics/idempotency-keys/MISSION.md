# Mission: Network Idempotency and Idempotency Keys

## Why

To own the distributed-systems reasoning underneath retry-safe APIs well enough
that it is still there in a year, not just readable on the day. The target is the
chain of reasoning — a network cannot tell a lost request from a lost response,
so a client must retry, so the receiver must deduplicate — rather than the
ability to recite what an `Idempotency-Key` header does. When this lands, reading
any vendor's idempotency documentation should feel like checking which of a small
number of known choices they made, not like learning something new.

## Success looks like

- Stating from memory why HTTP calls `PUT` and `DELETE` idempotent but not
  `POST`, and why "returns the same response" is the wrong definition.
- Explaining the ambiguous failure — "either once or not at all, and the user is
  not told which" — and why no protocol removes it.
- Drawing the eleven-step lifecycle of a key, and naming which two steps must be
  atomic and what breaks if either is not.
- Arguing why a conditional insert in the store that holds the effect beats an
  external distributed lock, using the fencing-token argument on both sides.
- Naming the mechanism's most dangerous property — an expired key is
  indistinguishable from a key never seen, so it silently re-executes.
- Recognising that a key buys effectively-once *effect*, never exactly-once
  *execution*, and saying what that forces on handler design.

## Constraints

- Starting from near zero on this specific topic: the phrase "retrying is safe"
  and little behind it.
- Long-term retention is the goal, so lessons carry retrieval practice and are
  meant to be spaced over days, not read in one sitting.
- Built in a single pass rather than dripped out. The spacing lives in the study
  advice, not in the delivery schedule.

## Out of scope

- Shipping a production implementation. This is a document set, not a project,
  and the illustrative code exists only to make atomicity concrete.
- Framework-specific or language-specific how-to for any particular stack.
- Consensus algorithms in their own right. Raft and Paxos are named only where a
  source names them; they are not taught here.
