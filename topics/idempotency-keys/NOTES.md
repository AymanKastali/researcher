# Notes

Working notes and stated preferences for this topic.

## Learner preferences

- **Sources over assertion.** Every substantive claim carries a quotation with
  attribution. A confident sentence with nothing behind it is the failure mode to
  avoid, and it applies to lessons as much as to research.
- **Batch, don't drip.** The whole topic is built in one pass. Spacing is advice
  inside the lessons, not a delivery schedule.
- **Illustrative code is Python**, and is always marked `.code-illustrative` so it
  can never be mistaken for a quotation. Quoted excerpts keep their original
  language — Ruby for Brandur, the DynamoDB condition expression as the Powertools
  authors wrote it.
- **Dark only, mobile first.** Every page is read at phone width before it ships.

## Where this topic came from

The topic was built from `docs/research/idempotency-keys.md` in this repo — a
2,241-line study guide whose sources were fetched and read on 11 September 2026.
The lessons do not add claims to that document; they sequence it for learning and
quote the same primary sources directly.

## Teaching decisions made

- **Lesson 1 starts at the algebra, not the header.** The learner's stated
  starting point was "retrying is safe and little more", and the function-versus-
  effect distinction is the one that everything later depends on. Opening with
  the header would have taught the mechanism before the problem.
- **The Kleppmann/antirez dispute is taught as a dispute** (lesson 7), with both
  sides quoted and the convergence drawn out, rather than resolved into a single
  recommendation. The disagreement is real and load-bearing, and the synthesis
  only means something if both positions are understood first.
- **Retention and expiry get top billing among the edge cases** (lesson 8),
  because it is the only failure mode that is invisible from both sides.

## Open questions for a future session

- Whether to add a lesson on the client side specifically — retry budgets,
  backoff with jitter, and where the key must be persisted so it survives a
  process restart. Currently covered only as step (0) and step (7) of the
  lifecycle.
- The IETF draft expires 18 April 2026. If it advances to RFC, lesson 2 and the
  vendor reference document both need revisiting, and the "work in progress"
  framing throughout becomes wrong.
