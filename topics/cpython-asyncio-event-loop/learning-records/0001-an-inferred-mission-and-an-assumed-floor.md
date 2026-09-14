# An inferred mission, and an assumed floor

**14 September 2026.**

## What happened

The request was to take `docs/research/cpython-asyncio-event-loop.md` and turn it
into lessons. No reason for wanting the subject was given, no prior knowledge was
stated, and no deliverable was named — no service to debug, no performance
problem to chase, no loop to write.

`MISSION.md` was therefore written around **durable understanding of the
machinery** rather than around a deliverable, taking its shape from the research
document's own scope statement: a reading of `BaseEventLoop` for someone who
already writes `async def` fluently and wants to know what happens underneath.
That is a storage-strength goal, so every lesson carries retrieval practice and
the set is written to be spaced over days.

## The floor is an assumption, and is recorded here as one

The research document states its own audience — "someone who already writes
`async def` and `await` fluently" — and the lessons take that literally:

- **Assumed present:** comfort writing coroutines, `await`, `asyncio.run`,
  `create_task`, `gather`. The reader has used `asyncio.sleep` and knows what a
  Task is *for*.
- **Assumed absent:** any exposure to `_run_once`, `Handle`, the `_ready` deque,
  the timer heap, `selectors`, `epoll`, the self-pipe, or
  `_asyncio_future_blocking`. Nothing is taught as "you'll recognise this from X",
  because there is no established X.

No evidence supports that split. It was chosen because it is the safe direction
to be wrong in: a reader who already knows the `_ready`/`_scheduled` division
loses ten minutes in lessons 1 and 2, while a reader who does not would lose the
entire argument that lessons 3 through 13 rest on.

## The one place the assumption is load-bearing

Lesson 7 teaches the `_asyncio_future_blocking` protocol **cold**, before the
round trip that uses it. That ordering only works if the reader can already read
a coroutine and knows that `await` suspends something. If it turns out they
cannot, the fix is not to move lesson 7 — it is to accept that this topic has the
wrong floor and that a coroutine primer belongs in front of it, which by the
repo's no-cross-topic rule would mean a separate workspace.

## What would supersede this record

The first genuine evidence of level will come from how lessons 2 and 3 land. If
the six steps and the `ntodo` snapshot are obvious, compress lessons 1–2 and move
the threading material (lesson 13) much earlier, since it is the part with
immediate operational consequences. If lesson 7 is the one that stalls, the floor
was wrong rather than the ordering.

Because there is no deliverable to build toward, the topic is judged on whether
the mechanism can be reconstructed from memory rather than on whether anything
ships — so the five reference documents carry more weight than usual, since they
are what actually gets revisited.
