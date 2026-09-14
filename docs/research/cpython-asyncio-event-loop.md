# CPython's asyncio Event Loop, From the Inside

How `BaseEventLoop` actually works in Python 3.13, read out of the source.

**Scope.** This is a reading of the machinery, for someone who already writes
`async def` and `await` fluently and wants to know what happens underneath. It
starts at one iteration of `BaseEventLoop._run_once()` and works outward: the
path a single `await` takes from a coroutine down to `epoll_wait` and back; the
division of labour between `Task`, `Future` and the loop, and which half of each
lives in C; the timer heap; the single point at which the loop blocks and what
that implies for threads; and what moved between 3.11 and 3.13. There is no
tutorial content here — no explanation of `async`/`await` syntax, no coroutine
primer.

**Sourcing.** Every claim about internals below is tied to a file, a function and
a line range that was opened and read while writing this document. Load-bearing
code is quoted, not paraphrased. Design claims are tied to the PEP section that
makes them, quoted and linked. Where the documentation and the source disagree —
and they do, in several places — both are quoted and the source is preferred,
with the disagreement called out rather than smoothed over. [§7](#7-where-the-documentation-and-the-source-disagree)
collects those. Anything that could not be verified is in
[§9](#9-what-could-not-be-verified).

---

## Reproducing the line numbers

All line numbers in this document are against **CPython 3.13.11**.

The Python-level files were read from a local install at
`/home/qas/miniconda3/lib/python3.13/asyncio/` (Anaconda's build of 3.13.11,
`Python 3.13.11 | packaged by Anaconda, Inc. | (main, Dec 10 2025, 21:28:48) [GCC 14.3.0]`).
Before citing anything, every file used was diffed byte-for-byte against the
upstream tag `v3.13.11`:

```
$ for f in base_events tasks futures events selector_events runners \
           timeouts taskgroups unix_events constants; do
    curl -sS -o up.py \
      "https://raw.githubusercontent.com/python/cpython/v3.13.11/Lib/asyncio/$f.py"
    diff -q up.py "/home/qas/miniconda3/lib/python3.13/asyncio/$f.py"
  done
```

All ten files, plus `Lib/selectors.py`, are identical to the tag. So
`Lib/asyncio/base_events.py:1970` in this document and
`/home/qas/miniconda3/lib/python3.13/asyncio/base_events.py:1970` on that install
are the same line, and both match
`https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/base_events.py#L1970`.

`Modules/_asynciomodule.c` is not shipped with a binary install. It was fetched
from the same tag
(`https://raw.githubusercontent.com/python/cpython/v3.13.11/Modules/_asynciomodule.c`,
3777 lines) and its line numbers are against that file.

Citations look like `Lib/asyncio/base_events.py:1970 — BaseEventLoop._run_once()`.

### Marker convention

Two markers run through the document, and they are the distinction that matters
most when reading internals:

- **[guaranteed]** — stated in a PEP, in the language reference, or in the
  `docs.python.org` reference for 3.13. You may rely on it; if CPython breaks it,
  that is a bug in CPython.
- **[impl detail]** — true of CPython 3.13.11 because that is how this code is
  written. Not promised anywhere. A different event loop (uvloop), a different
  Python version, or a refactor may change it without notice. Most of what is
  interesting in this document is **[impl detail]**.

There is no third marker for "the documentation is wrong about the current
implementation". Those cases are argued in full, with both texts quoted side by
side, in [§7](#7-where-the-documentation-and-the-source-disagree), and
cross-referenced from wherever they come up.

---

## Contents

1. [One iteration of `_run_once()`](#1-one-iteration-of-_run_once)
2. [From `await` to the selector and back](#2-from-await-to-the-selector-and-back)
3. [Task, Future and the loop: who owns what](#3-task-future-and-the-loop-who-owns-what)
4. [Timers](#4-timers)
5. [Where the loop blocks; reentrancy and threads](#5-where-the-loop-blocks-reentrancy-and-threads)
6. [What changed, 3.11 → 3.13](#6-what-changed-311--313)
7. [Where the documentation and the source disagree](#7-where-the-documentation-and-the-source-disagree)
8. [Sources](#8-sources)
9. [What could not be verified](#9-what-could-not-be-verified)

---

## 1. One iteration of `_run_once()`

### 1.1 The loop around the loop

`run_forever()` is four lines of real work:

```python
    def run_forever(self):
        """Run until stop() is called."""
        self._run_forever_setup()
        try:
            while True:
                self._run_once()
                if self._stopping:
                    break
        finally:
            self._run_forever_cleanup()
```

— `Lib/asyncio/base_events.py:678-687 — BaseEventLoop.run_forever()`

That is the whole event loop. Everything else in `asyncio` is scaffolding around
`_run_once()`.

Two things are worth noticing straight away. First, `stop()` does nothing but set
a flag:

```python
    def stop(self):
        """Stop running the event loop.

        Every callback already scheduled will still run.  This simply informs
        run_forever to stop looping after a complete iteration.
        """
        self._stopping = True
```

— `Lib/asyncio/base_events.py:727-733 — BaseEventLoop.stop()`

The `_stopping` check happens *after* `_run_once()` returns, so the iteration in
progress always finishes: the poll it already performed, the events it already
collected, and the entire ready queue it snapshotted. Second, `_run_forever_setup()`
is where the loop claims the thread:

```python
        self._check_closed()
        self._check_running()
        self._set_coroutine_origin_tracking(self._debug)

        self._old_agen_hooks = sys.get_asyncgen_hooks()
        self._thread_id = threading.get_ident()
        sys.set_asyncgen_hooks(
            firstiter=self._asyncgen_firstiter_hook,
            finalizer=self._asyncgen_finalizer_hook
        )

        events._set_running_loop(self)
```

— `Lib/asyncio/base_events.py:649-660 — BaseEventLoop._run_forever_setup()`

`self._thread_id` is set here and cleared in `_run_forever_cleanup()`
(`base_events.py:670`). It is also the implementation of `is_running()`:

```python
    def is_running(self):
        """Returns True if the event loop is running."""
        return (self._thread_id is not None)
```

— `Lib/asyncio/base_events.py:768-770 — BaseEventLoop.is_running()`

`_run_forever_setup` / `_run_forever_cleanup` were split out of `run_forever` so
that subclasses integrating a GUI loop can reuse the setup without reusing the
`while True` — the docstring says so explicitly at `base_events.py:645-647`.
**[impl detail]**

### 1.2 The two queues

The loop's entire scheduling state is two attributes, both initialised in
`BaseEventLoop.__init__`:

```python
        self._timer_cancelled_count = 0
        self._closed = False
        self._stopping = False
        self._ready = collections.deque()
        self._scheduled = []
```

— `Lib/asyncio/base_events.py:420-424 — BaseEventLoop.__init__()`

- `_ready` is a `collections.deque` of `Handle` objects that are due *now*. It is
  FIFO: `call_soon` appends on the right, `_run_once` pops from the left.
- `_scheduled` is a plain list used as a **min-heap** via the `heapq` module,
  holding `TimerHandle` objects ordered by their absolute fire time. See
  [§4](#4-timers).

Everything the loop can be asked to do eventually turns into "put a `Handle` in
`_ready`" or "push a `TimerHandle` onto `_scheduled`". I/O readiness is the third
source, and it is converted into the first by `_process_events()`.

### 1.3 The shape of one iteration

```
                       ┌─────────────────────────────────────┐
                       │  _run_once()                        │
                       └─────────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ 1. TIMER-HEAP HYGIENE                                base_events:1978 │
  │    if len(_scheduled) > 100 and cancelled/total > 0.5:                │
  │        rebuild _scheduled without cancelled handles, heapify,         │
  │        _timer_cancelled_count = 0                                     │
  │    else:                                                              │
  │        pop cancelled handles off the *head* only                      │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ 2. COMPUTE THE POLL TIMEOUT                          base_events:2001 │
  │    _ready non-empty or _stopping  -> 0      (don't block)             │
  │    _scheduled non-empty           -> clamp(head._when - time(),       │
  │                                            0, 86400)                  │
  │    otherwise                      -> None  (block indefinitely)       │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ 3. THE ONLY BLOCKING CALL                            base_events:2012 │
  │    event_list = self._selector.select(timeout)   ──► epoll_wait(2)    │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ 4. EVENTS -> CALLBACKS                               base_events:2013 │
  │    _process_events(event_list): for each ready fd, take the           │
  │    (reader, writer) Handles out of key.data and _ready.append() them  │
  │    (no user code runs here)                       selector_events:740 │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ 5. DUE TIMERS -> _ready                              base_events:2018 │
  │    end_time = time() + _clock_resolution                              │
  │    pop every TimerHandle with _when < end_time onto _ready            │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────▼───────────────────────────────────┐
  │ 6. DRAIN                                             base_events:2033 │
  │    ntodo = len(_ready)            <-- SNAPSHOT, taken once            │
  │    repeat ntodo times: handle = _ready.popleft(); handle._run()       │
  │    (this is the only place callbacks are actually called)             │
  └───────────────────────────────────────────────────────────────────────┘
```

Here is the whole method, uncut, because the rest of this section is commentary
on it:

```python
    def _run_once(self):
        """Run one full iteration of the event loop.

        This calls all currently ready callbacks, polls for I/O,
        schedules the resulting callbacks, and finally schedules
        'call_later' callbacks.
        """

        sched_count = len(self._scheduled)
        if (sched_count > _MIN_SCHEDULED_TIMER_HANDLES and
            self._timer_cancelled_count / sched_count >
                _MIN_CANCELLED_TIMER_HANDLES_FRACTION):
            # Remove delayed calls that were cancelled if their number
            # is too high
            new_scheduled = []
            for handle in self._scheduled:
                if handle._cancelled:
                    handle._scheduled = False
                else:
                    new_scheduled.append(handle)

            heapq.heapify(new_scheduled)
            self._scheduled = new_scheduled
            self._timer_cancelled_count = 0
        else:
            # Remove delayed calls that were cancelled from head of queue.
            while self._scheduled and self._scheduled[0]._cancelled:
                self._timer_cancelled_count -= 1
                handle = heapq.heappop(self._scheduled)
                handle._scheduled = False

        timeout = None
        if self._ready or self._stopping:
            timeout = 0
        elif self._scheduled:
            # Compute the desired timeout.
            timeout = self._scheduled[0]._when - self.time()
            if timeout > MAXIMUM_SELECT_TIMEOUT:
                timeout = MAXIMUM_SELECT_TIMEOUT
            elif timeout < 0:
                timeout = 0

        event_list = self._selector.select(timeout)
        self._process_events(event_list)
        # Needed to break cycles when an exception occurs.
        event_list = None

        # Handle 'later' callbacks that are ready.
        end_time = self.time() + self._clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = heapq.heappop(self._scheduled)
            handle._scheduled = False
            self._ready.append(handle)

        # This is the only place where callbacks are actually *called*.
        # All other places just add them to ready.
        # Note: We run all currently scheduled callbacks, but not any
        # callbacks scheduled by callbacks run this time around --
        # they will be run the next time (after another I/O poll).
        # Use an idiom that is thread-safe without using locks.
        ntodo = len(self._ready)
        for i in range(ntodo):
            handle = self._ready.popleft()
            if handle._cancelled:
                continue
            if self._debug:
                try:
                    self._current_handle = handle
                    t0 = self.time()
                    handle._run()
                    dt = self.time() - t0
                    if dt >= self.slow_callback_duration:
                        logger.warning('Executing %s took %.3f seconds',
                                       _format_handle(handle), dt)
                finally:
                    self._current_handle = None
            else:
                handle._run()
        handle = None  # Needed to break cycles when an exception occurs.
```

— `Lib/asyncio/base_events.py:1970-2051 — BaseEventLoop._run_once()`

### 1.4 Step 1 — cancelled-timer hygiene

A `TimerHandle` cannot be removed from the middle of a heap cheaply. `cancel()`
therefore does not remove it; it sets a flag and tells the loop:

```python
    def cancel(self):
        if not self._cancelled:
            self._loop._timer_handle_cancelled(self)
        super().cancel()
```

— `Lib/asyncio/events.py:157-160 — TimerHandle.cancel()`

```python
    def _timer_handle_cancelled(self, handle):
        """Notification that a TimerHandle has been cancelled."""
        if handle._scheduled:
            self._timer_cancelled_count += 1
```

— `Lib/asyncio/base_events.py:1965-1968 — BaseEventLoop._timer_handle_cancelled()`

So `_timer_cancelled_count` is a running estimate of how much dead weight the
heap is carrying. Step 1 uses it to choose between two strategies, governed by
two module constants:

```python
# Minimum number of _scheduled timer handles before cleanup of
# cancelled handles is performed.
_MIN_SCHEDULED_TIMER_HANDLES = 100

# Minimum fraction of _scheduled timer handles that are cancelled
# before cleanup of cancelled handles is performed.
_MIN_CANCELLED_TIMER_HANDLES_FRACTION = 0.5
```

— `Lib/asyncio/base_events.py:56-62`

- **Cheap path (the `else` branch).** While the *head* of the heap is a cancelled
  handle, pop it and decrement the counter. This is O(log n) per removal and
  touches nothing else. Cancelled handles buried behind live ones stay put.
- **Compaction (the `if` branch).** Only when there are more than 100 scheduled
  timers *and* more than half of them are believed cancelled: walk the whole
  list, keep the live ones, `heapq.heapify` the survivors — O(n) — and reset the
  counter to zero.

Both constants and the whole mechanism are **[impl detail]**. Neither appears
anywhere in `docs.python.org`. They are, however, pinned by the test suite, which
imports them by name and computes its fixtures from them:

```python
        # Need enough events to pass _MIN_CANCELLED_TIMER_HANDLES_FRACTION
        # so that deletion of cancelled events will occur on next _run_once
        add_cancel_count = int(math.ceil(
            base_events._MIN_SCHEDULED_TIMER_HANDLES *
            base_events._MIN_CANCELLED_TIMER_HANDLES_FRACTION)) + 1
```

— `Lib/test/test_asyncio/test_base_events.py:468-472 — BaseEventLoopTests.test__run_once_cancelled_event_cleanup()`

**An observation about the counter.** `_timer_cancelled_count` is decremented in
exactly one place — the head-pop loop at `base_events.py:1996-1999` — and reset in
exactly one other — the compaction branch at `base_events.py:1993`. Step 5, which
also removes handles from `_scheduled`, does not touch it:

```python
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = heapq.heappop(self._scheduled)
            handle._scheduled = False
            self._ready.append(handle)
```

— `Lib/asyncio/base_events.py:2019-2025`

There is no `_cancelled` test there. A cancelled timer that is *not* at the head
during step 1 (because a live timer with an earlier deadline is in front of it)
but *is* due during step 5 gets popped into `_ready` and skipped at the drain
(`base_events.py:2036-2037`) — while `_timer_cancelled_count` keeps counting it.
This is reproducible:

```python
# written for this document, not CPython source
import asyncio
loop = asyncio.new_event_loop()
def cb(): pass
now = loop.time()
loop.call_at(now - 1.0, cb)                  # due, live, sorts first
h = loop.call_at(now - 0.5, cb); h.cancel()  # due, cancelled, sorts behind it
print(loop._timer_cancelled_count, len(loop._scheduled))   # -> 1 2
loop._run_once()
print(loop._timer_cancelled_count, len(loop._scheduled))   # -> 1 0
loop.close()
```

Run on the install described above, this prints `1 2` then `1 0`: the heap is
empty but the loop still believes one cancelled timer is in it. The consequence
is bounded and benign — the ratio `_timer_cancelled_count / sched_count` is
inflated, so compaction can fire earlier than the 50 % rule suggests, and
compaction is correct regardless of the counter because it resets it. It is not
a correctness bug, but it does mean the counter is an *upper bound* on cancelled
scheduled handles, not a count of them. I found no CPython issue describing this;
see [§9](#9-what-could-not-be-verified).

### 1.5 Step 2 — the timeout, and what "blocking" means here

```python
        timeout = None
        if self._ready or self._stopping:
            timeout = 0
        elif self._scheduled:
            # Compute the desired timeout.
            timeout = self._scheduled[0]._when - self.time()
            if timeout > MAXIMUM_SELECT_TIMEOUT:
                timeout = MAXIMUM_SELECT_TIMEOUT
            elif timeout < 0:
                timeout = 0
```

— `Lib/asyncio/base_events.py:2001-2010`

Three cases, in priority order:

1. **`timeout = 0`** if anything is already ready, or if `stop()` has been called.
   The selector is still consulted, but it returns immediately. This is the branch
   that makes the documented `stop()` behaviour true — see
   [§7.2](#72-pep-3156-says-stop-stops-short-of-polling-for-io-the-313-docs-and-the-source-say-it-polls-once).
2. **`timeout = head_deadline - now`, clamped** if there are timers but nothing
   ready. Clamped below at `0` (a timer already past due must not produce a
   negative timeout, which some selectors read as "block forever") and above at
   `MAXIMUM_SELECT_TIMEOUT = 24 * 3600` (`base_events.py:67-68`, comment: "Maximum
   timeout passed to select to avoid OS limitations").
3. **`timeout = None`** if there is nothing ready and nothing scheduled. The
   selector blocks indefinitely, until an fd becomes ready — including the
   self-pipe fd, which is how another thread gets the loop's attention. See
   [§5](#5-where-the-loop-blocks-reentrancy-and-threads).

The clamp is not a limit on how long a timer can be: a timer 30 days out simply
costs 30 iterations of `_run_once`, each waking, finding the head still in the
future, and re-blocking for another day. **[impl detail]** The user-visible
consequence is documented, in the form of a history note:

> **versionchanged:: 3.8**
> In Python 3.7 and earlier with the default event loop implementation, the
> *delay* could not exceed one day. This has been fixed in Python 3.8.

— [`loop.call_later`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.call_later),
quoted from `Doc/library/asyncio-eventloop.rst:311-314` at tag `v3.13.11`

### 1.6 Step 3 — `select()`

```python
        event_list = self._selector.select(timeout)
```

— `Lib/asyncio/base_events.py:2012`

`self._selector` is set by `BaseSelectorEventLoop.__init__`:

```python
        if selector is None:
            selector = selectors.DefaultSelector()
        logger.debug('Using selector: %s', selector.__class__.__name__)
        self._selector = selector
        self._make_self_pipe()
        self._transports = weakref.WeakValueDictionary()
```

— `Lib/asyncio/selector_events.py:62-67 — BaseSelectorEventLoop.__init__()`

On Linux `DefaultSelector` is `EpollSelector` (`Lib/selectors.py:597`), whose
`select` is the last stop before the kernel:

```python
        def select(self, timeout=None):
            if timeout is None:
                timeout = -1
            elif timeout <= 0:
                timeout = 0
            else:
                # epoll_wait() has a resolution of 1 millisecond, round away
                # from zero to wait *at least* timeout seconds.
                timeout = math.ceil(timeout * 1e3) * 1e-3

            # epoll_wait() expects `maxevents` to be greater than zero;
            # we want to make sure that `select()` can be called when no
            # FD is registered.
            max_ev = len(self._fd_to_key) or 1
```

— `Lib/selectors.py:435-448 — EpollSelector.select()`

Two details that matter. `timeout=None` becomes `-1`, epoll's "block forever".
And the sub-millisecond rounding is **away from zero** — a 1.2 ms asyncio timeout
becomes a 2 ms `epoll_wait`, deliberately, so that the sleep is never *short*.
That interacts with step 5's clock-resolution fudge in the opposite direction;
see [§4.5](#45-the-clock-resolution-fudge).

The `select()` contract is documented on the abstract base:

> ```
> timeout -- if timeout > 0, this specifies the maximum wait time, in
>            seconds
>            if timeout <= 0, the select() call won't block, and will
>            report the currently ready file objects
>            if timeout is None, select() will block until a monitored
>            file object becomes ready
> ```

— `Lib/selectors.py:164-169 — BaseSelector.select()` docstring **[guaranteed]**

### 1.7 Step 4 — events become callbacks

```python
    def _process_events(self, event_list):
        for key, mask in event_list:
            fileobj, (reader, writer) = key.fileobj, key.data
            if mask & selectors.EVENT_READ and reader is not None:
                if reader._cancelled:
                    self._remove_reader(fileobj)
                else:
                    self._add_callback(reader)
            if mask & selectors.EVENT_WRITE and writer is not None:
                if writer._cancelled:
                    self._remove_writer(fileobj)
                else:
                    self._add_callback(writer)
```

— `Lib/asyncio/selector_events.py:740-752 — BaseSelectorEventLoop._process_events()`

The whole of asyncio's I/O dispatch is this. `key.data` — the opaque payload the
`selectors` module carries alongside each registration — is always a
two-tuple `(reader_handle, writer_handle)`, either element possibly `None`. On
readiness, the corresponding `Handle` is pushed onto `_ready`:

```python
    def _add_callback(self, handle):
        """Add a Handle to _ready."""
        if not handle._cancelled:
            self._ready.append(handle)
```

— `Lib/asyncio/base_events.py:1955-1958 — BaseEventLoop._add_callback()`

**No user code runs in step 4.** `_process_events` only moves handles between
data structures. On the abstract base, it is not even implemented:

```python
    def _process_events(self, event_list):
        """Process selector events."""
        raise NotImplementedError
```

— `Lib/asyncio/base_events.py:550-552`

This is the seam between `BaseEventLoop` (scheduling, timers, the ready queue)
and `BaseSelectorEventLoop` / `IocpProactor` (multiplexing). PEP 3156 describes
the split in its opening paragraph, which the module docstring repeats almost
verbatim:

> The event loop can be broken up into a multiplexer (the part responsible for
> notifying us of I/O events) and the event loop proper, which wraps a
> multiplexer with functionality for scheduling callbacks, immediately or at a
> given time in the future.

— `Lib/asyncio/base_events.py:3-6` (module docstring)

### 1.8 Step 6 — the drain, and why `ntodo` is snapshotted

This is the part worth slowing down for. The code again:

```python
        # This is the only place where callbacks are actually *called*.
        # All other places just add them to ready.
        # Note: We run all currently scheduled callbacks, but not any
        # callbacks scheduled by callbacks run this time around --
        # they will be run the next time (after another I/O poll).
        # Use an idiom that is thread-safe without using locks.
        ntodo = len(self._ready)
        for i in range(ntodo):
            handle = self._ready.popleft()
```

— `Lib/asyncio/base_events.py:2027-2035`

The obvious alternative — `while self._ready: handle = self._ready.popleft()` —
would be shorter and is wrong for two independent reasons. The comment names both.

**Reason one: fairness. Without the snapshot, an I/O-starved loop is possible.**
Callbacks run during the drain routinely schedule more callbacks; that is the
whole mechanism by which a `Task` advances (see
[§2](#2-from-await-to-the-selector-and-back)). A `while` loop would run those too,
in the same iteration, and so would their children, and so on. A coroutine that
does `while True: await asyncio.sleep(0)` — which is a bare `yield` that
re-schedules the task with `call_soon` (`Lib/asyncio/tasks.py:691-707`,
`Lib/asyncio/tasks.py:355-357`) — would keep `_ready` permanently non-empty and
the loop would never return to `select()`. Every socket in the process would
stall. With the snapshot, that coroutine gets exactly one step per iteration, and
step 3 runs in between.

The comment states the rule as a guarantee of the design — *"We run all currently
scheduled callbacks, but not any callbacks scheduled by callbacks run this time
around — they will be run the next time (after another I/O poll)"* — and CPython's
own test suite asserts it directly:

```python
    def test__run_once_schedule_handle(self):
        handle = None
        processed = False

        def cb(loop):
            nonlocal processed, handle
            processed = True
            handle = loop.call_soon(lambda: True)

        h = asyncio.TimerHandle(time.monotonic() - 1, cb, (self.loop,),
                                self.loop, None)

        self.loop._process_events = mock.Mock()
        self.loop._scheduled.append(h)
        self.loop._run_once()

        self.assertTrue(processed)
        self.assertEqual([handle], list(self.loop._ready))
```

— `Lib/test/test_asyncio/test_base_events.py:405-422`

After one `_run_once()`, the callback scheduled *by* a callback is still sitting
in `_ready`, unrun. The rule is also surfaced in the 3.13 reference, though only
in the context of `stop()`:

> If :meth:`stop` is called while :meth:`run_forever` is running, the loop will
> run the current batch of callbacks and then exit. Note that new callbacks
> scheduled by callbacks will not run in this case; instead, they will run the
> next time :meth:`run_forever` or :meth:`run_until_complete` is called.

— [`loop.run_forever`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.run_forever),
quoted from `Doc/library/asyncio-eventloop.rst:134-138` **[guaranteed]** —
note that "the current batch" is exactly `ntodo`.

**Reason two: thread safety without a lock.** `call_soon_threadsafe` appends to
`_ready` from an arbitrary OS thread (`base_events.py:881`, via `_call_soon`). The
loop thread is concurrently popping from the left. The snapshot makes that
interleaving safe without any mutex, because:

- `deque.append` and `deque.popleft` are individually atomic —
  > Deques support thread-safe, memory efficient appends and pops from either
  > side of the deque with approximately the same *O*(1) performance in either
  > direction.
  >
  > — [`collections.deque`, Python 3.13 docs](https://docs.python.org/3.13/library/collections.html#collections.deque),
  > quoted from `Doc/library/collections.rst:458-461` **[guaranteed]**
- `ntodo` is read once, before any popping, so a concurrent append can only make
  the real length *larger* than `ntodo`, never smaller. The drain therefore never
  pops more than it counted, and never hits an `IndexError`.
- Nothing else in the loop pops from `_ready`. `close()` calls `self._ready.clear()`
  (`base_events.py:750`) but refuses to run while the loop is running
  (`base_events.py:743-744`).

A `while self._ready` loop would also be memory-safe, but it would have the
starvation problem *and* a livelock problem: a producer thread appending faster
than the loop drains would pin the loop in the drain indefinitely.

**Cancelled handles still consume a slot.** Line 2036-2037 skips a cancelled
handle without running it, but the `for i in range(ntodo)` counter has already
budgeted for it. So cancelling a `call_soon` handle does not remove it from
`_ready`; it only makes the drain step over it. **[impl detail]**

**Debug mode is checked per handle, not per iteration.** `if self._debug:` sits
inside the loop (line 2038), so `set_debug()` taking effect mid-drain is
observable. In debug mode each callback is timed and anything slower than
`self.slow_callback_duration` (default `0.1`, `base_events.py:437`) is logged.
This is documented:

> Callbacks taking longer than 100 milliseconds are logged. The
> :attr:`loop.slow_callback_duration` attribute can be used to set the minimum
> execution duration in seconds that is considered "slow".

— [Debug Mode, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-dev.html#debug-mode),
quoted from `Doc/library/asyncio-dev.rst:56-58` **[guaranteed]**

**`handle = None` at line 2051** and `event_list = None` at line 2015 are not
tidiness. Both are commented "Needed to break cycles when an exception occurs" —
if `_run_once` raises, the frame is captured in the traceback, and a live local
referring to a handle that refers to a task that refers to the frame is a
reference cycle that only the cyclic GC can collect. The same idiom appears at
`events.py:105` (`Handle._run`), `tasks.py:296` and `tasks.py:371` (`Task.__step`).
**[impl detail]**

### 1.9 What `Handle._run` actually does

```python
    def _run(self):
        try:
            self._context.run(self._callback, *self._args)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            cb = format_helpers._format_callback_source(
                self._callback, self._args,
                debug=self._loop.get_debug())
            msg = f'Exception in callback {cb}'
            context = {
                'message': msg,
                'exception': exc,
                'handle': self,
            }
            if self._source_traceback:
                context['source_traceback'] = self._source_traceback
            self._loop.call_exception_handler(context)
        self = None  # Needed to break cycles when an exception occurs.
```

— `Lib/asyncio/events.py:87-105 — Handle._run()`

Three things:

1. **The callback runs inside a `contextvars.Context`**, never bare. The context
   is captured at `Handle` construction time:

   ```python
       def __init__(self, callback, args, loop, context=None):
           if context is None:
               context = contextvars.copy_context()
           self._context = context
   ```

   — `Lib/asyncio/events.py:36-39 — Handle.__init__()`

   This is PEP 567's asyncio integration. The PEP sketches it slightly
   differently — it puts the `copy_context()` inside `call_soon` —

   > ```python
   >     def call_soon(self, callback, *args, context=None):
   >         if context is None:
   >             context = contextvars.copy_context()
   >
   >         # ... some time later
   >         context.run(callback, *args)
   > ```
   >
   > — [PEP 567 § asyncio](https://peps.python.org/pep-0567/#asyncio)

   — but the observable behaviour is identical, because `call_soon` constructs the
   `Handle` synchronously (`base_events.py:852-857`). PEP 567's backwards-
   compatibility section states the contract:

   > 2. ``asyncio.Loop.call_at()``, ``asyncio.Loop.call_later()``,
   >    ``asyncio.Loop.call_soon()``, and ``asyncio.Future.add_done_callback()``
   >    run callback functions in the context they were called in. A new
   >    *context* keyword-only parameter can be used to specify a custom context.
   >
   > — [PEP 567 § Backwards Compatibility](https://peps.python.org/pep-0567/#backwards-compatibility)
   > **[guaranteed]**

2. **Exceptions are swallowed into the loop's exception handler**, not propagated
   out of `_run_once`. A callback that raises does not stop the loop. This is what
   produces the familiar `Exception in callback ...` log line.

3. **`SystemExit` and `KeyboardInterrupt` are re-raised** and therefore *do*
   escape `_run_once`, unwind `run_forever`, and hit the `finally:` that runs
   `_run_forever_cleanup()`. This asymmetry is deliberate and appears in the same
   shape all through `asyncio` — for example `Task.__step_run_and_handle_result`
   at `tasks.py:318-320` and `_SelectorSocketTransport._read_ready__data_received`
   at `selector_events.py:1008-1009`.

---

## 2. From `await` to the selector and back

This section traces one complete round trip. The hinge of the whole design is a
single attribute name, `_asyncio_future_blocking`, and the protocol around it.

### 2.1 The round trip, in one picture

```
  YOUR COROUTINE                     TASK                         LOOP / SELECTOR
  ──────────────                     ────                         ───────────────

  data = await loop.sock_recv(s, n)
        │
        │ sock_recv tries sock.recv(n) first      selector_events.py:374-377
        │   └─ succeeded? return immediately, coroutine never suspends
        │
        │ blocked. create the Future:             selector_events.py:378
        │   fut = self.create_future()   ───────────────────►  futures.Future
        │ register interest:                      selector_events.py:381
        │   self._add_reader(fd, self._sock_recv, fut, sock, n)
        │                                 ───────►  Handle(_sock_recv, ...)
        │                                 ───────►  selector.register(
        │                                              fd, EVENT_READ,
        │                                              (handle, None))
        │                                                  └─► epoll_ctl(ADD)
        │ await fut
        ▼
    Future.__await__            futures.py:283-289
      self._asyncio_future_blocking = True
      yield self  ─────────────────►
                              __step_run_and_handle_result
                              tasks.py:324-343
                                blocking = getattr(result,
                                    '_asyncio_future_blocking', None)
                                result._asyncio_future_blocking = False
                                result.add_done_callback(self.__wakeup, ...)
                                self._fut_waiter = result
                                return          ──► control back to _run_once
                                                    ──► select() blocks

                                                 ═══ kernel: data arrives ═══
                                                    epoll_wait returns (fd, EPOLLIN)

                                                 _process_events        sel_ev:740
                                                   _ready.append(handle)

                                                 drain: handle._run()   base:2050
                                                   → _sock_recv(fut, sock, n)
                                                        sel_ev:390-404
                                                     data = sock.recv(n)
                                                     fut.set_result(data)
                                                        futures.py:248-258
                                                          → __schedule_callbacks
                                                          → call_soon(__wakeup,
                                                                      fut)

                                                 next iteration, drain:
                                                   Task.__wakeup(fut)   tasks:373
                                                     fut.result()  (may raise)
                                                     self.__step()
                              __step / __step_run_and_handle_result
                                self._fut_waiter = None
                                result = coro.send(None)   ◄── resumes here
        ▲                                          tasks.py:304
        │
  data is the value                Future.__await__ resumes past the yield,
  returned by await                returns self.result()          futures.py:289
```

### 2.2 The fast path nobody mentions

`sock_recv` does not create a Future unless it has to:

```python
    async def sock_recv(self, sock, n):
        """Receive data from the socket.

        The return value is a bytes object representing the data received.
        The maximum amount of data to be received at once is specified by
        nbytes.
        """
        base_events._check_ssl_socket(sock)
        if self._debug and sock.gettimeout() != 0:
            raise ValueError("the socket must be non-blocking")
        try:
            return sock.recv(n)
        except (BlockingIOError, InterruptedError):
            pass
        fut = self.create_future()
        fd = sock.fileno()
        self._ensure_fd_no_transport(fd)
        handle = self._add_reader(fd, self._sock_recv, fut, sock, n)
        fut.add_done_callback(
            functools.partial(self._sock_read_done, fd, handle=handle))
        return await fut
```

— `Lib/asyncio/selector_events.py:364-384 — BaseSelectorEventLoop.sock_recv()`

If the socket already has data buffered, `sock.recv(n)` returns it and the
coroutine returns *without ever suspending*: no Future, no selector registration,
no trip through the loop. `await loop.sock_recv(...)` is then just a function
call that happens to be spelled with `await`. **[impl detail]** — the docs for
`loop.sock_recv` say only "Receive up to *nbytes* from *sock*"
(`Doc/library/asyncio-eventloop.rst:1049-1057`) and promise nothing about
suspension. The same optimisation appears on the write side:

```python
        if not self._buffer:
            # Optimization: try to send now.
            try:
                n = self._sock.send(data)
```

— `Lib/asyncio/selector_events.py:1064-1067 — _SelectorSocketTransport.write()`

### 2.3 Registering with the selector

```python
    def _add_reader(self, fd, callback, *args):
        self._check_closed()
        handle = events.Handle(callback, args, self, None)
        key = self._selector.get_map().get(fd)
        if key is None:
            self._selector.register(fd, selectors.EVENT_READ,
                                    (handle, None))
        else:
            mask, (reader, writer) = key.events, key.data
            self._selector.modify(fd, mask | selectors.EVENT_READ,
                                  (handle, writer))
            if reader is not None:
                reader.cancel()
        return handle
```

— `Lib/asyncio/selector_events.py:274-287 — BaseSelectorEventLoop._add_reader()`

Points worth making explicit:

- **`register` vs `modify`.** The selector holds *one* registration per fd with a
  combined read/write mask. First interest in an fd is a `register`
  (`epoll_ctl(EPOLL_CTL_ADD)`); adding the other direction is a `modify`
  (`EPOLL_CTL_MOD`) that ORs the bit in. `_remove_reader`
  (`selector_events.py:289-306`) reverses it, and calls `unregister` only when the
  mask goes empty.
- **One reader per fd, and the old one is silently cancelled.** `if reader is not
  None: reader.cancel()`. This *is* documented:
  > Any preexisting callback registered for *fd* is cancelled and replaced by
  > *callback*.
  >
  > — [`loop.add_reader`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.add_reader),
  > quoted from `Doc/library/asyncio-eventloop.rst:1010-1011` **[guaranteed]**
- **`context=None` at registration**, so `Handle.__init__` calls
  `contextvars.copy_context()` — the I/O callback inherits the context of whoever
  registered it, not of whoever's data happens to arrive.
- **`_add_reader` returns the `Handle`; the public `add_reader` throws it away.**

  ```python
      def add_reader(self, fd, callback, *args):
          """Add a reader callback."""
          self._ensure_fd_no_transport(fd)
          self._add_reader(fd, callback, *args)
  ```

  — `Lib/asyncio/selector_events.py:344-347`

  PEP 3156 specified exactly this: *"Note that `add_reader()`, `add_writer()` and
  `add_signal_handler()` do not return Handles."*
  ([PEP 3156 § Handles](https://peps.python.org/pep-3156/#handles)) **[guaranteed]**
  The internal `_add_reader` returns one because `sock_recv` needs it, to decide
  in `_sock_read_done` whether the reader it installed is still the live one:

  ```python
      def _sock_read_done(self, fd, fut, handle=None):
          if handle is None or not handle.cancelled():
              self.remove_reader(fd)
  ```

  — `Lib/asyncio/selector_events.py:386-388`

### 2.4 The `_asyncio_future_blocking` protocol

This is the hinge. Start with the declaration and its comment, which is the
clearest single statement of the design in the whole codebase:

```python
    # This field is used for a dual purpose:
    # - Its presence is a marker to declare that a class implements
    #   the Future protocol (i.e. is intended to be duck-type compatible).
    #   The value must also be not-None, to enable a subclass to declare
    #   that it is not compatible by setting this to None.
    # - It is set by __iter__() below so that Task._step() can tell
    #   the difference between
    #   `await Future()` or`yield from Future()` (correct) vs.
    #   `yield Future()` (incorrect).
    _asyncio_future_blocking = False
```

— `Lib/asyncio/futures.py:59-68 — Future` class attribute

And the awaiting side:

```python
    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            yield self  # This tells Task to wait for completion.
        if not self.done():
            raise RuntimeError("await wasn't used with future")
        return self.result()  # May raise too.

    __iter__ = __await__  # make compatible with 'yield from'.
```

— `Lib/asyncio/futures.py:283-291 — Future.__await__()`

Note the direction: CPython defines `__await__` and aliases `__iter__` to it.
PEP 492 prescribed the reverse — *"to enable Future objects in `await` statements,
the only change is to add `__await__ = __iter__` line to `asyncio.Future` class"*
([PEP 492 § Await Expression](https://peps.python.org/pep-0492/#await-expression))
— but the two are indistinguishable from outside. What PEP 492 *does* guarantee is
the mechanism the whole thing rests on:

> Any ``yield from`` chain of calls ends with a ``yield``. This is a fundamental
> mechanism of how *Futures* are implemented. Since, internally, coroutines are a
> special kind of generators, every ``await`` is suspended by a ``yield``
> somewhere down the chain of ``await`` calls (please refer to :pep:`3156` for a
> detailed explanation).

— [PEP 492 § Await Expression](https://peps.python.org/pep-0492/#await-expression)
**[guaranteed]**

That `yield self` at `futures.py:286` is the bottom of every chain. Whatever depth
of `await` you write, the object that finally comes out of `coro.send(None)` is a
Future, and the flag on it is `True`.

Now the receiving end — the single most important block of code in `asyncio`:

```python
        else:
            blocking = getattr(result, '_asyncio_future_blocking', None)
            if blocking is not None:
                # Yielded Future must come from Future.__iter__().
                if futures._get_loop(result) is not self._loop:
                    new_exc = RuntimeError(
                        f'Task {self!r} got Future '
                        f'{result!r} attached to a different loop')
                    self._loop.call_soon(
                        self.__step, new_exc, context=self._context)
                elif blocking:
                    if result is self:
                        new_exc = RuntimeError(
                            f'Task cannot await on itself: {self!r}')
                        self._loop.call_soon(
                            self.__step, new_exc, context=self._context)
                    else:
                        result._asyncio_future_blocking = False
                        result.add_done_callback(
                            self.__wakeup, context=self._context)
                        self._fut_waiter = result
                        if self._must_cancel:
                            if self._fut_waiter.cancel(
                                    msg=self._cancel_message):
                                self._must_cancel = False
                else:
                    new_exc = RuntimeError(
                        f'yield was used instead of yield from '
                        f'in task {self!r} with {result!r}')
                    self._loop.call_soon(
                        self.__step, new_exc, context=self._context)

            elif result is None:
                # Bare yield relinquishes control for one event loop iteration.
                self._loop.call_soon(self.__step, context=self._context)
            elif inspect.isgenerator(result):
                # Yielding a generator is just wrong.
                new_exc = RuntimeError(
                    f'yield was used instead of yield from for '
                    f'generator in task {self!r} with {result!r}')
                self._loop.call_soon(
                    self.__step, new_exc, context=self._context)
            else:
                # Yielding something else is an error.
                new_exc = RuntimeError(f'Task got bad yield: {result!r}')
                self._loop.call_soon(
                    self.__step, new_exc, context=self._context)
```

— `Lib/asyncio/tasks.py:323-369 — Task.__step_run_and_handle_result()`

The attribute is doing three different jobs at once, and reading it as a
three-valued signal makes the design legible:

| `getattr(result, '_asyncio_future_blocking', None)` | Meaning | Task's response |
| --- | --- | --- |
| `None` — absent, or explicitly `None` | Not a Future at all | Fall through to the `result is None` / generator / bad-yield branches |
| `False` | Is a Future, but it was `yield`ed rather than `await`ed | `RuntimeError('yield was used instead of yield from ...')` |
| `True` | Is a Future and it suspended properly | Subscribe `__wakeup` to it, record it in `_fut_waiter`, return |

The `None` case is the duck-typing opt-out described in the class comment, and
`isfuture` implements exactly that rule:

```python
def isfuture(obj):
    """Check for a Future.

    This returns True when obj is a Future instance or is advertising
    itself as duck-type compatible by setting _asyncio_future_blocking.
    See comment in Future for more details.
    """
    return (hasattr(obj.__class__, '_asyncio_future_blocking') and
            obj._asyncio_future_blocking is not None)
```

— `Lib/asyncio/base_futures.py:13-21 — isfuture()`

(The `asyncio.isfuture` documentation drops the not-`None` condition — see
[§7.4](#74-isfuture-documents-a-weaker-test-than-it-performs).)

The `False` case catches the classic mistake. `yield fut` inside a coroutine
hands the Future to the Task without going through `Future.__await__`, so the
flag was never set to `True`, and the Task refuses rather than silently
mis-scheduling. This is why `__await__` sets the flag and `__step` immediately
clears it (`tasks.py:340`): the flag is a one-shot token, valid for exactly one
hand-off, minted by `__await__` and burned by `__step`. A second `yield` of the
same Future without a second `__await__` would be rejected.

And `Future.__await__` checks the other end of the same token:

```python
        if not self.done():
            raise RuntimeError("await wasn't used with future")
```

— `Lib/asyncio/futures.py:287-288`

If control comes back to `__await__` and the Future is still pending, somebody
resumed the coroutine without the Future being resolved — the Task's contract was
broken. The C implementation encodes the same check even more tightly, as a
bitfield read:

```c
    if (fut->fut_state == STATE_PENDING) {
        if (!fut->fut_blocking) {
            fut->fut_blocking = 1;
            *result = Py_NewRef(fut);
            return PYGEN_NEXT;
        }
        PyErr_SetString(PyExc_RuntimeError,
                        "await wasn't used with future");
        return PYGEN_ERROR;
    }
```

— `Modules/_asynciomodule.c:1572-1581 — FutureIter_am_send()` (CPython v3.13.11)

Empirically, on the install described above:

```python
# written for this document, not CPython source
f = asyncio.Future(loop=asyncio.new_event_loop())
f._asyncio_future_blocking          # -> False
it = f.__await__()
next(it) is f                       # -> True   (the future yields *itself*)
f._asyncio_future_blocking          # -> True
```

**The whole protocol is [impl detail].** The only place any of it surfaces in the
documentation is the definition of `asyncio.isfuture`
(`Doc/library/asyncio-future.rst:22-29`). No PEP specifies the attribute. PEP 3156
describes the layering it implements without naming it:

> The scheduler has no public interface. You interact with it by using
> ``yield from future`` and ``yield from task``. In fact, there is no single
> object representing the scheduler -- its behavior is implemented by the
> ``Task`` and ``Future`` classes using only the public interface of the event
> loop, so it will work with third-party event loop implementations, too.

— [PEP 3156 § The Scheduler](https://peps.python.org/pep-3156/#the-scheduler)
**[guaranteed]**

That sentence is the design constraint that produced `_asyncio_future_blocking`.
Because the scheduler may only use the *public* loop API — `call_soon`,
`create_future`, `time` — the Task cannot ask the loop "is this thing a Future of
yours?". It has to interrogate the yielded object itself. A duck-typed attribute
is the only tool available.

### 2.5 Waking up

When data arrives, step 4 queues the reader `Handle`, step 6 runs it, and the
callback is `_sock_recv`:

```python
    def _sock_recv(self, fut, sock, n):
        # _sock_recv() can add itself as an I/O callback if the operation can't
        # be done immediately. Don't use it directly, call sock_recv().
        if fut.done():
            return
        try:
            data = sock.recv(n)
        except (BlockingIOError, InterruptedError):
            return  # try again next time
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            fut.set_exception(exc)
        else:
            fut.set_result(data)
```

— `Lib/asyncio/selector_events.py:390-404`

`fut.done()` is checked first because the Future may have been cancelled between
registration and readiness, and a spurious wakeup (`BlockingIOError`) is treated
as "no data yet, stay registered". Then:

```python
    def set_result(self, result):
        """Mark the future done and set its result.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise exceptions.InvalidStateError(f'{self._state}: {self!r}')
        self._result = result
        self._state = _FINISHED
        self.__schedule_callbacks()
```

— `Lib/asyncio/futures.py:248-258 — Future.set_result()`

```python
    def __schedule_callbacks(self):
        """Internal: Ask the event loop to call all callbacks.

        The callbacks are scheduled to be called as soon as possible. Also
        clears the callback list.
        """
        callbacks = self._callbacks[:]
        if not callbacks:
            return

        self._callbacks[:] = []
        for callback, ctx in callbacks:
            self._loop.call_soon(callback, self, context=ctx)
```

— `Lib/asyncio/futures.py:158-170 — Future.__schedule_callbacks()`

**The callbacks are never called inline.** `set_result` returns having only
enqueued them. PEP 3156 makes this a guarantee:

> ``add_done_callback(fn)``. Add a callback to be run when the Future becomes
> done (or is cancelled). If the Future is already done (or cancelled), schedules
> the callback to using ``call_soon()``. Difference with :pep:`3148`: The callback
> is never called immediately, and always in the context of the caller [...] You
> can think of this as calling the callback through ``call_soon()``.

— [PEP 3156 § Futures](https://peps.python.org/pep-3156/#futures) **[guaranteed]**

The consequence is a full extra loop iteration between "the bytes arrived" and
"your coroutine sees them": `_sock_recv` runs in iteration *N*'s drain,
`call_soon` appends `__wakeup` to `_ready`, and the `ntodo` snapshot means it runs
in iteration *N+1*. Latency, in exchange for the strict serialisation guarantee
PEP 3156 calls out as *"an important guarantee: when two or more callbacks use or
modify shared state, each callback is guaranteed that while it is running, the
shared state isn't changed by another callback"*
([PEP 3156 § Basic Callbacks](https://peps.python.org/pep-3156/#basic-callbacks)).

Finally:

```python
    def __wakeup(self, future):
        try:
            future.result()
        except BaseException as exc:
            # This may also be a cancellation.
            self.__step(exc)
        else:
            # Don't pass the value of `future.result()` explicitly,
            # as `Future.__iter__` and `Future.__await__` don't need it.
            # If we call `_step(value, None)` instead of `_step()`,
            # Python eval loop would use `.send(value)` method call,
            # instead of `__next__()`, which is slower for futures
            # that return non-generator iterators from their `__iter__`.
            self.__step()
        self = None  # Needed to break cycles when an exception occurs.
```

— `Lib/asyncio/tasks.py:373-387 — Task.__wakeup()`

`__wakeup` calls `future.result()` purely to convert a stored exception (or a
cancellation) into a live raise, then forwards it into the coroutine via
`coro.throw`. The *value* is deliberately discarded and re-fetched by
`Future.__await__` resuming past its `yield` (`futures.py:289`) — the comment
explains the performance reason.

And `__step`:

```python
    def __step(self, exc=None):
        if self.done():
            raise exceptions.InvalidStateError(
                f'_step(): already done: {self!r}, {exc!r}')
        if self._must_cancel:
            if not isinstance(exc, exceptions.CancelledError):
                exc = self._make_cancelled_error()
            self._must_cancel = False
        self._fut_waiter = None

        _enter_task(self._loop, self)
        try:
            self.__step_run_and_handle_result(exc)
        finally:
            _leave_task(self._loop, self)
            self = None  # Needed to break cycles when an exception occurs.
```

— `Lib/asyncio/tasks.py:281-296 — Task.__step()`

```python
        coro = self._coro
        try:
            if exc is None:
                # We use the `send` method directly, because coroutines
                # don't have `__iter__` and `__next__` methods.
                result = coro.send(None)
            else:
                result = coro.throw(exc)
```

— `Lib/asyncio/tasks.py:299-306`

`_enter_task` / `_leave_task` are what make `asyncio.current_task()` work, and
they enforce non-reentrancy:

```python
def _enter_task(loop, task):
    current_task = _current_tasks.get(loop)
    if current_task is not None:
        raise RuntimeError(f"Cannot enter into task {task!r} while another "
                           f"task {current_task!r} is being executed.")
    _current_tasks[loop] = task
```

— `Lib/asyncio/tasks.py:1057-1062`

### 2.6 The transport path, for contrast

`sock_recv` is the low-level API. A transport registers its reader *once*, at
construction, and never deregisters it per-read:

```python
        self._loop.call_soon(self._protocol.connection_made, self)
        # only start reading when connection_made() has been called
        self._loop.call_soon(self._add_reader,
                             self._sock_fd, self._read_ready)
        if waiter is not None:
            # only wake up the waiter when connection_made() has been called
            self._loop.call_soon(futures._set_result_unless_cancelled,
                                 waiter, None)
```

— `Lib/asyncio/selector_events.py:944-951 — _SelectorSocketTransport.__init__()`

Note that even `_add_reader` is deferred through `call_soon`, so that
`connection_made` is guaranteed to have run before any `data_received`. Then
every readiness event drives:

```python
    def _read_ready__data_received(self):
        if self._conn_lost:
            return
        try:
            data = self._sock.recv(self.max_size)
        except (BlockingIOError, InterruptedError):
            return
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            self._fatal_error(exc, 'Fatal read error on socket transport')
            return

        if not data:
            self._read_ready__on_eof()
            return

        try:
            self._protocol.data_received(data)
```

— `Lib/asyncio/selector_events.py:1001-1019`

There is **no Future anywhere in the transport read path**. `data_received` is a
plain callback. The Future only reappears one layer up, in `StreamReader`, when
somebody `await`s. PEP 3156 describes that layering as deliberate — the callback
API is the primitive, the coroutine API is optional:

> This is a separate toplevel section because its status is different from the
> event loop interface. Usage of coroutines is optional, and it is perfectly fine
> to write code using callbacks only.

— [PEP 3156 § Coroutines and the Scheduler](https://peps.python.org/pep-3156/#coroutines-and-the-scheduler)
**[guaranteed]**

`max_size = 256 * 1024` (`selector_events.py:762`) is the per-`recv` ceiling and
is **[impl detail]**.

---

## 3. Task, Future and the loop: who owns what

### 3.1 The three-way split

| | Owns | Does not own |
| --- | --- | --- |
| **`BaseEventLoop`** | `_ready`, `_scheduled`, the selector, the clock, the thread identity, the exception handler, the executor. Calls callbacks. | Anything about coroutines. It has never heard of `await`. |
| **`Future`** | One result-or-exception slot, a state enum, a list of done-callbacks, and a reference to its loop. Turns `set_result` into `loop.call_soon`. | Any knowledge of who is waiting, or why. |
| **`Task`** | A coroutine object, a `contextvars.Context`, cancellation bookkeeping (`_must_cancel`, `_num_cancels_requested`, `_cancel_message`), and `_fut_waiter`. Drives `coro.send` / `coro.throw`. | The ready queue, the selector, time. |

The `Task` is a `Future` by inheritance:

```python
class Task(futures._PyFuture):  # Inherit Python Task implementation
                                # from a Python Future implementation.
```

— `Lib/asyncio/tasks.py:71-72`

and it publishes its own state machine in a comment that is worth having in full,
because it is the precise contract between the three parties:

```python
    # An important invariant maintained while a Task not done:
    # _fut_waiter is either None or a Future.  The Future
    # can be either done() or not done().
    # The task can be in any of 3 states:
    #
    # - 1: _fut_waiter is not None and not _fut_waiter.done():
    #      __step() is *not* scheduled and the Task is waiting for _fut_waiter.
    # - 2: (_fut_waiter is None or _fut_waiter.done()) and __step() is scheduled:
    #       the Task is waiting for __step() to be executed.
    # - 3:  _fut_waiter is None and __step() is *not* scheduled:
    #       the Task is currently executing (in __step()).
    #
    # * In state 1, one of the callbacks of __fut_waiter must be __wakeup().
    # * The transition from 1 to 2 happens when _fut_waiter becomes done(),
    #   as it schedules __wakeup() to be called (which calls __step() so
    #   we way that __step() is scheduled).
    # * It transitions from 2 to 3 when __step() is executed, and it clears
    #   _fut_waiter to None.
```

— `Lib/asyncio/tasks.py:76-93` **[impl detail]**

`_fut_waiter` is the only structural difference from a plain `Future`, and it
exists for exactly one reason: cancellation has to propagate *inward*.

```python
        if self._fut_waiter is not None:
            if self._fut_waiter.cancel(msg=msg):
                # Leave self._fut_waiter; it may be a Task that
                # catches and ignores the cancellation so we may have
                # to cancel it again later.
                return True
        # It must be the case that self.__step is already scheduled.
        self._must_cancel = True
        self._cancel_message = msg
        return True
```

— `Lib/asyncio/tasks.py:229-238 — Task.cancel()`

Cancelling a Task in state 1 cancels the Future it is blocked on, which resolves
that Future, which schedules `__wakeup`, which raises `CancelledError` into the
coroutine. Cancelling in state 2 or 3 can't do that — there is nothing to
cancel — so it sets `_must_cancel` and the next `__step` converts it into a throw
(`tasks.py:285-288`).

`Task.cancel` also carries a commented-out block that is a small monument to how
hard this is:

```python
        self._num_cancels_requested += 1
        # These two lines are controversial.  See discussion starting at
        # https://github.com/python/cpython/pull/31394#issuecomment-1053545331
        # Also remember that this is duplicated in _asynciomodule.c.
        # if self._num_cancels_requested > 1:
        #     return False
```

— `Lib/asyncio/tasks.py:223-228`

"Also remember that this is duplicated in `_asynciomodule.c`" is the parity
requirement showing through in a source comment.

### 3.2 How the C accelerator is swapped in

Three modules do the same trick at the bottom of the file. `futures.py`:

```python
try:
    import _asyncio
except ImportError:
    pass
else:
    # _CFuture is needed for tests.
    Future = _CFuture = _asyncio.Future
```

— `Lib/asyncio/futures.py:419-425`

`tasks.py`:

```python
_PyTask = Task


try:
    import _asyncio
except ImportError:
    pass
else:
    # _CTask is needed for tests.
    Task = _CTask = _asyncio.Task
```

— `Lib/asyncio/tasks.py:390-399`

`events.py`, with a rationale attached:

```python
try:
    # get_event_loop() is one of the most frequently called
    # functions in asyncio.  Pure Python implementation is
    # about 4 times slower than C-accelerated.
    from _asyncio import (_get_running_loop, _set_running_loop,
                          get_running_loop, get_event_loop)
except ImportError:
    pass
else:
    # Alias C implementations for testing purposes.
    _c__get_running_loop = _get_running_loop
    _c__set_running_loop = _set_running_loop
    _c_get_running_loop = get_running_loop
    _c_get_event_loop = get_event_loop
```

— `Lib/asyncio/events.py:858-871`

and `tasks.py` again, for the task registry:

```python
try:
    from _asyncio import (_register_task, _register_eager_task,
                          _unregister_task, _unregister_eager_task,
                          _enter_task, _leave_task, _swap_current_task,
                          _scheduled_tasks, _eager_tasks, _current_tasks,
                          current_task)
except ImportError:
    pass
```

— `Lib/asyncio/tasks.py:1102-1109`

The pattern is always the same: define the pure-Python version, alias it to
`_Py*`, then rebind the public name to the C version and alias *that* to `_C*`.
Both implementations stay importable, which is what makes the parity test matrix
in [§3.4](#34-the-cpython-parity-requirement) possible. On the install described
above:

```
asyncio.Task is _asyncio.Task            -> True
asyncio.Future is _asyncio.Future        -> True
asyncio.tasks.current_task is C version  -> True
asyncio.events._get_running_loop.__module__ -> '_asyncio'
asyncio.tasks._scheduled_tasks is _asyncio._scheduled_tasks -> True
```

**What is *not* swapped:** `BaseEventLoop`. There is no C event loop in CPython.
`_ready`, `_scheduled`, `_run_once`, `call_soon`, `Handle`, `TimerHandle` and the
selector plumbing are pure Python, always. The C `Task` schedules itself by
calling the *Python* `loop.call_soon` through the normal attribute-lookup path:

```c
static int
call_soon(asyncio_state *state, PyObject *loop, PyObject *func, PyObject *arg,
          PyObject *ctx)
{
    PyObject *handle;

    if (ctx == NULL) {
        PyObject *stack[] = {loop, func, arg};
        size_t nargsf = 3 | PY_VECTORCALL_ARGUMENTS_OFFSET;
        handle = PyObject_VectorcallMethod(&_Py_ID(call_soon), stack, nargsf, NULL);
    }
```

— `Modules/_asynciomodule.c:288-297` (CPython v3.13.11)

That is PEP 3156's *"using only the public interface of the event loop"*
constraint, enforced in C.

### 3.3 What the C version actually accelerates

Reading `Modules/_asynciomodule.c`, the wins are structural rather than
algorithmic:

**1. Struct fields instead of instance dicts.** `Future` and `Task` become C
structs with a shared header macro:

```c
#define FutureObj_HEAD(prefix)                                              \
    PyObject_HEAD                                                           \
    PyObject *prefix##_loop;                                                \
    PyObject *prefix##_callback0;                                           \
    PyObject *prefix##_context0;                                            \
    PyObject *prefix##_callbacks;                                           \
    PyObject *prefix##_exception;                                           \
    PyObject *prefix##_exception_tb;                                        \
    PyObject *prefix##_result;                                              \
    PyObject *prefix##_source_tb;                                           \
    PyObject *prefix##_cancel_msg;                                          \
    PyObject *prefix##_cancelled_exc;                                       \
    fut_state prefix##_state;                                               \
    /* These bitfields need to be at the end of the struct
       so that these and bitfields from TaskObj are contiguous.
    */                                                                      \
    unsigned prefix##_log_tb: 1;                                            \
    unsigned prefix##_blocking: 1;
```

— `Modules/_asynciomodule.c:113-130`

`_asyncio_future_blocking` — a Python attribute access in the pure-Python path —
is a one-bit bitfield here, and `Task` reuses the header so the Future and Task
bitfields pack contiguously.

**2. A fast path that skips attribute lookup entirely.** `task_step_handle_result_impl`
checks the exact type first, and for an exact `Future`/`Task` reads the bitfield
directly rather than doing `getattr(result, '_asyncio_future_blocking', None)`:

```c
    /* Check if `result` is FutureObj or TaskObj (and not a subclass) */
    if (Future_CheckExact(state, result) || Task_CheckExact(state, result)) {
        PyObject *wrapper;
        PyObject *tmp;
        FutureObj *fut = (FutureObj*)result;

        /* Check if `result` future is attached to a different loop */
        if (fut->fut_loop != task->task_loop) {
            goto different_loop;
        }

        if (!fut->fut_blocking) {
            goto yield_insteadof_yf;
        }

        fut->fut_blocking = 0;
```

— `Modules/_asynciomodule.c:2876-2891`

The generic path — for third-party Future-likes — is still there, 60 lines further
down, doing the full `PyObject_GetOptionalAttr(result, &_Py_ID(_asyncio_future_blocking), &o)`
(`_asynciomodule.c:2949`) and `PyObject_SetAttr(... Py_False)` (`2979-2980`). So the
C version implements *both* the fast structural path and the documented duck-typed
protocol, and they must agree.

**3. A one-element callback fast path.** Most Futures have exactly one done
callback — the Task's `__wakeup`. The C version stores it in a dedicated
`fut_callback0` slot and only allocates a list from the second callback onward:

```c
           Callbacks in the future object are stored as follows:

              callback0 -- a pointer to the first callback
              callbacks -- a list of 2nd, 3rd, ... callbacks
```

— `Modules/_asynciomodule.c:638-641 — future_add_done_callback()`

**4. A coroutine type cache.** `is_coroutine` short-circuits on
`PyCoro_CheckExact` and otherwise consults a set of known-good types, so
`asyncio.iscoroutine()` — a Python call — runs once per type rather than once per
task:

```c
    /* Check if `type(coro)` is in the cache.
       Caching makes is_coroutine() function almost as fast as
       PyCoro_CheckExact() for non-native coroutine-like objects
       (like coroutines compiled with Cython).

       asyncio.iscoroutine() has its own type caching mechanism.
       This cache allows us to avoid the cost of even calling
       a pure-Python function in 99.9% cases.
    */
```

— `Modules/_asynciomodule.c:217-224`

**5. A free-list for the await iterator.** `Future.__await__` allocates an
iterator object on every await; the C version recycles them — but only in the
GIL-enabled build:

```c
#ifndef Py_GIL_DISABLED
    if (state->fi_freelist_len) {
        state->fi_freelist_len--;
        it = state->fi_freelist;
```

— `Modules/_asynciomodule.c:1755-1758 — future_new_iter()`

**6. `get_running_loop` on the thread state.** The Python version keeps the
running loop in a `threading.local`; the C version reads a field on the
`_PyThreadStateImpl` directly:

```c
    _PyThreadStateImpl *ts = (_PyThreadStateImpl *)_PyThreadState_GET();
    PyObject *loop = Py_XNewRef(ts->asyncio_running_loop);
```

— `Modules/_asynciomodule.c:3241-3242 — _asyncio__get_running_loop_impl()`

**7. Deferred task-name formatting.** `Task-1`, `Task-2` … are not formatted at
construction. The counter is stored as a `PyLong` in the name slot and turned into
a string only if `get_name()` is called:

```c
        // optimization: defer task name formatting
        // store the task counter as PyLong in the name
        // for deferred formatting in get_name
#ifdef Py_GIL_DISABLED
        unsigned long long counter = _Py_atomic_add_uint64(&state->task_name_counter, 1) + 1;
#else
        unsigned long long counter = ++state->task_name_counter;
#endif
```

— `Modules/_asynciomodule.c:2086-2093`

**How much is it worth?** Less than you would guess, and the reason is
instructive. Measured on the install described above (3 repetitions, best of
each):

```
_CTask   200k bare-yield steps: 0.286s
_PyTask  200k bare-yield steps: 0.319s      ratio 1.12x
C Task+Future    100k awaits:   0.278s
Py Task+Future   100k awaits:   0.411s      ratio 1.48x
```

(Benchmark written for this document; it constructs the loop, runs
`_CTask`/`_PyTask` over the same coroutine, and times `run_until_complete`.)

A 1.1×–1.5× improvement, not 10×. The reason is that every step of a Task still
goes through `loop.call_soon` → `events.Handle.__init__` → `contextvars.copy_context()`
→ `_ready.append` → `Handle._run` → `Context.run` — six pure-Python operations
per step, none of which the accelerator touches. The C module makes `Task` and
`Future` cheap; the *loop* remains the floor. That is a direct consequence of the
PEP 3156 layering quoted above: the scheduler may only use public loop API, so the
accelerator cannot reach into `_ready`.

### 3.4 The C/Python parity requirement

Because both implementations are live, they are tested against each other in a
matrix. `Lib/test/test_asyncio/test_tasks.py` instantiates the same
`BaseTaskTests` body six ways:

```python
@unittest.skipUnless(hasattr(futures, '_CFuture') and
                     hasattr(tasks, '_CTask'),
                     'requires the C _asyncio module')
class CTask_CFuture_Tests(BaseTaskTests, SetMethodsTest,
                          test_utils.TestCase):

    Task = getattr(tasks, '_CTask', None)
    Future = getattr(futures, '_CFuture', None)
```

— `Lib/test/test_asyncio/test_tasks.py:2821-2828`

and then, further down, `CTask_PyFuture_Tests` (2882-2885),
`PyTask_CFuture_Tests` (2890-2893), `PyTask_PyFuture_Tests` (2896-2900), plus two
subclass variants (`CTaskSubclass_PyFuture_Tests` 2865-2868,
`PyTask_CFutureSubclass_Tests` 2874-2877) generated by a decorator that also
injects an extra assertion:

```python
def add_subclass_tests(cls):
    BaseTask = cls.Task
    BaseFuture = cls.Future
    ...
    class CommonFuture:
        def __init__(self, *args, **kwargs):
            self.calls = collections.defaultdict(lambda: 0)
            super().__init__(*args, **kwargs)

        def add_done_callback(self, *args, **kwargs):
            self.calls['add_done_callback'] += 1
            return super().add_done_callback(*args, **kwargs)
```

— `Lib/test/test_asyncio/test_tasks.py:2710-2724`

with

```python
        self.assertEqual(
            dict(task.calls),
            {'add_done_callback': 1})
```

— `Lib/test/test_asyncio/test_tasks.py:2745-2747`

That is not a performance test. It asserts that a C `Task` awaiting a Python
`Future` (and every other cross combination) calls `add_done_callback` **exactly
once** — i.e. that the C fast path and the generic duck-typed path produce
identical observable call sequences. `test_futures.py` does the same for
`Future` alone (`CFutureTests` 704-708, `CSubFutureTests` 746-750, `PyFutureTests`
758-759, and `BaseFutureInheritanceTests` 1106-1144 run for both).

**One place where parity is not exact.** The Python `_get_running_loop` carries a
PID guard that the C one does not:

```python
# A TLS for the running event loop, used by _get_running_loop.
class _RunningLoop(threading.local):
    loop_pid = (None, None)


_running_loop = _RunningLoop()
...
def _get_running_loop():
    """Return the running event loop or None.

    This is a low-level function intended to be used by event loops.
    This function is thread-specific.
    """
    # NOTE: this function is implemented in C (see _asynciomodule.c)
    running_loop, pid = _running_loop.loop_pid
    if running_loop is not None and pid == os.getpid():
        return running_loop
```

— `Lib/asyncio/events.py:747-776`

versus `_asynciomodule.c:3241-3247`, which reads `ts->asyncio_running_loop` with
no PID check at all. The gap is closed elsewhere, by a fork hook that applies to
both:

```python
if hasattr(os, 'fork'):
    def on_fork():
        # Reset the loop and wakeupfd in the forked child process.
        if _event_loop_policy is not None:
            _event_loop_policy._local = BaseDefaultEventLoopPolicy._Local()
        _set_running_loop(None)
        signal.set_wakeup_fd(-1)

    os.register_at_fork(after_in_child=on_fork)
```

— `Lib/asyncio/events.py:874-882`

So the Python implementation is belt-and-braces and the C one relies on the hook.
Behaviourally equivalent on any platform with `os.register_at_fork`, but not the
same code. **[impl detail]**

### 3.5 What the loop refuses to know

Two `NotImplementedError` stubs on `BaseEventLoop` mark the boundary of the
"event loop proper":

```python
    def _write_to_self(self):
        """Write a byte to self-pipe, to wake up the event loop.

        This may be called from a different thread.

        The subclass is responsible for implementing the self-pipe.
        """
        raise NotImplementedError

    def _process_events(self, event_list):
        """Process selector events."""
        raise NotImplementedError
```

— `Lib/asyncio/base_events.py:541-552`

Everything above that line is portable scheduling; everything below it is
`BaseSelectorEventLoop` (Unix, and Windows' `SelectorEventLoop`) or
`ProactorEventLoop` (Windows IOCP).

---

## 4. Timers

### 4.1 `TimerHandle`

```python
class TimerHandle(Handle):
    """Object returned by timed callback registration methods."""

    __slots__ = ['_scheduled', '_when']

    def __init__(self, when, callback, args, loop, context=None):
        super().__init__(callback, args, loop, context)
        if self._source_traceback:
            del self._source_traceback[-1]
        self._when = when
        self._scheduled = False
```

— `Lib/asyncio/events.py:108-118`

Two fields on top of `Handle`: the absolute deadline, and a flag recording whether
this handle is currently sitting in the heap. `Handle` itself is `__slots__`-ed
too (`events.py:32-34`) — these objects are allocated per callback, so their size
matters.

The ordering methods make it heap-usable:

```python
    def __lt__(self, other):
        if isinstance(other, TimerHandle):
            return self._when < other._when
        return NotImplemented
```

— `Lib/asyncio/events.py:129-132`

`__lt__`, `__le__`, `__gt__`, `__ge__` all compare `_when` only. `__eq__`,
however, does not:

```python
    def __eq__(self, other):
        if isinstance(other, TimerHandle):
            return (self._when == other._when and
                    self._callback == other._callback and
                    self._args == other._args and
                    self._cancelled == other._cancelled)
        return NotImplemented
```

— `Lib/asyncio/events.py:149-155`

So two `TimerHandle`s with the same deadline but different callbacks are neither
`<` nor `>` nor `==` each other. The ordering is a *pre*order, not a total order.
`heapq` never needs more than `__lt__`, so this is harmless in practice — but it
is also exactly why the ordering of same-deadline timers is left undefined, which
is the one part of this that *is* promised:

> *callback* will be called exactly once. If two callbacks are scheduled for
> exactly the same time, the order in which they are called is undefined.

— [`loop.call_later`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.call_later),
quoted from `Doc/library/asyncio-eventloop.rst:289-291` **[guaranteed]**

PEP 3156 says the same: *"Callbacks scheduled in the past or at exactly the same
time will be called in an undefined order."*
([PEP 3156 § Basic Callbacks](https://peps.python.org/pep-3156/#basic-callbacks))

And `__hash__` is `hash(self._when)` (`events.py:126-127`), consistent with
`__eq__` being a refinement of `_when` equality.

### 4.2 `call_at` is the primitive; `call_later` is sugar

```python
    def call_at(self, when, callback, *args, context=None):
        """Like call_later(), but uses an absolute time.

        Absolute time corresponds to the event loop's time() method.
        """
        if when is None:
            raise TypeError("when cannot be None")
        self._check_closed()
        if self._debug:
            self._check_thread()
            self._check_callback(callback, 'call_at')
        timer = events.TimerHandle(when, callback, args, self, context)
        if timer._source_traceback:
            del timer._source_traceback[-1]
        heapq.heappush(self._scheduled, timer)
        timer._scheduled = True
        return timer
```

— `Lib/asyncio/base_events.py:805-821 — BaseEventLoop.call_at()`

```python
        timer = self.call_at(self.time() + delay, callback, *args,
                             context=context)
```

— `Lib/asyncio/base_events.py:799-800 — BaseEventLoop.call_later()`

This is PEP 3156's stated equivalence, implemented literally:

> ``call_at(when, callback, *args)``. This is like ``call_later()``, but the time
> is expressed as an absolute time. Returns a similar ``Handle``. There is a
> simple equivalency: ``loop.call_later(delay, callback, *args)`` is the same as
> ``loop.call_at(loop.time() + delay, callback, *args)``.

— [PEP 3156 § Basic Callbacks](https://peps.python.org/pep-3156/#basic-callbacks)
**[guaranteed]**

The practical consequence of `call_later` snapshotting `self.time()` *at
scheduling time* is that a delay is relative to when you scheduled it, not to
when the previous iteration ended — there is no drift accumulation from the loop
itself, only from however long the callback is delayed by a busy queue.

### 4.3 The clock

```python
    def time(self):
        """Return the time according to the event loop's clock.

        This is a float expressed in seconds since an epoch, but the
        epoch, precision, accuracy and drift are unspecified and may
        differ per event loop.
        """
        return time.monotonic()
```

— `Lib/asyncio/base_events.py:772-779 — BaseEventLoop.time()`

The docstring's disclaimer is stronger than the published documentation, which
commits to monotonicity:

> Return the current time, as a :class:`float` value, according to the event
> loop's internal monotonic clock.

— [`loop.time`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.time),
quoted from `Doc/library/asyncio-eventloop.rst:342-345`

and stronger still than PEP 3156, which explicitly permits `time.time()`:

> ``time()``. Returns the current time according to the event loop's clock. This
> may be ``time.time()`` or ``time.monotonic()`` or some other system-specific
> clock, but it must return a float expressing the time in units of approximately
> one second since some epoch. (No clock is perfect -- see :pep:`418`.)

— [PEP 3156 § Basic Callbacks](https://peps.python.org/pep-3156/#basic-callbacks)

So: **[guaranteed]** it is a float in approximately-seconds; **[guaranteed]** by
the 3.13 docs that it is monotonic; **[impl detail]** that it is precisely
`time.monotonic()`. The docs page also states the design intent plainly — *"Event
loop uses monotonic clocks to track time"*
(`Doc/library/asyncio-eventloop.rst:277-278`). `asyncio.timeout_at` spells out
what that means for callers:

> Please note: it is not POSIX time but a time with undefined starting base, e.g.
> the time of the system power on.

— `Lib/asyncio/timeouts.py:171-172 — timeout_at()` docstring

### 4.4 `_clock_resolution`

```python
        self._clock_resolution = time.get_clock_info('monotonic').resolution
```

— `Lib/asyncio/base_events.py:430 — BaseEventLoop.__init__()`

Captured once, at loop construction. It is used in exactly one place — step 5 of
`_run_once`.

### 4.5 The clock-resolution fudge

```python
        # Handle 'later' callbacks that are ready.
        end_time = self.time() + self._clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
```

— `Lib/asyncio/base_events.py:2017-2022`

A timer is considered due if `_when < now + resolution`, not `_when <= now`. The
loop deliberately fires timers *up to one clock tick early*, rather than burning
an entire extra iteration — another `select()`, another syscall — on a timer that
is within the clock's own measurement error of being due.

This is one of the few pieces of `_run_once` internals that made it into the
reference documentation, and it is stated as a note on both `call_later` and
`call_at`:

> .. note::
>
>    For performance, callbacks scheduled with :meth:`loop.call_later` may run up
>    to one clock-resolution early (see ``time.get_clock_info('monotonic').resolution``).

— [`loop.call_later`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.call_later),
quoted from `Doc/library/asyncio-eventloop.rst:301-305`; the same note appears at
`327-331` for `call_at` **[guaranteed]**

Note the two rounding decisions pull in opposite directions and roughly cancel:
`EpollSelector.select` rounds the *timeout* **up** to the next whole millisecond
so the sleep is never short (`Lib/selectors.py:441-443`), while `_run_once` treats
a timer as due one *resolution* **early**. On Linux `time.get_clock_info('monotonic').resolution`
is typically 1 ns, so the fudge is negligible there and the epoll rounding
dominates; on a platform with a coarse monotonic clock the fudge is what stops
timers being late by a full tick.

### 4.6 `asyncio.sleep`, the canonical timer user

```python
async def sleep(delay, result=None):
    """Coroutine that completes after a given time (in seconds)."""
    if delay <= 0:
        await __sleep0()
        return result

    if math.isnan(delay):
        raise ValueError("Invalid delay: NaN (not a number)")

    loop = events.get_running_loop()
    future = loop.create_future()
    h = loop.call_later(delay,
                        futures._set_result_unless_cancelled,
                        future, result)
    try:
        return await future
    finally:
        h.cancel()
```

— `Lib/asyncio/tasks.py:703-721 — sleep()`

A Future plus a `call_later` that resolves it — and, critically, `h.cancel()` in
the `finally`, so that a cancelled `sleep` does not leave a dead `TimerHandle` in
the heap forever. That `cancel()` is what increments `_timer_cancelled_count` and
eventually triggers the compaction described in
[§1.4](#14-step-1--cancelled-timer-hygiene). A server with ten thousand
`asyncio.wait_for`-style timeouts that mostly *don't* fire is precisely the
workload the compaction path exists for.

`delay <= 0` takes a different path entirely — no Future, no timer:

```python
@types.coroutine
def __sleep0():
    """Skip one event loop run cycle.

    This is a private helper for 'asyncio.sleep()', used
    when the 'delay' is set to 0.  It uses a bare 'yield'
    expression (which Task.__step knows how to handle)
    instead of creating a Future object.
    """
    yield
```

— `Lib/asyncio/tasks.py:691-700`

A bare `yield` produces `result is None` in `__step_run_and_handle_result`, which
hits the `elif result is None:` branch at `tasks.py:355-357` and simply
`call_soon`s the next step. That is why `await asyncio.sleep(0)` is the idiom for
"yield to the loop exactly once": it costs one `Handle`, no Future, no timer.
**[impl detail]** — the documentation says only *"Setting the delay to 0 provides
an optimized path to allow other tasks to run"*, without specifying the mechanism.

### 4.7 `asyncio.timeout` on top of the same machinery

```python
            loop = events.get_running_loop()
            if when <= loop.time():
                self._timeout_handler = loop.call_soon(self._on_timeout)
            else:
                self._timeout_handler = loop.call_at(when, self._on_timeout)
```

— `Lib/asyncio/timeouts.py:67-71 — Timeout.reschedule()`

```python
    def _on_timeout(self) -> None:
        assert self._state is _State.ENTERED
        self._task.cancel()
        self._state = _State.EXPIRING
        # drop the reference early
        self._timeout_handler = None
```

— `Lib/asyncio/timeouts.py:127-132`

One `TimerHandle` whose callback cancels the task, plus a small state machine
(`CREATED` → `ENTERED` → `EXPIRING` → `EXPIRED`, `timeouts.py:18-23`) that
converts the resulting `CancelledError` back into a `TimeoutError` on the way out
— but *only* if the cancellation count says this timeout owns it:

```python
        if self._state is _State.EXPIRING:
            self._state = _State.EXPIRED

            if self._task.uncancel() <= self._cancelling and exc_type is not None:
                # Since there are no new cancel requests, we're
                # handling this.
                if issubclass(exc_type, exceptions.CancelledError):
                    raise TimeoutError from exc_val
```

— `Lib/asyncio/timeouts.py:109-116 — Timeout.__aexit__()`

`self._cancelling = self._task.cancelling()` is snapshotted on entry
(`timeouts.py:93`). The `cancelling()`/`uncancel()` pair added in 3.11 exists
precisely so that nested cancellation sources can tell whose cancellation they are
looking at — see [§6.2](#62-311-taskgroup-timeout-runner-and-the-cancellation-count).

---

## 5. Where the loop blocks; reentrancy and threads

### 5.1 The single blocking point

```python
        event_list = self._selector.select(timeout)
```

— `Lib/asyncio/base_events.py:2012`

That is the only call in `_run_once` that can block for a meaningful duration, and
`_run_once` is the only thing `run_forever` does. Everything else — pushing onto
heaps, popping deques, running callbacks — is bounded by the work already queued.

The corollary is the whole of asyncio's operational folklore, stated once in the
docs:

> Blocking (CPU-bound) code should not be called directly. For example, if a
> function performs a CPU-intensive calculation for 1 second, all concurrent
> asyncio Tasks and IO operations would be delayed by 1 second.

— [Running Blocking Code, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-dev.html#running-blocking-code),
quoted from `Doc/library/asyncio-dev.rst:122-125` **[guaranteed]**

A slow callback does not merely delay itself; it delays step 3 of the *next*
iteration, so no fd is even polled until it returns.

### 5.2 `call_soon` vs `call_soon_threadsafe`

Put them side by side. The bodies are near-identical:

```python
    def call_soon(self, callback, *args, context=None):
        """Arrange for a callback to be called as soon as possible.

        This operates as a FIFO queue: callbacks are called in the
        order in which they are registered.  Each callback will be
        called exactly once.

        Any positional arguments after the callback will be passed to
        the callback when it is called.
        """
        self._check_closed()
        if self._debug:
            self._check_thread()
            self._check_callback(callback, 'call_soon')
        handle = self._call_soon(callback, args, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        return handle
```

— `Lib/asyncio/base_events.py:823-840`

```python
    def call_soon_threadsafe(self, callback, *args, context=None):
        """Like call_soon(), but thread-safe."""
        self._check_closed()
        if self._debug:
            self._check_callback(callback, 'call_soon_threadsafe')
        handle = self._call_soon(callback, args, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        self._write_to_self()
        return handle
```

— `Lib/asyncio/base_events.py:876-885`

Both funnel into:

```python
    def _call_soon(self, callback, args, context):
        handle = events.Handle(callback, args, self, context)
        if handle._source_traceback:
            del handle._source_traceback[-1]
        self._ready.append(handle)
        return handle
```

— `Lib/asyncio/base_events.py:852-857`

**There are exactly two differences.** `call_soon` calls `_check_thread()` (and
only in debug mode); `call_soon_threadsafe` calls `_write_to_self()`
unconditionally. That is all.

### 5.3 `_check_thread`

```python
    def _check_thread(self):
        """Check that the current thread is the thread running the event loop.

        Non-thread-safe methods of this class make this assumption and will
        likely behave incorrectly when the assumption is violated.

        Should only be called when (self._debug == True).  The caller is
        responsible for checking this condition for performance reasons.
        """
        if self._thread_id is None:
            return
        thread_id = threading.get_ident()
        if thread_id != self._thread_id:
            raise RuntimeError(
                "Non-thread-safe operation invoked on an event loop other "
                "than the current one")
```

— `Lib/asyncio/base_events.py:859-874`

Three things to take from this:

1. **It only runs in debug mode.** `call_soon` guards the call with
   `if self._debug:` (line 834), as does `call_at` (line 813). In production mode
   there is no thread check at all. The documentation is explicit that this is a
   debug-mode feature:
   > When the debug mode is enabled:
   >
   > * Many non-threadsafe asyncio APIs (such as :meth:`loop.call_soon` and
   >   :meth:`loop.call_at` methods) raise an exception if they are called from a
   >   wrong thread.
   >
   > — [Debug Mode, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-dev.html#debug-mode),
   > quoted from `Doc/library/asyncio-dev.rst:47-51` **[guaranteed]**
2. **It returns silently when the loop is not running.** `self._thread_id is None`
   means `run_forever` has not been entered (or has exited). So calling `call_soon`
   from an arbitrary thread on a not-yet-running loop is never diagnosed, even in
   debug mode. This is what makes the common "build the loop here, hand it to a
   thread there" setup work.
3. **It is advisory, not protective.** The docstring says the non-thread-safe
   methods "will likely behave incorrectly" — but nothing enforces it in
   production.

### 5.4 What actually happens if you call `call_soon` from another thread

Read the code and the answer is uncomfortable: the `Handle` is constructed, and
`self._ready.append(handle)` runs. `deque.append` is atomic
(`Doc/library/collections.rst:458-461`, quoted in
[§1.8](#18-step-6--the-drain-and-why-ntodo-is-snapshotted)), so the queue is not
corrupted. The callback *will* run. It just will not run **until something else
wakes the selector.**

Measured on the install described above, with a loop parked in
`await asyncio.sleep(3.0)` and a worker thread scheduling a callback 0.2 s in:

```
call_soon_threadsafe:     callback ran 0.000s after scheduling
call_soon (other thread): callback ran 2.803s after scheduling
```

(Experiment written for this document. The second callback sat in `_ready`
untouched for 2.8 s, until the `sleep(3.0)` timer expired and step 3 returned of
its own accord.)

That is the failure mode: not a crash, not a lost callback — an unbounded latency
that depends entirely on what *else* the loop happens to have scheduled. If the
loop had been idle (`timeout = None`, `epoll_wait(-1)`), the callback would never
have run at all.

So the honest statement is: **[impl detail]** `call_soon` from another thread does
not corrupt the queue in CPython 3.13.11, because `_ready` is a `deque`; it is
nonetheless wrong, because the callback's latency is unbounded, and nothing about
the deque guarantee is part of the `call_soon` contract. **[guaranteed]** — *"Unlike
:meth:`call_soon_threadsafe`, this method is not thread-safe"*
(`Doc/library/asyncio-eventloop.rst:233`).

### 5.5 The self-pipe

```python
    def _make_self_pipe(self):
        # A self-socket, really. :-)
        self._ssock, self._csock = socket.socketpair()
        self._ssock.setblocking(False)
        self._csock.setblocking(False)
        self._internal_fds += 1
        self._add_reader(self._ssock.fileno(), self._read_from_self)
```

— `Lib/asyncio/selector_events.py:118-124 — BaseSelectorEventLoop._make_self_pipe()`

Called from `BaseSelectorEventLoop.__init__` (`selector_events.py:66`), so every
selector loop owns one from birth. Despite the name it is a `socket.socketpair()`,
not an `os.pipe()` — the comment says as much — because Windows' `select()` only
accepts sockets. `_ssock` (server side) is registered with the selector as a
reader; `_csock` (client side) is the end that gets written to.

The write side:

```python
    def _write_to_self(self):
        # This may be called from a different thread, possibly after
        # _close_self_pipe() has been called or even while it is
        # running.  Guard for self._csock being None or closed.  When
        # a socket is closed, send() raises OSError (with errno set to
        # EBADF, but let's not rely on the exact error code).
        csock = self._csock
        if csock is None:
            return

        try:
            csock.send(b'\0')
        except OSError:
            if self._debug:
                logger.debug("Fail to write a null byte into the "
                             "self-pipe socket",
                             exc_info=True)
```

— `Lib/asyncio/selector_events.py:141-157`

`csock = self._csock` is copied into a local *before* the `None` check — that
local read is the guard against another thread setting `self._csock = None` in
`_close_self_pipe` (`selector_events.py:110-116`) between the check and the
`send`. And the `except OSError` swallows the case where the socket was closed
after the local was taken. This function is written to be callable from any
thread, at any time, including during loop teardown.

The read side:

```python
    def _read_from_self(self):
        while True:
            try:
                data = self._ssock.recv(4096)
                if not data:
                    break
                self._process_self_data(data)
            except InterruptedError:
                continue
            except BlockingIOError:
                break
```

— `Lib/asyncio/selector_events.py:129-139`

It drains everything available and hands the bytes to `_process_self_data`, which
on the base class does nothing at all:

```python
    def _process_self_data(self, data):
        pass
```

— `Lib/asyncio/selector_events.py:126-127`

The bytes are irrelevant. The *wakeup* is the payload. `recv` returning is proof
that `select()` returned, which is proof that the loop is out of step 3 and on its
way to step 6, where it will drain whatever the other thread appended.

**The mechanism, end to end:**

```
  OTHER THREAD                          LOOP THREAD
  ────────────                          ───────────
  loop.call_soon_threadsafe(cb)
    │
    ├─ _call_soon(...)                  blocked in
    │    _ready.append(handle)  ──┐     epoll_wait(-1)
    │    (atomic deque append)    │            │
    │                             │            │
    └─ _write_to_self()           │            │
         _csock.send(b'\0')  ─────┼──► kernel marks _ssock readable
                                  │            │
                                  │     epoll_wait returns (_ssock, EPOLLIN)
                                  │            │
                                  │     _process_events -> _ready.append(
                                  │            Handle(_read_from_self))
                                  │            │
                                  │     drain: _read_from_self() reads b'\0',
                                  │            discards it
                                  │            │
                                  └──► next iteration: timeout=0 (if _ready
                                       non-empty) ... your cb runs
```

Note the one-iteration lag: the self-pipe wakeup arrives as an *event*, whose
handler goes into `_ready`. If your `call_soon_threadsafe` handle was appended
*before* the loop woke, both are in `_ready` and both run in the same drain. If it
raced in afterwards, it runs next iteration. Either way the loop is awake and
`ntodo` will be non-zero, so step 2 computes `timeout = 0` and it spins straight
through.

**The self-pipe is also the signal path.** On Unix, `add_signal_handler` points
CPython's signal-wakeup fd at the same `_csock`:

```python
        try:
            # set_wakeup_fd() raises ValueError if this is not the
            # main thread.  By calling it early we ensure that an
            # event loop running in another thread cannot add a signal
            # handler.
            signal.set_wakeup_fd(self._csock.fileno())
        except (ValueError, OSError) as exc:
            raise RuntimeError(str(exc))
```

— `Lib/asyncio/unix_events.py:102-109 — _UnixSelectorEventLoop.add_signal_handler()`

so the kernel writing a signal number into `_csock` both wakes the loop *and*
delivers the signal number. `_UnixSelectorEventLoop` overrides
`_process_self_data` to demultiplex the two uses of the same socket:

```python
    def _process_self_data(self, data):
        for signum in data:
            if not signum:
                # ignore null bytes written by _write_to_self()
                continue
            self._handle_signal(signum)
```

— `Lib/asyncio/unix_events.py:83-88`

`b'\0'` is chosen as the wakeup byte precisely because signal number 0 does not
exist. **[impl detail]**, and a neat one.

### 5.6 Why `call_soon` need not write, and `call_soon_threadsafe` must

`call_soon` is only ever legitimately called from the loop thread. The loop thread
can only be executing `call_soon` if it is *inside* step 6 — running a callback —
or outside `run_forever` entirely. In neither case is it blocked in `select()`. A
wakeup would be a wasted `send()` syscall on every single `call_soon`, which is the
hottest path in asyncio (every Task step goes through it).

`call_soon_threadsafe` has no such guarantee. By definition the caller is another
thread, and the loop thread may be parked in `epoll_wait(-1)` with no deadline. The
`send()` is mandatory. PEP 3156 specifies exactly this:

> ``call_soon_threadsafe(callback, *args)``. Like ``call_soon(callback, *args)``,
> but when called from another thread while the event loop is blocked waiting for
> I/O, unblocks the event loop. Returns a ``Handle``. This is the *only* method
> that is safe to call from another thread.

— [PEP 3156 § Thread interaction](https://peps.python.org/pep-3156/#thread-interaction)
**[guaranteed]**

`stop()` is the sharpest illustration of the asymmetry. It sets a flag
(`base_events.py:733`) and does *not* write to the self-pipe. A `loop.stop()` from
another thread therefore will not wake a parked loop, and the loop keeps sleeping
until something else does. CPython's own `Runner` knows this and works around it
explicitly in its `SIGINT` handler:

```python
    def _on_sigint(self, signum, frame, main_task):
        self._interrupt_count += 1
        if self._interrupt_count == 1 and not main_task.done():
            main_task.cancel()
            # wakeup loop if it is blocked by select() with long timeout
            self._loop.call_soon_threadsafe(lambda: None)
            return
        raise KeyboardInterrupt()
```

— `Lib/asyncio/runners.py:150-157 — Runner._on_sigint()`

`call_soon_threadsafe(lambda: None)` scheduling a no-op is not a callback at all;
it is a hand-written selector wakeup. **[impl detail]**

The signal path has its own wrapper for the same reason:

```python
    def _add_callback_signalsafe(self, handle):
        """Like _add_callback() but called from a signal handler."""
        self._add_callback(handle)
        self._write_to_self()
```

— `Lib/asyncio/base_events.py:1960-1963`

### 5.7 Reentrancy

`_run_once` is not reentrant, and several things enforce that:

- **`_check_running`** refuses a second `run_forever` on the same loop, and any
  `run_forever` while *another* loop is running in this thread:
  ```python
      def _check_running(self):
          if self.is_running():
              raise RuntimeError('This event loop is already running')
          if events._get_running_loop() is not None:
              raise RuntimeError(
                  'Cannot run the event loop while another loop is running')
  ```
  — `Lib/asyncio/base_events.py:635-640` **[guaranteed]** — the docs say
  `run_until_complete` / `run_forever` "cannot be called when the event loop is
  already running" (PEP 3156 § Starting, Stopping and Closing).
- **`_enter_task` / `_leave_task`** refuse a second task step inside a task step
  on the same loop (`tasks.py:1057-1070`, quoted in
  [§2.5](#25-waking-up)).
- **`Runner.run`** and **`asyncio.run`** fail fast:
  ```python
      if events._get_running_loop() is not None:
          # fail fast with short traceback
          raise RuntimeError(
              "asyncio.run() cannot be called from a running event loop")
  ```
  — `Lib/asyncio/runners.py:189-192`

There is no "nested loop" facility and none is planned; `nest_asyncio`-style
third-party patches work by monkeypatching around `_check_running`, not by any
supported hook.

`call_soon_threadsafe`, unusually, *is* documented as reentrancy-safe:

> This function is safe to be called from a reentrant context or signal handler,
> however, it is not safe or fruitful to use the returned handle in such contexts.

— [`loop.call_soon_threadsafe`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe),
quoted from `Doc/library/asyncio-eventloop.rst:241-242` **[guaranteed]**

That claim directly contradicts PEP 3156 — see
[§7.1](#71-pep-3156-says-call_soon_threadsafe-is-not-signal-safe-the-313-docs-say-it-is).

### 5.8 What is and is not safe from another thread

| Operation | Status | Evidence |
| --- | --- | --- |
| `loop.call_soon_threadsafe(cb)` | **Safe. [guaranteed]** | [PEP 3156 § Thread interaction](https://peps.python.org/pep-3156/#thread-interaction); `Doc/library/asyncio-eventloop.rst:235-249` |
| `asyncio.run_coroutine_threadsafe(coro, loop)` | **Safe. [guaranteed]** | `Doc/library/asyncio-dev.rst:85-87`; implemented as `loop.call_soon_threadsafe(callback)` at `Lib/asyncio/tasks.py:1003` |
| `loop.call_soon` / `call_later` / `call_at` | **Not safe. [guaranteed]** that it isn't; **[impl detail]** that it appears to work with unbounded latency | `Doc/library/asyncio-eventloop.rst:233`; measured in [§5.4](#54-what-actually-happens-if-you-call-call_soon-from-another-thread) |
| `fut.set_result` / `fut.cancel` / `task.cancel` | **Not safe.** Use `call_soon_threadsafe(fut.cancel)` | `Doc/library/asyncio-dev.rst:77-83`: *"Almost all asyncio objects are not thread safe [...] the :meth:`loop.call_soon_threadsafe` method should be used, e.g.: `loop.call_soon_threadsafe(fut.cancel)`"*; `Future` docstring `Lib/asyncio/futures.py:35`: *"This class is not thread-safe."* |
| `loop.stop()` | **Undocumented, and does not wake the loop.** [impl detail] | `Lib/asyncio/base_events.py:727-733` sets a flag and nothing else; `Lib/asyncio/runners.py:155` works around it |
| `loop.close()` | **Not safe**, and refuses while running | `Lib/asyncio/base_events.py:743-744` |
| `loop._write_to_self()` | Safe by construction, but private | `Lib/asyncio/selector_events.py:141-149` — written to tolerate concurrent teardown |
| `asyncio.all_tasks(loop)` | **Races**, and retries | `Lib/asyncio/tasks.py:56-66` — see below |
| `loop.add_signal_handler` | Main thread only, enforced | `Lib/asyncio/unix_events.py:103-109`; *"To handle signals the event loop must be run in the main thread"* (`Doc/library/asyncio-dev.rst`) |

`all_tasks` deserves its own look, because it is the one place in `asyncio` where
a cross-thread race is handled by *retrying*:

```python
def all_tasks(loop=None):
    """Return a set of all tasks for the loop."""
    if loop is None:
        loop = events.get_running_loop()
    # capturing the set of eager tasks first, so if an eager task "graduates"
    # to a regular task in another thread, we don't risk missing it.
    eager_tasks = list(_eager_tasks)
    # Looping over the WeakSet isn't safe as it can be updated from another
    # thread, therefore we cast it to list prior to filtering. The list cast
    # itself requires iteration, so we repeat it several times ignoring
    # RuntimeErrors (which are not very likely to occur).
    # See issues 34970 and 36607 for details.
    scheduled_tasks = None
    i = 0
    while True:
        try:
            scheduled_tasks = list(_scheduled_tasks)
        except RuntimeError:
            i += 1
            if i >= 1000:
                raise
        else:
            break
    return {t for t in itertools.chain(scheduled_tasks, eager_tasks)
            if futures._get_loop(t) is loop and not t.done()}
```

— `Lib/asyncio/tasks.py:44-68`

Note what this reveals: **there is no per-loop task registry.** `_scheduled_tasks`
is one module-level `WeakSet` shared by every loop in the process
(`Lib/asyncio/tasks.py:1036-1044`), and `all_tasks(loop)` filters it by
`futures._get_loop(t) is loop`. In the C build it is the same object, created once
in the module's per-interpreter state:

```c
    PyObject *weak_set;
    WITH_MOD("weakref")
    GET_MOD_ATTR(weak_set, "WeakSet");
    state->scheduled_tasks = PyObject_CallNoArgs(weak_set);
```

— `Modules/_asynciomodule.c:3662-3665 — module_init()`

and registration is a plain method call on that Python object:

```c
static int
register_task(asyncio_state *state, PyObject *task)
{
    PyObject *res = PyObject_CallMethodOneArg(state->scheduled_tasks,
                                                 &_Py_ID(add), task);
```

— `Modules/_asynciomodule.c:1897-1901`

`Py_MOD_PER_INTERPRETER_GIL_SUPPORTED` (`_asynciomodule.c:3756`) makes the state
per-interpreter, so the registry is **per-interpreter**, not per-loop and not
per-thread. Running twenty loops in twenty threads puts all their tasks in one
`WeakSet`, and `all_tasks` linearises it every call.

### 5.9 The `_current_tasks` dict is the one thing locked

`_current_tasks` maps loop → currently-running task. In C it is a real dict and
the swap is the only place in `_asynciomodule.c` that takes a critical section:

```c
    PyDictObject *current_tasks = (PyDictObject *)state->current_tasks;
    Py_BEGIN_CRITICAL_SECTION(current_tasks);
    prev_task = swap_current_task_lock_held(current_tasks, loop, hash, task);
    Py_END_CRITICAL_SECTION();
    return prev_task;
```

— `Modules/_asynciomodule.c:2024-2028 — swap_current_task()`

`Py_BEGIN_CRITICAL_SECTION` is PEP 703's deadlock-avoiding per-object lock
mechanism:

> This PEP proposes a scheme called "Python critical sections" to implicitly
> release per-object locks to avoid deadlocks.

— [PEP 703 § Python Critical Sections](https://peps.python.org/pep-0703/#python-critical-sections)

It is needed here because the swap is a *compound* read-then-write that must be
atomic as a unit — `enter_task` can get away with a single
`PyDict_SetDefaultRef` (`_asynciomodule.c:1937`) and `leave_task` with a single
`_PyDict_DelItemIf` (`1977`), but `swap_current_task` cannot. See
[§6.5](#65-313-free-threading-and-what-it-means-for-the-loop).

---

## 6. What changed, 3.11 → 3.13

The headline is that **`_run_once` barely moved and `BaseEventLoop` is still pure
Python**. Everything interesting happened one layer up, in `Task`, in the
structured-concurrency primitives, and in the C accelerator.

To date things precisely rather than from memory, `Modules/_asynciomodule.c` and
`Lib/asyncio/base_events.py` were fetched at tags `v3.11.0`, `v3.12.0`, `v3.13.0`
and `v3.13.11` and compared directly. Results are in
[§6.6](#66-a-dated-symbol-table-for-_asynciomodulec) and
[§6.7](#67-what-changed-inside-_run_once-itself).

### 6.1 Version scoreboard

| Change | Version | Evidence |
| --- | --- | --- |
| `TaskGroup` | 3.11 | `Doc/whatsnew/3.11.rst:578-583` |
| `asyncio.timeout` / `timeout_at` | 3.11 | `Doc/whatsnew/3.11.rst:585-588` |
| `asyncio.Runner` | 3.11 | `Doc/whatsnew/3.11.rst:590-592` |
| `Task.cancelling()` / `Task.uncancel()` | 3.11 | `Doc/whatsnew/3.11.rst:614-617` |
| `Barrier`, `all_errors=` on `create_connection`, `StreamWriter.start_tls`, raw datagram socket methods | 3.11 | `Doc/whatsnew/3.11.rst:594-612` |
| `eager_task_factory` / `create_eager_task_factory` / `Task(eager_start=)` | 3.12 | `Doc/whatsnew/3.12.rst:650-653` |
| `loop_factory=` on `asyncio.run` | 3.12 | `Doc/whatsnew/3.12.rst:666-668` |
| C implementation of `current_task` | 3.12 | `Doc/whatsnew/3.12.rst:670-671` |
| `sendmsg()` writes, no unnecessary copying | 3.12 | `Doc/whatsnew/3.12.rst:645-648` |
| `asyncio.EventLoop` alias | 3.13 | `Doc/library/asyncio-eventloop.rst:1878-1885` (**not** in What's New) |
| `as_completed` returns an async + plain iterator | 3.13 | `Doc/whatsnew/3.13.rst:684-690` |
| `Queue.shutdown` / `QueueShutDown` | 3.13 | `Doc/whatsnew/3.13.rst:702-704` |
| `Server.close_clients` / `abort_clients` | 3.13 | `Doc/whatsnew/3.13.rst:706-708` |
| TaskGroup nested-cancellation fixes; `uncancel()` may reset `_must_cancel` | 3.13 | `Doc/whatsnew/3.13.rst:714-734` |
| `TaskGroup.create_task` closes the coroutine when the group is inactive | 3.13 | `Doc/whatsnew/3.13.rst:736-740` |
| `loop.create_task(**kwargs)` | 3.13.3 (accidental), retained 3.13.4+ | `Doc/whatsnew/3.13.rst:742-757`; see [§7.5](#75-whats-new-in-313-says-three-create_task-entry-points-gained-kwargs-only-one-did) |
| Free-threaded build (experimental) | 3.13 | `Doc/whatsnew/3.13.rst:311-365`, [PEP 703](https://peps.python.org/pep-0703/) |
| `_run_forever_setup` / `_run_forever_cleanup` split out of `run_forever` | 3.13 | absent at `v3.12.0`, present at `v3.13.0` |
| `asyncio.free_running_loop` | **does not exist** | see [§9](#9-what-could-not-be-verified) |

### 6.2 3.11: `TaskGroup`, `timeout()`, `Runner`, and the cancellation count

These four landed together and are one design, not four features. The problem they
solve is that `CancelledError` carries no identity: if a task is cancelled while
already being cancelled by someone else, whoever catches it cannot tell whose
cancellation it is. `cancelling()` / `uncancel()` add that identity as a counter.

```python
    def cancelling(self):
        """Return the count of the task's cancellation requests.

        This count is incremented when .cancel() is called
        and may be decremented using .uncancel().
        """
        return self._num_cancels_requested

    def uncancel(self):
        """Decrement the task's count of cancellation requests.

        This should be called by the party that called `cancel()` on the task
        beforehand.

        Returns the remaining number of cancellation requests.
        """
        if self._num_cancels_requested > 0:
            self._num_cancels_requested -= 1
            if self._num_cancels_requested == 0:
                self._must_cancel = False
        return self._num_cancels_requested
```

— `Lib/asyncio/tasks.py:240-260`

The `if self._num_cancels_requested == 0: self._must_cancel = False` clause is
the 3.13 addition, described in What's New as:

> In order to handle some corner cases, :meth:`~asyncio.Task.uncancel` may now
> reset the undocumented ``_must_cancel`` flag when the cancellation count reaches
> zero.

— [What's New in Python 3.13 § asyncio](https://docs.python.org/3.13/whatsnew/3.13.html#asyncio),
quoted from `Doc/whatsnew/3.13.rst:730-732`

Note the phrase "the undocumented `_must_cancel` flag" — the release notes are
explicitly describing an **[impl detail]** because there was no way to describe the
fix otherwise.

`asyncio.timeout` uses the counter as shown in [§4.7](#47-asynciotimeout-on-top-of-the-same-machinery)
(`timeouts.py:93` snapshots, `timeouts.py:112` compares). `TaskGroup` uses it to
keep the count stable across its own internal cancel/uncancel dance:

```python
        if self._parent_cancel_requested:
            # If this flag is set we *must* call uncancel().
            if self._parent_task.uncancel() == 0:
                # If there are no pending cancellations left,
                # don't propagate CancelledError.
                propagate_cancellation_error = None
```

— `Lib/asyncio/taskgroups.py:144-149 — TaskGroup._aexit()`

`Runner` is the third piece: it hoists the loop lifecycle out of `asyncio.run` so
it can be reused, and it owns the `contextvars.Context` across multiple `run()`
calls:

```python
    def _lazy_init(self):
        if self._state is _State.CLOSED:
            raise RuntimeError("Runner is closed")
        if self._state is _State.INITIALIZED:
            return
        if self._loop_factory is None:
            self._loop = events.new_event_loop()
            if not self._set_event_loop:
                # Call set_event_loop only once to avoid calling
                # attach_loop multiple times on child watchers
                events.set_event_loop(self._loop)
                self._set_event_loop = True
        else:
            self._loop = self._loop_factory()
        if self._debug is not None:
            self._loop.set_debug(self._debug)
        self._context = contextvars.copy_context()
        self._state = _State.INITIALIZED
```

— `Lib/asyncio/runners.py:131-148`

and `asyncio.run` becomes a three-line wrapper around it:

```python
    if events._get_running_loop() is not None:
        # fail fast with short traceback
        raise RuntimeError(
            "asyncio.run() cannot be called from a running event loop")

    with Runner(debug=debug, loop_factory=loop_factory) as runner:
        return runner.run(main)
```

— `Lib/asyncio/runners.py:189-195`

Note the asymmetry in `_lazy_init`: when `loop_factory` is supplied, `Runner` does
**not** call `set_event_loop`. The documentation states this as a contract on the
caller — *"It is the responsibility of the *loop_factory* to set the created loop
as the current one"* (`Doc/library/asyncio-runner.rst`, `Runner` class) — and the
source matches it exactly.

Teardown is in `Runner.close`, and this is where `asyncio.run`'s shutdown
semantics actually live:

```python
        try:
            loop = self._loop
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(
                loop.shutdown_default_executor(constants.THREAD_JOIN_TIMEOUT))
        finally:
            if self._set_event_loop:
                events.set_event_loop(None)
            loop.close()
```

— `Lib/asyncio/runners.py:68-77`

`THREAD_JOIN_TIMEOUT = 300` (`Lib/asyncio/constants.py:33-34`) is the "5 minutes"
the `asyncio.run` docstring promises (`runners.py:177-179`) and the `timeout`
parameter added to `shutdown_default_executor` in 3.12
(`Doc/library/asyncio-eventloop.rst:212-213`).

### 6.3 3.12: the eager task factory

This is the largest behavioural change in the window. Normally, creating a Task
schedules its first step:

```python
        if eager_start and self._loop.is_running():
            self.__eager_start()
        else:
            self._loop.call_soon(self.__step, context=self._context)
            _register_task(self)
```

— `Lib/asyncio/tasks.py:124-128 — Task.__init__()`

With `eager_start=True` and a running loop, the first step happens *inline*, in the
constructor:

```python
    def __eager_start(self):
        prev_task = _swap_current_task(self._loop, self)
        try:
            _register_eager_task(self)
            try:
                self._context.run(self.__step_run_and_handle_result, None)
            finally:
                _unregister_eager_task(self)
        finally:
            try:
                curtask = _swap_current_task(self._loop, prev_task)
                assert curtask is self
            finally:
                if self.done():
                    self._coro = None
                    self = None  # Needed to break cycles when an exception occurs.
                else:
                    _register_task(self)
```

— `Lib/asyncio/tasks.py:262-279`

Read the `finally` carefully: if the coroutine finished during that first step, the
task is *never* registered in `_scheduled_tasks` and never touches `_ready`. If it
blocked, it graduates — `_register_task(self)` — and from that point behaves like
any other task. The two registries exist for exactly this:

```python
# Collectively these two sets hold references to the complete set of active
# tasks. Eagerly executed tasks use a faster regular set as an optimization
# but may graduate to a WeakSet if the task blocks on IO.
_scheduled_tasks = weakref.WeakSet()
_eager_tasks = set()
```

— `Lib/asyncio/tasks.py:1036-1040`

and it is why `all_tasks` snapshots `_eager_tasks` *first* (`tasks.py:48-50`):
reading the eager set before the scheduled set means a task graduating between the
two reads is seen twice, not zero times.

The factory itself is trivial:

```python
    def factory(loop, coro, *, name=None, context=None):
        return custom_task_constructor(
            coro, loop=loop, name=name, context=context, eager_start=True)

    return factory


eager_task_factory = create_eager_task_factory(Task)
```

— `Lib/asyncio/tasks.py:1026-1033`

The C path mirrors it, including entering the context explicitly rather than
going through `Context.run`:

```c
static int
task_eager_start(asyncio_state *state, TaskObj *task)
{
    assert(task != NULL);
    PyObject *prevtask = swap_current_task(state, task->task_loop, (PyObject *)task);
    ...
    if (PyContext_Enter(task->task_context) == -1) {
```

— `Modules/_asynciomodule.c:3120-3134`

with an optimisation note attached to the graduation check:

```c
    if (task->task_state == STATE_PENDING) {
        if (register_task(state, (PyObject *)task) == -1) {
            retval = -1;
        }
    } else {
        // This seems to really help performance on pyperformance benchmarks
        Py_CLEAR(task->task_coro);
    }
```

— `Modules/_asynciomodule.c:3167-3174`

Measured on the install described above (100 000 `await create_task(noop())`,
best of 3):

```
lazy  100k create_task(noop): 0.367s
eager 100k create_task(noop): 0.079s   -> 4.64x faster
```

(Benchmark written for this document.) That lands inside the range the release
notes claim:

> Add :func:`asyncio.eager_task_factory` and :func:`asyncio.create_eager_task_factory`
> functions to allow opting an event loop in to eager task execution, making some
> use-cases 2x to 5x faster.

— [What's New in Python 3.12 § asyncio](https://docs.python.org/3.12/whatsnew/3.12.html#asyncio),
quoted from `Doc/whatsnew/3.12.rst:650-653`

The documentation is unusually blunt that this is a semantic change, not just an
optimisation:

> Immediate execution of the coroutine is a semantic change. If the coroutine
> returns or raises, the task is never scheduled to the event loop. If the
> coroutine execution blocks, the task is scheduled to the event loop. This change
> may introduce behavior changes to existing applications. For example, the
> application's task execution order is likely to change.

— [Eager Task Factory, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-task.html#eager-task-factory),
quoted from `Doc/library/asyncio-task.rst:627-634` **[guaranteed]**

It is opt-in precisely because of that. Nothing in CPython sets it by default in
3.13.

### 6.4 3.12: the write path

> The performance of writing to sockets in :mod:`asyncio` has been significantly
> improved. ``asyncio`` now avoids unnecessary copying when writing to sockets and
> uses :meth:`~socket.socket.sendmsg` if the platform supports it.

— [What's New in Python 3.12 § asyncio](https://docs.python.org/3.12/whatsnew/3.12.html#asyncio),
quoted from `Doc/whatsnew/3.12.rst:645-648`

The mechanism, in 3.13.11, is a capability probe at import:

```python
_HAS_SENDMSG = hasattr(socket.socket, 'sendmsg')

if _HAS_SENDMSG:
    try:
        SC_IOV_MAX = os.sysconf('SC_IOV_MAX')
    except OSError:
        # Fallback to send
        _HAS_SENDMSG = False
```

— `Lib/asyncio/selector_events.py:33-40`

a method pointer chosen once per transport:

```python
        if _HAS_SENDMSG:
            self._write_ready = self._write_sendmsg
        else:
            self._write_ready = self._write_send
```

— `Lib/asyncio/selector_events.py:935-938`

and a scatter-gather write that passes the buffered chunks to the kernel without
concatenating them:

```python
    def _get_sendmsg_buffer(self):
        return itertools.islice(self._buffer, SC_IOV_MAX)

    def _write_sendmsg(self):
        assert self._buffer, 'Data should not be empty'
        if self._conn_lost:
            return
        try:
            nbytes = self._sock.sendmsg(self._get_sendmsg_buffer())
            self._adjust_leftover_buffer(nbytes)
```

— `Lib/asyncio/selector_events.py:1086-1095`

`_adjust_leftover_buffer` is the "no unnecessary copying" half — a partial write
re-slices only the one chunk that was split, as a `memoryview`:

```python
    def _adjust_leftover_buffer(self, nbytes: int) -> None:
        buffer = self._buffer
        while nbytes:
            b = buffer.popleft()
            b_len = len(b)
            if b_len <= nbytes:
                nbytes -= b_len
            else:
                buffer.appendleft(b[nbytes:])
                break
```

— `Lib/asyncio/selector_events.py:1117-1126`

and `writelines` feeds it directly, with one `memoryview` per item and no
`b''.join`:

```python
        self._buffer.extend([memoryview(data) for data in list_of_data])
        self._write_ready()
        # If the entire buffer couldn't be written, register a write handler
        if self._buffer:
            self._loop._add_writer(self._sock_fd, self._write_ready)
            self._maybe_pause_protocol()
```

— `Lib/asyncio/selector_events.py:1180-1185 — _SelectorSocketTransport.writelines()`

Note that `writelines` calls `self._write_ready()` **synchronously** before
falling back to registering a writer — the same "try it now" optimisation as
`write()` (`selector_events.py:1064-1067`). **[impl detail]** in both cases.

### 6.5 3.13: free-threading, and what it means for the loop

The free-threaded build is experimental in 3.13 and requires a separate
interpreter binary:

> CPython now has experimental support for running in a free-threaded mode, with
> the :term:`global interpreter lock` (GIL) disabled. This is an experimental
> feature and therefore is not enabled by default. The free-threaded mode requires
> a different executable, usually called ``python3.13t`` [...]
> **The free-threaded mode is experimental** and work is ongoing to improve it:
> expect some bugs and a substantial single-threaded performance hit.

— [What's New in Python 3.13 § Free-threaded CPython](https://docs.python.org/3.13/whatsnew/3.13.html#free-threaded-cpython),
quoted from `Doc/whatsnew/3.13.rst:316-331`

`_asyncio` declares itself ready for it:

```c
static struct PyModuleDef_Slot module_slots[] = {
    {Py_mod_exec, module_exec},
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
    {0, NULL},
};
```

— `Modules/_asynciomodule.c:3754-3759`

`Py_MOD_GIL_NOT_USED` is the opt-in described in What's New:

> Extensions that support running with the :term:`GIL` disabled should use the
> :c:data:`Py_mod_gil` slot. [...] Importing C extensions that don't use these
> mechanisms will cause the GIL to be enabled

— `Doc/whatsnew/3.13.rst:342-346`

So importing `asyncio` on a free-threaded build does **not** re-enable the GIL.
What that declaration costs, concretely, is visible in three places in the module:

1. **The `FutureIter` free-list is compiled out.** `#ifndef Py_GIL_DISABLED`
   guards both the struct field (`_asynciomodule.c:74-77`), the allocation
   (`1755-1764`) and the deallocation (`1534-1550`). A shared, unlocked free-list
   cannot be made safe cheaply, so under free-threading every `await` on a Future
   allocates a fresh iterator.
2. **The task-name counter becomes atomic.**
   ```c
   #ifdef Py_GIL_DISABLED
           unsigned long long counter = _Py_atomic_add_uint64(&state->task_name_counter, 1) + 1;
   #else
           unsigned long long counter = ++state->task_name_counter;
   #endif
   ```
   — `Modules/_asynciomodule.c:2089-2093`

   The pure-Python side has the same concern and solves it differently:
   ```python
   # Helper to generate new task names
   # This uses itertools.count() instead of a "+= 1" operation because the latter
   # is not thread safe. See bpo-11866 for a longer explanation.
   _task_name_counter = itertools.count(1).__next__
   ```
   — `Lib/asyncio/tasks.py:31-34`
3. **`swap_current_task` takes a critical section** (`_asynciomodule.c:2024-2028`,
   quoted in [§5.9](#59-the-_current_tasks-dict-is-the-one-thing-locked)).

**What is *not* protected.** The task registry is a `weakref.WeakSet`
(`_asynciomodule.c:3662-3665`) — a pure-Python object with a Python `add` /
`discard`. Under PEP 703 its internal `set` gets a per-object lock, so it will not
corrupt; but the *compound* operation `list(_scheduled_tasks)` in `all_tasks` is
still a loop over a mutating collection, which is exactly why `all_tasks` retries
up to 1000 times on `RuntimeError` (`Lib/asyncio/tasks.py:56-66`). PEP 703 is
explicit that per-object locking does not make compound operations atomic:

> Per-object locks with critical sections provide weaker protections than the GIL.
> Because the GIL doesn't necessarily ensure that concurrent operations are atomic
> or correct, the per-object locking scheme also cannot ensure that concurrent
> operations are atomic or correct. Instead, per-object locking aims for similar
> protections as the GIL, but with mutual exclusion limited to individual objects.

— [PEP 703 § Container Thread-Safety](https://peps.python.org/pep-0703/#container-thread-safety)

**And the event loop itself gains nothing.** `BaseEventLoop` is pure Python and
unchanged for free-threading. The `_ready` deque idiom in `_run_once`
([§1.8](#18-step-6--the-drain-and-why-ntodo-is-snapshotted)) relies on
`deque.append` / `deque.popleft` being individually atomic, which PEP 703 preserves
via the per-object lock — but the free-threading how-to is careful to label that
as description, not promise:

> Built-in types like :class:`dict`, :class:`list`, and :class:`set` use internal
> locks to protect against concurrent modifications in ways that behave similarly
> to the GIL. However, Python has not historically guaranteed specific behavior
> for concurrent modifications to these built-in types, so this should be treated
> as a description of the current implementation, not a guarantee of current or
> future behavior.

— [Python support for free threading, Python 3.13 docs](https://docs.python.org/3.13/howto/free-threading-python.html#thread-safety),
quoted from `Doc/howto/free-threading-python.rst:77-84`

Which is the **[impl detail]** / **[guaranteed]** distinction stated by CPython
itself, about the exact data structure `_run_once` depends on.

The practical position in 3.13 is therefore: you may run *N* event loops in *N*
threads on a free-threaded build and they will not contend on a GIL, but a single
loop is no more parallel than before — it is still one thread running one callback
at a time — and every cross-loop shared structure (`_scheduled_tasks`,
`_current_tasks`) is a genuine contention point. Nothing in the 3.13 documentation
promises asyncio is free-threading-safe; the only evidence is the `Py_mod_gil`
declaration in the C module.

### 6.6 A dated symbol table for `_asynciomodule.c`

Presence of each symbol in `Modules/_asynciomodule.c`, checked by fetching the
file at each tag and grepping. `Y` = present, `n` = absent.

| Symbol | 3.11.0 | 3.12.0 | 3.13.0 | 3.13.11 | What it is |
| --- | :-: | :-: | :-: | :-: | --- |
| `fi_freelist` | Y | Y | Y | Y | `FutureIter` free-list (pre-dates 3.11) |
| `task_name_counter` | Y | Y | Y | Y | task naming counter |
| `task_eager_start` | n | Y | Y | Y | eager task execution, 3.12 |
| `register_eager_task` | n | Y | Y | Y | the `_eager_tasks` registry, 3.12 |
| `task_step_handle_result_impl` | n | Y | Y | Y | `task_step_impl` split in two, 3.12 |
| `Py_MOD_PER_INTERPRETER_GIL_SUPPORTED` | n | Y | Y | Y | per-interpreter module state, 3.12 |
| `_asyncio_current_task` | n | Y | Y | Y | C `current_task()`, 3.12 |
| `Py_mod_gil` | n | n | Y | Y | free-threading opt-in, 3.13 |
| `Py_BEGIN_CRITICAL_SECTION` | n | n | Y | Y | per-object locking, 3.13 |
| `asyncio_running_loop` | n | n | Y | Y | running loop moved onto the thread state, 3.13 |

File sizes: 3505 lines at `v3.11.0`, 3815 at `v3.12.0`, 3749 at `v3.13.0`, 3777 at
`v3.13.11`.

Two entries deserve a note. **`task_step_handle_result_impl`** is the 3.12 split of
the monolithic `task_step_impl` into "advance the coroutine" and "interpret what it
yielded" — the second half is the `_asyncio_future_blocking` dispatch quoted in
[§2.4](#24-the-_asyncio_future_blocking-protocol), and the split exists so the
eager-start path can reuse it. **`asyncio_running_loop`** is the 3.13 move of the
running-loop pointer from a `threading.local` into a field on `_PyThreadStateImpl`
(`_asynciomodule.c:3241`, `3265-3269`), which is the free-threading-friendly
equivalent.

### 6.7 What changed inside `_run_once` itself

Diffing `BaseEventLoop._run_once` across the four tags gives two changes in three
releases:

**3.11 → 3.12: cycle-breaking on `event_list`.** These two lines are absent at
`v3.11.0` and present from `v3.12.0`:

```python
        self._process_events(event_list)
        # Needed to break cycles when an exception occurs.
        event_list = None
```

— `Lib/asyncio/base_events.py:2013-2015`

**3.12 → 3.13: the timeout computation was un-inlined.** At `v3.11.0` and
`v3.12.0` it reads:

```python
            when = self._scheduled[0]._when
            timeout = min(max(0, when - self.time()), MAXIMUM_SELECT_TIMEOUT)
```

At `v3.13.0` and `v3.13.11` it reads:

```python
            timeout = self._scheduled[0]._when - self.time()
            if timeout > MAXIMUM_SELECT_TIMEOUT:
                timeout = MAXIMUM_SELECT_TIMEOUT
            elif timeout < 0:
                timeout = 0
```

— `Lib/asyncio/base_events.py:2006-2010`

Semantically identical; it removes two builtin calls per iteration from the
hottest loop in the module. **`_run_once` is otherwise byte-identical between
`v3.13.0` and `v3.13.11`.**

The other loop-level 3.13 change is the extraction of `_run_forever_setup` and
`_run_forever_cleanup` (`base_events.py:642-676`), absent at `v3.12.0`, with a
docstring stating the motivation:

> This method exists so that custom event loop subclasses (e.g., event loops that
> integrate a GUI event loop with Python's event loop) have access to all the loop
> setup logic.

— `Lib/asyncio/base_events.py:645-647`

That is a small but real API-shaped concession: a GUI integration can now drive
iterations itself without reimplementing the hook and thread-id bookkeeping.

---

## 7. Where the documentation and the source disagree

Five, found by reading both. In each case the source is the authority for what
3.13.11 actually does.

### 7.1 PEP 3156 says `call_soon_threadsafe` is not signal-safe; the 3.13 docs say it is

PEP 3156:

> Note: this is not safe to call from a signal handler (since it may use locks).
> In fact, no API is signal-safe; if you want to handle signals, use
> ``add_signal_handler()`` described below.

— [PEP 3156 § Thread interaction](https://peps.python.org/pep-3156/#thread-interaction)

The 3.13 reference:

> This function is safe to be called from a reentrant context or signal handler,
> however, it is not safe or fruitful to use the returned handle in such contexts.

— [`loop.call_soon_threadsafe`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe),
quoted from `Doc/library/asyncio-eventloop.rst:241-242`

**The source supports the docs.** The whole path is
`_check_closed` → `events.Handle(...)` → `contextvars.copy_context()` →
`deque.append` → `socket.send(b'\0')` (`base_events.py:876-885`,
`base_events.py:852-857`, `selector_events.py:141-157`). There is no
`threading.Lock` anywhere in it. PEP 3156's parenthetical "(since it may use
locks)" describes an implementation that no longer exists, and the caveat about
the returned handle is the honest residue: `Handle.cancel()` mutates
`self._cancelled`, `self._callback` and `self._args` (`events.py:73-82`) with no
synchronisation, so cancelling from a signal handler a handle the loop is about to
run is genuinely racy.

**Verdict:** prefer the docs and the source. PEP 3156 is a 2012 design document
with `Status: Final`; it is normative about intent, not about the 3.13 code.

### 7.2 PEP 3156 says `stop()` stops short of polling for I/O; the 3.13 docs and the source say it polls once

PEP 3156:

> ``stop()``. Stops the event loop as soon as it is convenient. [...] How soon
> after this point the event loop stops is up to the implementation, but the
> intention is to stop short of polling for I/O, and not to run any callbacks
> scheduled in the future; the major freedom an implementation has is how much of
> the "ready queue" (callbacks already scheduled with ``call_soon()``) it processes
> before stopping.

— [PEP 3156 § Starting, Stopping and Closing](https://peps.python.org/pep-3156/#starting-stopping-and-closing)

The 3.13 reference:

> If :meth:`stop` is called before :meth:`run_forever` is called, the loop will
> poll the I/O selector once with a timeout of zero, run all callbacks scheduled
> in response to I/O events (and those that were already scheduled), and then exit.

— [`loop.run_forever`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-eventloop.html#asyncio.loop.run_forever),
quoted from `Doc/library/asyncio-eventloop.rst:129-132`

**The source says: it depends on when you call it.**

```python
        timeout = None
        if self._ready or self._stopping:
            timeout = 0
```

— `Lib/asyncio/base_events.py:2001-2003`

- `stop()` **before** `run_forever()`: `_stopping` is already `True` when the first
  `_run_once` computes its timeout, so it polls with `timeout = 0`, runs
  `_process_events`, runs the due timers, drains the ready queue, and exits. Exactly
  as the docs say, and *not* "short of polling for I/O".
- `stop()` **during** the drain: `select()` for this iteration already happened
  before the callback ran, and `run_forever` breaks immediately after `_run_once`
  returns (`base_events.py:684-685`). No further poll. As the PEP intends.

The PEP's "not to run any callbacks scheduled in the future" is also slightly
strong: if a timer is already due when `stop()` is called before `run_forever`,
step 5 moves it into `_ready` and step 6 runs it.

**Verdict:** the 3.13 docs are precisely right; the PEP describes intent for one of
the two cases.

### 7.3 The `call_later` "may run early" note is documented; the cancelled-timer accounting is not

Contrast two pieces of the same method. The clock-resolution fudge at
`base_events.py:2018` **is** documented, twice
(`Doc/library/asyncio-eventloop.rst:301-305` and `327-331`, quoted in
[§4.5](#45-the-clock-resolution-fudge)). The cancelled-timer compaction at
`base_events.py:1978-1999`, its two constants, and the `_timer_cancelled_count`
staleness described in [§1.4](#14-step-1--cancelled-timer-hygiene) are documented
nowhere.

This is not strictly a disagreement, but it is the sharpest illustration of where
the **[guaranteed]** / **[impl detail]** line actually sits: the observable timing
skew is promised, the entire data-structure hygiene mechanism behind it is not.

### 7.4 `isfuture` documents a weaker test than it performs

The docs:

> Return ``True`` if *obj* is either of:
>
> * an instance of :class:`asyncio.Future`,
> * an instance of :class:`asyncio.Task`,
> * a Future-like object with a ``_asyncio_future_blocking`` attribute.

— [`asyncio.isfuture`, Python 3.13 docs](https://docs.python.org/3.13/library/asyncio-future.html#asyncio.isfuture),
quoted from `Doc/library/asyncio-future.rst:22-29`

The source:

```python
    return (hasattr(obj.__class__, '_asyncio_future_blocking') and
            obj._asyncio_future_blocking is not None)
```

— `Lib/asyncio/base_futures.py:20-21`

Two conditions the documentation omits. The attribute must be on the **class**
(an instance-only attribute does not count), and its value must **not be `None`**.
The `not None` clause is not an accident — it is the documented-in-source opt-out:

> The value must also be not-None, to enable a subclass to declare that it is not
> compatible by setting this to None.

— `Lib/asyncio/futures.py:62-64`

and CPython's test suite asserts it:

```python
    def test_isfuture(self):
        class MyFuture:
            _asyncio_future_blocking = None

            def __init__(self):
                self._asyncio_future_blocking = False

        self.assertFalse(asyncio.isfuture(MyFuture))
        self.assertTrue(asyncio.isfuture(MyFuture()))
```

— `Lib/test/test_asyncio/test_futures.py:138-146`

So a class can set `_asyncio_future_blocking = None` at class level to *opt out* of
being treated as a Future, while its instances set `False` to opt back in.
Following the documentation literally would get both of those backwards.

**Verdict:** prefer the source. The documented rule is a simplification that is
wrong at the edges, and the edges are the reason the attribute is three-valued.

### 7.5 "What's New in 3.13" says three `create_task` entry points gained `**kwargs`; only one did

What's New:

> The function and methods named ``create_task`` have received a new ``**kwargs``
> argument that is passed through to the task constructor. [...] To keep the
> workarounds working, the extra ``**kwargs`` argument still allows passing
> additional keyword arguments to :class:`~asyncio.Task` and to custom task
> factories.
>
> This affects the following function and methods:
> :meth:`asyncio.create_task`, :meth:`asyncio.loop.create_task`,
> :meth:`asyncio.TaskGroup.create_task`.

— [What's New in Python 3.13 § asyncio](https://docs.python.org/3.13/whatsnew/3.13.html#asyncio),
quoted from `Doc/whatsnew/3.13.rst:742-757`

The source at 3.13.11:

```python
    def create_task(self, coro, *, name=None, context=None, **kwargs):
```
— `Lib/asyncio/base_events.py:461 — BaseEventLoop.create_task()` — **has it**

```python
def create_task(coro, *, name=None, context=None):
```
— `Lib/asyncio/tasks.py:402 — asyncio.create_task()` — **does not**

```python
    def create_task(self, coro, *, name=None, context=None):
```
— `Lib/asyncio/taskgroups.py:181 — TaskGroup.create_task()` — **does not**

The two reference pages agree with the source, not with What's New:
`Doc/library/asyncio-task.rst:241` documents
`create_task(coro, *, name=None, context=None)`,
`Doc/library/asyncio-task.rst:333` documents
`TaskGroup.create_task(coro, *, name=None, context=None)`, and only
`Doc/library/asyncio-eventloop.rst:370` shows the `**kwargs`.

For completeness, the change is genuinely a 3.13 patch-release event, not a 3.13.0
one: at tag `v3.13.0`, `BaseEventLoop.create_task` is
`def create_task(self, coro, *, name=None, context=None):`
(`Lib/asyncio/base_events.py:462` at that tag), with no `**kwargs`.

**Verdict:** prefer the source and the reference pages. The What's New entry
describes the 3.13.3 state of all three signatures; two of them were reverted in
3.13.4 and the entry was not fully updated.

---

## 8. Sources

Fetched and read on **12 September 2026**. Split by weight: CPython source at a
tagged release is the authority for what the implementation does; a PEP is the
authority for what was intended and promised; `docs.python.org` is the authority
for what users are entitled to rely on. Where they conflict, [§7](#7-where-the-documentation-and-the-source-disagree)
says which wins and why.

### CPython source, tag `v3.13.11`

| Source | Details | Used for |
| --- | --- | --- |
| [`Lib/asyncio/base_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/base_events.py) | 2075 lines. Verified byte-identical to the local install at `/home/qas/miniconda3/lib/python3.13/asyncio/base_events.py`. | `_run_once` (1970-2051), `run_forever` (678-687), `stop` (727-733), `call_soon`/`call_at`/`call_later` (781-885), `_check_thread` (859-874), the timer constants (56-68), `_run_forever_setup` (642-660), `create_task` (461-484). |
| [`Lib/asyncio/events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/events.py) | 882 lines. Verified identical. | `Handle` (29-105), `TimerHandle` (108-168), `_RunningLoop` / `_get_running_loop` (747-786), the `_asyncio` import (858-871), `on_fork` (874-882), `BaseDefaultEventLoopPolicy.get_event_loop` (688-719). |
| [`Lib/asyncio/futures.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/futures.py) | 425 lines. Verified identical. | The `_asyncio_future_blocking` comment (59-68), `__schedule_callbacks` (158-170), `add_done_callback` (217-229), `set_result` (248-258), `__await__` (283-291), the `_asyncio` import (419-425). |
| [`Lib/asyncio/base_futures.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/base_futures.py) | 67 lines. | `isfuture` (13-21) and the three state constants (7-10). |
| [`Lib/asyncio/tasks.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/tasks.py) | 1118 lines. Verified identical. | The Task state invariant (76-93), `__init__` (99-128), `cancel`/`cancelling`/`uncancel` (198-260), `__eager_start` (262-279), `__step` (281-296), `__step_run_and_handle_result` (298-371), `__wakeup` (373-387), `sleep`/`__sleep0` (691-721), `create_eager_task_factory` (1007-1033), the registries (1036-1089), the `_asyncio` imports (393-399, 1102-1118), `all_tasks` (44-68). |
| [`Lib/asyncio/selector_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/selector_events.py) | 1322 lines. Verified identical. | `__init__` (59-67), the self-pipe (110-157), `_add_reader`/`_remove_reader` (274-306), `add_reader` (344-347), `sock_recv`/`_sock_recv` (364-404), `_process_events` (740-752), `_SelectorTransport.__init__` (769-795), `_SelectorSocketTransport` read and write paths (923-1185). |
| [`Lib/asyncio/runners.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/runners.py) | 216 lines. Verified identical. | `Runner.close` (64-79), `Runner.run` (86-129), `_lazy_init` (131-148), `_on_sigint` (150-157), `run` (160-195), `_cancel_all_tasks` (198-216). |
| [`Lib/asyncio/timeouts.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/timeouts.py) | 184 lines. Verified identical. | `Timeout` state machine (18-23), `reschedule` (50-71), `__aenter__`/`__aexit__` (85-125), `_on_timeout` (127-132), `timeout_at` docstring (165-184). |
| [`Lib/asyncio/taskgroups.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/taskgroups.py) | 278 lines. Verified identical. | `_aexit` (82-178), `create_task` (181-211), `_abort` (221-226), `_on_task_done` (228-278). |
| [`Lib/asyncio/unix_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/unix_events.py) | 1536 lines. Verified identical. | `_process_self_data` (83-88), `add_signal_handler` (90-133), `_handle_signal` (135-143). |
| [`Lib/asyncio/constants.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/constants.py) | 41 lines. Verified identical. | `THREAD_JOIN_TIMEOUT = 300` (33-34), `DEBUG_STACK_DEPTH` (13-16). |
| [`Lib/selectors.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/selectors.py) | 603 lines. Verified identical. | `BaseSelector.select` contract (158-175), `EpollSelector.select` (435-463), `DefaultSelector` resolution (595-603). |
| [`Modules/_asynciomodule.c`](https://github.com/python/cpython/blob/v3.13.11/Modules/_asynciomodule.c) | 3777 lines. Fetched from the tag; not shipped with a binary install. | The struct layout (107-151), `call_soon` (288-320), `future_schedule_callbacks` (352-407), `future_add_done_callback` (619-692), `FutureIter_am_send` (1557-1593), `future_new_iter` and the free-list (1747-1775), the task registry helpers (1897-2029), `Task.__init__` (2047-2124), `task_step_impl` (2736-2862), `task_step_handle_result_impl` (2866-3090), `task_step` (3092-3118), `task_eager_start` (3120-3177), `task_wakeup` (3179-3221), the running-loop accessors (3237-3316), `module_init`/`module_exec`/`module_slots` (3603-3759). |
| [`Lib/test/test_asyncio/test_base_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/test/test_asyncio/test_base_events.py) | 2295 lines. | `test__run_once` (381-397), `test__run_once_schedule_handle` (405-422), `test__run_once_cancelled_event_cleanup` (424-498) — the tests that pin the drain semantics and the compaction constants. |
| [`Lib/test/test_asyncio/test_tasks.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/test/test_asyncio/test_tasks.py) | 3601 lines. | The C/Python parity matrix: `add_subclass_tests` (2710-2765), `CTask_CFuture_Tests` (2821-2849), `CTaskSubclass_PyFuture_Tests` (2862-2868), `PyTask_CFutureSubclass_Tests` (2871-2877), `CTask_PyFuture_Tests` (2880-2885), `PyTask_CFuture_Tests` (2888-2893), `PyTask_PyFuture_Tests` (2896-2900). |
| [`Lib/test/test_asyncio/test_futures.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/test/test_asyncio/test_futures.py) | 1148 lines. | `test_isfuture` (138-159), the C/Python future test classes (704-759), `BaseFutureInheritanceTests` (1106-1144). |

Earlier tags, fetched only to date changes ([§6.6](#66-a-dated-symbol-table-for-_asynciomodulec),
[§6.7](#67-what-changed-inside-_run_once-itself)):
[`Modules/_asynciomodule.c` at `v3.11.0`](https://github.com/python/cpython/blob/v3.11.0/Modules/_asynciomodule.c) (3505 lines),
[`v3.12.0`](https://github.com/python/cpython/blob/v3.12.0/Modules/_asynciomodule.c) (3815),
[`v3.13.0`](https://github.com/python/cpython/blob/v3.13.0/Modules/_asynciomodule.c) (3749);
`Lib/asyncio/base_events.py` at the same three tags;
`Lib/asyncio/tasks.py` and `Lib/asyncio/taskgroups.py` at `v3.13.0`.

### PEPs

| Source | Details | Used for |
| --- | --- | --- |
| [PEP 3156 — Asynchronous IO Support Rebooted: the "asyncio" Module](https://peps.python.org/pep-3156/) | Guido van Rossum, BDFL-Delegate Antoine Pitrou. Created 12 Dec 2012, Status **Final**, Python-Version 3.3. Read from the [RST source](https://raw.githubusercontent.com/python/peps/main/peps/pep-3156.rst). | [§ Basic Callbacks](https://peps.python.org/pep-3156/#basic-callbacks) — strict serialisation of callbacks, `call_soon` FIFO order, the `call_later`/`call_at` equivalence, the undefined order of same-deadline timers, `time()`'s permitted clocks. [§ Thread interaction](https://peps.python.org/pep-3156/#thread-interaction) — `call_soon_threadsafe` as the only thread-safe method, and the (now outdated) signal-safety caveat. [§ Starting, Stopping and Closing](https://peps.python.org/pep-3156/#starting-stopping-and-closing) — `stop()` semantics. [§ Handles](https://peps.python.org/pep-3156/#handles) — `add_reader` returns nothing. [§ Futures](https://peps.python.org/pep-3156/#futures) — callbacks are never called inline. [§ The Scheduler](https://peps.python.org/pep-3156/#the-scheduler) — the scheduler uses only the public loop API, the constraint that produced `_asyncio_future_blocking`. [§ Coroutines and the Scheduler](https://peps.python.org/pep-3156/#coroutines-and-the-scheduler) — coroutines are optional over a callback core. |
| [PEP 492 — Coroutines with async and await syntax](https://peps.python.org/pep-0492/) | Yury Selivanov, Status Final, Python-Version 3.5. Read from the [RST source](https://raw.githubusercontent.com/python/peps/main/peps/pep-0492.rst). | [§ Await Expression](https://peps.python.org/pep-0492/#await-expression) — every `await` chain bottoms out in a `yield`; `__await__` must return an iterator; the prescribed `__await__ = __iter__` on `asyncio.Future` (CPython does the reverse). |
| [PEP 567 — Context Variables](https://peps.python.org/pep-0567/) | Yury Selivanov, Status Final, Python-Version 3.7. Read from the [RST source](https://raw.githubusercontent.com/python/peps/main/peps/pep-0567.rst). | [§ asyncio](https://peps.python.org/pep-0567/#asyncio) — the sketch of `call_soon` copying the context and `Task` maintaining its own; [§ Backwards Compatibility](https://peps.python.org/pep-0567/#backwards-compatibility) — the normative statement that `call_at`/`call_later`/`call_soon`/`add_done_callback` run callbacks in the calling context. |
| [PEP 703 — Making the Global Interpreter Lock Optional in CPython](https://peps.python.org/pep-0703/) | Sam Gross. Read from the [RST source](https://raw.githubusercontent.com/python/peps/main/peps/pep-0703.rst). | [§ Container Thread-Safety](https://peps.python.org/pep-0703/#container-thread-safety) — per-object locks give GIL-like, not atomic, protection; which operations lock. [§ Python Critical Sections](https://peps.python.org/pep-0703/#python-critical-sections) — the `Py_BEGIN_CRITICAL_SECTION` mechanism `swap_current_task` uses. |

PEP 525 and PEP 530 (asynchronous generators, `async` comprehensions) were
considered and are not cited: the async-generator hooks in `_run_forever_setup`
(`base_events.py:653-658`) and `shutdown_asyncgens` touch them, but nothing in the
six questions turns on generator semantics, and citing them would have meant
quoting sections that do not bear on the loop.

### Python 3.13 documentation

All quoted from the reST sources at tag `v3.13.11` so that quotations are exact and
line-citable; each links to the rendered 3.13 page.

| Source | Used for |
| --- | --- |
| [Event Loop](https://docs.python.org/3.13/library/asyncio-eventloop.html) (`Doc/library/asyncio-eventloop.rst`, 2060 lines) | `run_forever` and `stop` (115-163), `call_soon` (218-233), `call_soon_threadsafe` (235-253), `call_later`/`call_at` and the clock-resolution note (281-340), `loop.time` (342-350), `loop.create_task` signature (370), `add_reader`/`add_writer` (1004-1030), `sock_recv` (1049-1063), `asyncio.EventLoop` (1878-1885). |
| [Coroutines and Tasks](https://docs.python.org/3.13/library/asyncio-task.html) (`Doc/library/asyncio-task.rst`, 1472 lines) | `create_task` signature (241), `TaskGroup.create_task` signature (333), `sleep(0)` (478), Eager Task Factory (609-651), `Task(..., eager_start=)` (1143-1204). |
| [Futures](https://docs.python.org/3.13/library/asyncio-future.html) (`Doc/library/asyncio-future.rst`, 280 lines) | `isfuture` (22-31) — the one place `_asyncio_future_blocking` appears in the documentation at all. |
| [Developing with asyncio](https://docs.python.org/3.13/library/asyncio-dev.html) (`Doc/library/asyncio-dev.rst`, 248 lines) | Debug Mode (18-58), Concurrency and Multithreading (63-117), Running Blocking Code (119-130). |
| [Runners](https://docs.python.org/3.13/library/asyncio-runner.html) (`Doc/library/asyncio-runner.rst`, 162 lines) | `asyncio.run` with `loop_factory` and the 3.12 versionchanged; `Runner` and the loop-factory responsibility clause. |
| [`collections.deque`](https://docs.python.org/3.13/library/collections.html#collections.deque) (`Doc/library/collections.rst:458-461`) | The thread-safe append/pop guarantee the `_ready` idiom rests on. |
| [Python support for free threading](https://docs.python.org/3.13/howto/free-threading-python.html) (`Doc/howto/free-threading-python.rst`, 154 lines) | § Thread safety (74-90) — built-in container locking described as implementation, not guarantee. |
| [What's New in Python 3.11](https://docs.python.org/3.11/whatsnew/3.11.html#asyncio) (`Doc/whatsnew/3.11.rst:575-617`) | `TaskGroup`, `timeout()`, `Runner`, `Barrier`, `cancelling()`/`uncancel()`. |
| [What's New in Python 3.12](https://docs.python.org/3.12/whatsnew/3.12.html#asyncio) (`Doc/whatsnew/3.12.rst:642-679`) | `sendmsg` writes, eager task factory ("2x to 5x faster"), `loop_factory`, C `current_task`, child-watcher changes. |
| [What's New in Python 3.13](https://docs.python.org/3.13/whatsnew/3.13.html) (`Doc/whatsnew/3.13.rst`, 2866 lines) | § asyncio (681-757); § Free-threaded CPython (311-369); § Optimizations (1485-1509) — which contains **no** asyncio entry. |
| [Pending removal in Python 3.14](https://docs.python.org/3.13/deprecations/pending-removal-in-3.14.html) | The child-watcher deprecations and the `get_event_loop` `DeprecationWarning`, whose implementation is at `Lib/asyncio/events.py:710-713`. |

### Measurements made for this document

All run on the install described in
[Reproducing the line numbers](#reproducing-the-line-numbers): CPython 3.13.11,
GIL enabled (`sys._is_gil_enabled()` → `True`), Linux 6.8, `EpollSelector`. These
are measurements, not sources; they are reported because they are reproducible and
because they falsify plausible assumptions.

| Measurement | Result | Where used |
| --- | --- | --- |
| `_CTask` vs `_PyTask`, 200 000 bare-yield steps | 0.286 s vs 0.319 s (1.12×) | [§3.3](#33-what-the-c-version-actually-accelerates) |
| C vs Python `Task`+`Future`, 100 000 awaits | 0.278 s vs 0.411 s (1.48×) | [§3.3](#33-what-the-c-version-actually-accelerates) |
| Eager vs lazy task factory, 100 000 `create_task(noop())` | 0.079 s vs 0.367 s (4.64×) | [§6.3](#63-312-the-eager-task-factory) |
| `call_soon_threadsafe` vs `call_soon` from a worker thread, loop parked in `sleep(3.0)` | 0.000 s vs 2.803 s latency | [§5.4](#54-what-actually-happens-if-you-call-call_soon-from-another-thread) |
| `_timer_cancelled_count` after a buried cancelled timer fires | counter 1, `_scheduled` empty | [§1.4](#14-step-1--cancelled-timer-hygiene) |
| `Future.__await__` flag transition | `False` → yields self → `True` | [§2.4](#24-the-_asyncio_future_blocking-protocol) |
| `asyncio.Task is _asyncio.Task`, `events._get_running_loop.__module__` | `True`, `'_asyncio'` | [§3.2](#32-how-the-c-accelerator-is-swapped-in) |
| `hasattr(asyncio, 'free_running_loop')` | `False` | [§9](#9-what-could-not-be-verified) |

---

## 9. What could not be verified

Stated plainly, because a confident sentence with nothing behind it is the one
failure this document should not contain.

1. **`asyncio.free_running_loop` does not exist, in 3.13 or anywhere I could find.**
   It was on the brief as a "verify, don't assume" item. `grep -rn free_running_loop`
   over the whole of `/home/qas/miniconda3/lib/python3.13/asyncio/` returns nothing;
   `hasattr(asyncio, 'free_running_loop')` is `False`; the string does not appear in
   `Doc/whatsnew/3.13.rst`, `Doc/library/asyncio-eventloop.rst`,
   `Doc/library/asyncio-task.rst`, `Doc/library/asyncio-runner.rst` or
   `Doc/library/asyncio-dev.rst` at tag `v3.13.11`. No such API is described here.

2. **I did not trace the original changeset that introduced the `ntodo` idiom.**
   [§1.8](#18-step-6--the-drain-and-why-ntodo-is-snapshotted) is argued from the
   in-source comment (`base_events.py:2027-2032`), from
   `test__run_once_schedule_handle`, from the documented `run_forever` behaviour,
   and from the `collections.deque` guarantee. The comment says "Use an idiom that
   is thread-safe without using locks"; I did not find the commit or Tulip-era
   issue that first wrote it, so the *historical* motivation is inferred from the
   comment rather than sourced from a discussion.

3. **The `_timer_cancelled_count` staleness in
   [§1.4](#14-step-1--cancelled-timer-hygiene) is my own reading plus a
   reproduction, not a known issue.** A semantic search of `python/cpython` issues
   for a description of it returned nothing matching. I am confident about the
   behaviour — the code path is short and the reproduction is deterministic — and
   deliberately not confident that it is considered a defect rather than an
   accepted approximation. It is presented as an observation, not a bug report.

4. **No free-threaded interpreter was available to test against.**
   `sys._is_gil_enabled()` returns `True` on this install, so every claim in
   [§6.5](#65-313-free-threading-and-what-it-means-for-the-loop) about the
   `Py_GIL_DISABLED` build is read from the `#ifdef` branches in
   `Modules/_asynciomodule.c` and from PEP 703 and the free-threading how-to. None
   of it was executed. In particular, the claim that running several loops in
   several threads does not contend on a GIL is a reading of `Py_mod_gil`, not a
   measurement.

5. **`ProactorEventLoop` (Windows) is not covered.** Everything in
   [§1](#1-one-iteration-of-_run_once), [§4](#4-timers) and
   [§5.1](#51-the-single-blocking-point) that lives in `BaseEventLoop` applies to
   it, because it inherits the same `_run_once`. Everything in
   [§2](#2-from-await-to-the-selector-and-back) and
   [§5.5](#55-the-self-pipe) does not: IOCP is a completion model, not a readiness
   model, and `Lib/asyncio/proactor_events.py` and `windows_events.py` were not
   read. No claim here should be transferred to Windows without checking.

6. **`sslproto.py`, `streams.py` and `subprocess.py` were not read.** The transport
   trace in [§2.6](#26-the-transport-path-for-contrast) stops at
   `_SelectorSocketTransport`. How `StreamReader` turns `data_received` callbacks
   back into awaitable Futures is one layer further up and is not described here.

7. **The benchmark numbers are single-machine, single-run-best-of-three.** They are
   reported to establish orders of magnitude — "the C accelerator is worth tens of
   percent, not an order of magnitude" and "eager tasks are worth several times" —
   and should not be read as performance characterisation. No CPU pinning, no
   `pyperf`, no isolation from an otherwise-busy desktop.

8. **I did not check whether the two `_run_once` changes between 3.12 and 3.13
   ([§6.7](#67-what-changed-inside-_run_once-itself)) have associated `gh-` issue
   numbers.** They were found by diffing the file across tags, which establishes
   *that* and *when* they changed but not *why* or *by whom*. The
   `_run_forever_setup` split has a motivation because its docstring states one;
   the timeout un-inlining does not, and none is asserted.

9. **PEP 3156's `Status: Final` was taken at face value.** The two disagreements in
   [§7.1](#71-pep-3156-says-call_soon_threadsafe-is-not-signal-safe-the-313-docs-say-it-is)
   and [§7.2](#72-pep-3156-says-stop-stops-short-of-polling-for-io-the-313-docs-and-the-source-say-it-polls-once)
   are reported as PEP-vs-implementation drift. I did not search python-dev or the
   issue tracker for a discussion formally superseding either passage, so it is
   possible one of them was consciously amended somewhere I did not look rather
   than silently outgrown.

10. **The claim that `BaseEventLoop` has no C implementation is scoped to CPython.**
    It is true of the CPython source tree at `v3.13.11` — there is no loop type in
    `Modules/_asynciomodule.c`, and `Lib/asyncio/base_events.py` has no accelerator
    import. Third-party loops (uvloop in particular) replace exactly this layer, and
    nothing in [§1](#1-one-iteration-of-_run_once), [§4](#4-timers) or
    [§5](#5-where-the-loop-blocks-reentrancy-and-threads) should be assumed to hold
    under one.
