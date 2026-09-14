# Mission: CPython's asyncio Event Loop, From the Inside

## Why

To be able to reason about an asyncio program from the machinery rather than
from the tutorial — and to still be able to do it in a year. Every non-obvious
thing asyncio does in production is a consequence of `BaseEventLoop._run_once()`:
why a callback scheduled by a callback waits for the next iteration, why a
blocking call stalls every socket in the process, why `call_soon` from a worker
thread appears to work and then hangs for three seconds, why `await` on an
already-buffered socket never suspends at all. None of that is derivable from
`async`/`await` syntax. All of it is derivable from eighty lines of Python.

The target is being able to reconstruct *why* the loop behaves as it does — from
the six steps of one iteration, the `ntodo` snapshot, and the
`_asyncio_future_blocking` handshake — not being able to recall which decorator a
blog post recommended.

## Success looks like

- Reciting the six steps of one `_run_once()` iteration in order, and naming
  which single step can block.
- Explaining why the drain snapshots `ntodo = len(self._ready)` instead of
  looping `while self._ready`, and naming both reasons the source comment gives.
- Tracing one `await loop.sock_recv(...)` from the coroutine down to
  `epoll_wait` and back, and saying at which points a full extra loop iteration
  is spent.
- Reading `_asyncio_future_blocking` as a three-valued signal, and explaining why
  a duck-typed attribute is the only tool PEP 3156's layering leaves available.
- Saying what `call_soon` from another thread actually does in CPython 3.13.11 —
  not "it breaks", but the precise failure mode — and why
  `call_soon_threadsafe(lambda: None)` appears in CPython's own SIGINT handler.
- Naming which half of `Task`/`Future` lives in C, which half does not, and why
  the accelerator is worth tens of percent rather than an order of magnitude.
- Separating a **[guaranteed]** claim from an **[impl detail]** on sight, and
  naming at least two places where the 3.13 documentation and the 3.13.11 source
  disagree.

## Constraints

- **CPython 3.13.11 is the version taught.** Every line citation is against that
  tag. A different version, or a different loop implementation, may differ, and
  the lessons say so wherever it matters.
- Long-term retention is the goal, so lessons carry retrieval practice and are
  written to be spaced over days rather than read in one sitting.
- Built in a single pass rather than dripped out. The spacing lives in the study
  advice, not in the delivery schedule.
- Every claim is traceable to a quoted line of CPython source, a quoted PEP
  section, or a quoted paragraph of the 3.13 documentation. Nothing is asserted
  on recall.
- The **[guaranteed]** / **[impl detail]** distinction is carried on the page,
  never smoothed over. Most of what is interesting here is **[impl detail]**.

## Out of scope

- **Tutorial content.** No explanation of `async`/`await` syntax, no coroutine
  primer, no "what is concurrency". The reader already writes `async def`
  fluently; this is about what happens underneath.
- **`ProactorEventLoop` and Windows IOCP.** `Lib/asyncio/proactor_events.py` and
  `windows_events.py` were not read. Everything in `BaseEventLoop` applies;
  nothing in the selector or self-pipe lessons transfers without checking.
- **Third-party loops.** uvloop replaces exactly the layer these lessons open up.
  Nothing here should be assumed to hold under one.
- **`sslproto.py`, `streams.py`, `subprocess.py`.** The transport trace stops at
  `_SelectorSocketTransport`; how `StreamReader` turns `data_received` callbacks
  back into awaitable Futures is one layer further up and is not taught.
- **Performance characterisation.** The measurements quoted are single-machine
  and establish orders of magnitude only. No benchmark is presented as a
  benchmark.
