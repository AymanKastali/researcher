# CPython asyncio Event Loop Glossary

The vocabulary of the machinery: the objects the loop owns, the protocol that
joins a coroutine to it, the timing terms, the threading terms, and the two
evidence markers this topic keeps apart. Where a term has a quoted definition in
a PEP, in the 3.13 documentation, or in a CPython source comment, that quotation
is the authority and this entry is its compression. All source references are
against tag `v3.13.11`.

## The two evidence markers

**[guaranteed]**:
A claim stated in a PEP, in the language reference, or in the `docs.python.org`
reference for 3.13. You may rely on it; if CPython breaks it, that is a bug in
CPython.
_Avoid_: Documented, official, safe

**[impl detail]**:
A claim true of CPython 3.13.11 because that is how this code is written. Not
promised anywhere. A different loop (uvloop), a different Python version, or a
refactor may change it without notice. **Most of what is interesting in this
topic is [impl detail].**
_Avoid_: Internal, private, hack

## The loop's own state

**Event loop proper**:
The half of the loop that schedules callbacks and timers, owns the ready queue
and the clock, and knows nothing about I/O. PEP 3156 splits the design here: "The
event loop can be broken up into a multiplexer (the part responsible for
notifying us of I/O events) and the event loop proper, which wraps a multiplexer
with functionality for scheduling callbacks, immediately or at a given time in
the future" ([PEP 3156](https://peps.python.org/pep-3156/), repeated almost
verbatim as the `base_events.py` module docstring). In CPython this is
`BaseEventLoop`, and it is **pure Python, always**.
_Avoid_: The core, the scheduler, the runtime

