# Prior knowledge baseline: transactions yes, queue primitives no

Ayman reports being solid on Postgres transaction mechanics — `BEGIN`/`COMMIT`
and isolation basics — but has not used `FOR UPDATE SKIP LOCKED`,
`LISTEN`/`NOTIFY`, or logical decoding. Established at workspace setup on
2026-09-10, before any lesson was delivered.

## Implications

- Skip teaching what a transaction is. Lesson 01 can assume atomicity is
  understood and spend its budget on *why atomicity does not extend across two
  systems* — the interesting part.
- The row-locking primitives are the real new material, so they get their own
  lesson (02) rather than being smuggled in as a detail of the relay.
- Claimed depth is self-reported and untested. If Lesson 02 shows shaky ground
  on what a row lock holds and for how long, supersede this record.