**Multiplexer**:
The half that turns file-descriptor readiness into events. In CPython this is
`BaseSelectorEventLoop` (Unix, and Windows' `SelectorEventLoop`) or
`ProactorEventLoop` (Windows IOCP). The seam between the two halves is the pair
of `NotImplementedError` stubs at `base_events.py:541-552`.
_Avoid_: The poller, the reactor, the backend

**`_ready`**:
A `collections.deque` of `Handle` objects due *now*. FIFO: `call_soon` appends on
the right, the drain pops from the left. Together with `_scheduled` it is the
loop's **entire** scheduling state (`base_events.py:420-424`).
_Avoid_: The queue, the callback list, the run queue

**`_scheduled`**:
A plain list used as a min-heap via `heapq`, holding `TimerHandle` objects
ordered by absolute fire time.
_Avoid_: The timers, the schedule, the timer queue

**`_run_once()`**:
One full iteration of the event loop: timer-heap hygiene, compute the poll
timeout, poll, turn events into callbacks, move due timers into `_ready`, drain.
`run_forever` is a `while True` around it and nothing else
(`base_events.py:1970-2051`).
_Avoid_: A tick, a cycle, a turn

**The drain**:
Step 6 of `_run_once`, and "the only place where callbacks are actually
*called*" (source comment, `base_events.py:2027-2028`). Everything else in
asyncio only *adds* to `_ready`.
_Avoid_: The dispatch, the execution phase

**`ntodo`**:
The snapshot `ntodo = len(self._ready)` taken once, before the drain begins. It
is what makes the drain fair (a callback that schedules a callback does not get
to run it this iteration) and thread-safe without a lock (a concurrent append can
only make the real length larger, never smaller).
_Avoid_: The batch size, the count

**`Handle`**:
The loop's unit of scheduled work: a callback, its arguments, a captured
`contextvars.Context`, and a cancelled flag (`events.py:29-105`). `__slots__`-ed,
because one is allocated per callback.
_Avoid_: Job, task, callback object

**`TimerHandle`**:
A `Handle` with an absolute deadline `_when` and a `_scheduled` flag recording
whether it is currently in the heap (`events.py:108-168`). Orders by `_when`
alone, but compares equal only on callback and args too — so the ordering is a
**preorder**, not a total order.
_Avoid_: Timer, alarm, scheduled callback

## Futures, Tasks and the handshake

**Future**:
One result-or-exception slot, a state enum, a list of done-callbacks, and a
reference to its loop. It knows nothing about who is waiting or why. Its one
active behaviour is turning `set_result` into `loop.call_soon` — the callbacks
are **never** called inline ([PEP 3156 § Futures](https://peps.python.org/pep-3156/#futures)).
_Avoid_: Promise, deferred, result

**Task**:
A `Future` subclass that also owns a coroutine object, a `contextvars.Context`,
cancellation bookkeeping, and `_fut_waiter`. It drives `coro.send` / `coro.throw`
and knows nothing about the ready queue, the selector, or time.
_Avoid_: Green thread, fiber, job

**`_fut_waiter`**:
The Future a Task is currently blocked on, and the only structural difference
between a `Task` and a plain `Future`. It exists so cancellation can propagate
*inward*: cancelling a Task cancels the Future it is waiting on
(`tasks.py:229-238`).
_Avoid_: The awaited thing, the child

**`_asyncio_future_blocking`**:
The attribute the whole coroutine/loop join rests on, described by its own source
comment as serving "a dual purpose": a marker declaring Future-protocol
compatibility, and the flag "set by `__iter__()` […] so that `Task._step()` can
tell the difference between `await Future()` […] (correct) vs. `yield Future()`
(incorrect)" (`futures.py:59-68`). Read it as **three-valued**: `None` means "not
a Future", `False` means "a Future that was yielded wrongly", `True` means "a
Future that suspended properly".
_Avoid_: The blocking flag, the future flag

**The one-shot token**:
The lifecycle of `_asyncio_future_blocking` on one hand-off. `Future.__await__`
mints it by setting the flag to `True` (`futures.py:285`); `Task.__step` burns it
by immediately setting it back to `False` (`tasks.py:340`). A second `yield` of
the same Future without a second `__await__` is rejected.
_Avoid_: The handshake bit, the one-time flag

**Duck-typed Future**:
Any object advertising itself as Future-compatible by carrying
`_asyncio_future_blocking` on its **class** with a value that is **not `None`**
(`base_futures.py:13-21`). A class can opt *out* by setting the attribute to
`None` at class level while its instances set `False` to opt back in — a
subtlety the `isfuture` documentation omits.
_Avoid_: Future-like, awaitable

**Eager task**:
A Task whose first step runs *inline in the constructor* rather than through
`call_soon`, enabled by `eager_task_factory` (3.12). If the coroutine finishes in
that first step the task is never registered and never touches `_ready`; if it
blocks, it *graduates* to the normal registry. The documentation calls this "a
semantic change", not an optimisation.
_Avoid_: Fast task, inline task, sync task

## Timing

**`loop.time()`**:
The loop's clock. **[guaranteed]** by the 3.13 docs to be monotonic;
**[impl detail]** that it is precisely `time.monotonic()`. PEP 3156 permits
`time.time()`, and the docstring disclaims epoch, precision, accuracy and drift.
Not POSIX time: the base is undefined, "e.g. the time of the system power on"
(`timeouts.py:171-172`).
_Avoid_: Now, wall clock, timestamp

**`_clock_resolution`**:
`time.get_clock_info('monotonic').resolution`, captured once at loop
construction and used in exactly one place: step 5 of `_run_once`.
_Avoid_: Tick, granularity, precision

**The clock-resolution fudge**:
Step 5 treats a timer as due when `_when < now + _clock_resolution`, rather than
`_when <= now` — firing up to one clock tick *early* rather than burning a whole
extra iteration on a timer within the clock's own measurement error of being due.
**[guaranteed]**, and one of the very few pieces of `_run_once` in the reference
documentation.
_Avoid_: Rounding, slack, jitter

**`MAXIMUM_SELECT_TIMEOUT`**:
`24 * 3600`, the ceiling on any single poll timeout, "to avoid OS limitations"
(`base_events.py:67-68`). Not a limit on how long a timer may be: a 30-day timer
simply costs 30 iterations that each wake, find the head still in the future, and
re-block.
_Avoid_: The max sleep, the timeout cap

**Compaction**:
The O(n) rebuild of `_scheduled` that drops cancelled handles, triggered only
when there are more than `_MIN_SCHEDULED_TIMER_HANDLES` (100) timers *and* more
than `_MIN_CANCELLED_TIMER_HANDLES_FRACTION` (0.5) of them are believed
cancelled. The alternative, cheap path pops cancelled handles off the *head*
only. Both constants are **[impl detail]** and appear nowhere in the
documentation — but CPython's test suite imports them by name.
_Avoid_: Cleanup, GC, vacuum

## Threads and wakeups

**`call_soon_threadsafe`**:
`call_soon` plus one mandatory `_write_to_self()`. Per PEP 3156, "This is the
*only* method that is safe to call from another thread."
_Avoid_: The thread-safe version, the async post

**The self-pipe**:
A `socket.socketpair()` — despite the name — owned by every selector loop from
birth (`selector_events.py:118-124`). The read end is registered with the
selector; writing a byte to the write end forces `select()` to return. The bytes
are discarded: **the wakeup is the payload**.
_Avoid_: The wake pipe, the eventfd, the trigger

**`_write_to_self`**:
The write half, deliberately written to be callable from any thread at any time,
including during loop teardown. Copies `self._csock` into a local *before* the
`None` check and swallows `OSError`, so a concurrent close cannot break it.
_Avoid_: Wake, poke, signal

**Signal demultiplexing**:
On Unix, `add_signal_handler` points CPython's signal-wakeup fd at the *same*
socket the self-pipe uses, so the kernel writing a signal number both wakes the
loop and delivers the number. `b'\0'` is the chosen wakeup byte precisely because
signal number 0 does not exist (`unix_events.py:83-88`).
_Avoid_: Signal handling, the signal pipe

**Reentrancy**:
Running a loop inside a loop, which asyncio refuses in three separate places:
`_check_running` (`base_events.py:635-640`), `_enter_task`/`_leave_task`
(`tasks.py:1057-1070`) and `Runner.run` (`runners.py:189-192`). There is no
nested-loop facility and none is planned.
_Avoid_: Nesting, recursion, re-entry

## The C accelerator

**`_asyncio`**:
The C extension module that replaces `Future`, `Task`, `current_task` and the
running-loop accessors at import time. The Python versions stay importable as
`_PyFuture`/`_PyTask`, which is what makes the six-way parity test matrix
possible. **There is no C event loop**: `BaseEventLoop`, `Handle`, `_ready`,
`_run_once` and `call_soon` are pure Python in every build.
_Avoid_: The C core, the native loop, the fast path

**The parity requirement**:
Because both implementations are live, `test_tasks.py` runs the same test body
six ways — C Task with Python Future, Python Task with C Future, and subclass
variants — asserting identical *observable call sequences*, down to
`add_done_callback` being called exactly once.
_Avoid_: Compatibility, the test matrix

**`Py_BEGIN_CRITICAL_SECTION`**:
PEP 703's deadlock-avoiding per-object lock. `swap_current_task` is the only
place in `_asynciomodule.c` that takes one, because it is a *compound*
read-then-write that must be atomic as a unit.
_Avoid_: The lock, the mutex
