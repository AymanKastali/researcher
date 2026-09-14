# CPython asyncio Event Loop Resources

Sources for this topic, kept in three grades of evidence that the lessons never
blur. A PEP, a documentation page, and a line of source are three different kinds
of claim, and each page says which one it is using.

1. **PEPs** — the authority for what was *intended and promised*. PEP 3156 is a
   2012 design document with `Status: Final`; it is normative about intent, not
   about the 3.13 code, and in two places it has been outgrown.
2. **`docs.python.org` for 3.13** — the authority for what a user is *entitled to
   rely on*. Claims sourced here are marked **[guaranteed]**.
3. **CPython source at tag `v3.13.11`** — the authority for what the
   implementation *actually does*. Claims sourced only here are marked
   **[impl detail]**: not promised anywhere, and free to change without notice.

Where they conflict, the source is the authority for behaviour and the
disagreement is shown rather than smoothed over. Lesson 15 and the
[Unverified claims](reference/unverified-claims.html) reference collect all five
known conflicts.

All entries were fetched and read while writing
`docs/research/cpython-asyncio-event-loop.md` in this repo, on 12 September 2026.

## Knowledge

### CPython source, tag `v3.13.11`

The primary evidence for this entire topic. Every Python-level file below was
diffed byte-for-byte against the upstream tag before being cited, so a line
number in a lesson matches the line number on GitHub.

- [`Lib/asyncio/base_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/base_events.py)
  2075 lines. **The single most important reading in this topic.** Use for:
  `_run_once` (1970–2051), `run_forever` (678–687), `_run_forever_setup`
  (642–660), `stop` (727–733), `is_running` (768–770), `time` (772–779),
  `call_later`/`call_at`/`call_soon`/`_call_soon` (781–857),
  `_check_thread` (859–874), `call_soon_threadsafe` (876–885), `_add_callback`
  (1955–1958), `_timer_handle_cancelled` (1965–1968), the timer constants
  (56–68), the `NotImplementedError` stubs (541–552), `create_task` (461–484).
- [`Lib/asyncio/events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/events.py)
  882 lines. Use for: `Handle` (29–105) and `Handle._run` (87–105), `TimerHandle`
  (108–168), `_RunningLoop`/`_get_running_loop` (747–786), the `_asyncio` import
  and its rationale (858–871), the `on_fork` hook (874–882).
- [`Lib/asyncio/futures.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/futures.py)
  425 lines. Use for: the `_asyncio_future_blocking` class comment (59–68) —
  **the clearest single statement of the design in the whole codebase** —
  `__schedule_callbacks` (158–170), `set_result` (248–258), `__await__`
  (283–291), the `_asyncio` import (419–425).
- [`Lib/asyncio/base_futures.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/base_futures.py)
  67 lines. Use for: `isfuture` (13–21), which performs a stricter test than the
  documentation describes.
- [`Lib/asyncio/tasks.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/tasks.py)
  1118 lines. Use for: `all_tasks` and its retry loop (44–68), the three-state
  Task invariant comment (76–93), `__init__` (99–128), `cancel`/`cancelling`/
  `uncancel` (198–260), `__eager_start` (262–279), `__step` (281–296),
  `__step_run_and_handle_result` (298–371), `__wakeup` (373–387),
  `__sleep0`/`sleep` (691–721), `create_eager_task_factory` (1007–1033), the two
  task registries (1036–1044), `_enter_task`/`_leave_task` (1057–1070).
- [`Lib/asyncio/selector_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/selector_events.py)
  1322 lines. Use for: `__init__` (59–67), the self-pipe (110–157),
  `_add_reader`/`_remove_reader` (274–306), `add_reader` (344–347),
  `sock_recv`/`_sock_read_done`/`_sock_recv` (364–404), `_process_events`
  (740–752), `_SelectorSocketTransport` read and write paths (923–1185), the
  `sendmsg` capability probe (33–40).
- [`Lib/asyncio/runners.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/runners.py)
  216 lines. Use for: `Runner.close` (64–79), `_lazy_init` (131–148), `_on_sigint`
  (150–157) — the hand-written selector wakeup — and `run` (160–195).
- [`Lib/asyncio/timeouts.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/timeouts.py)
  184 lines. Use for: the `Timeout` state machine (18–23), `reschedule` (50–71),
  `__aexit__` (109–125), `_on_timeout` (127–132), the `timeout_at` docstring on
  the monotonic epoch (165–184).
- [`Lib/asyncio/taskgroups.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/taskgroups.py)
  278 lines. Use for: `_aexit` and the uncancel dance (82–178), `create_task`
  (181–211).
- [`Lib/asyncio/unix_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/unix_events.py)
  1536 lines. Use for: `_process_self_data` (83–88) and `add_signal_handler`
  (90–133) — the two uses of one socket, demultiplexed by the fact that signal 0
  does not exist.
- [`Lib/asyncio/constants.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/asyncio/constants.py)
  41 lines. Use for: `THREAD_JOIN_TIMEOUT = 300` (33–34).
- [`Lib/selectors.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/selectors.py)
  603 lines. Use for: the `BaseSelector.select` contract (158–175),
  `EpollSelector.select` and its round-away-from-zero millisecond rule (435–463),
  `DefaultSelector` resolution (595–603).
- [`Modules/_asynciomodule.c`](https://github.com/python/cpython/blob/v3.13.11/Modules/_asynciomodule.c)
  3777 lines. **Not shipped with a binary install** — fetched from the tag. Use
  for: the `FutureObj_HEAD` struct macro (113–130), `call_soon` (288–320),
  `future_add_done_callback` and the one-element fast path (619–692),
  `FutureIter_am_send` (1557–1593), the `FutureIter` free-list and its
  `Py_GIL_DISABLED` guard (1747–1775), `register_task` (1897–1901),
  `swap_current_task` and its critical section (2024–2028), deferred task-name
  formatting (2086–2093), `task_step_handle_result_impl` (2866–3090),
  `task_eager_start` (3120–3177), `_asyncio__get_running_loop_impl` (3241–3247),
  `module_slots` and `Py_mod_gil` (3754–3759).
- Test suite, used as evidence that a behaviour is *pinned* rather than
  incidental —
  [`test_base_events.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/test/test_asyncio/test_base_events.py)
  (`test__run_once_schedule_handle` 405–422; `test__run_once_cancelled_event_cleanup`
  424–498, which imports the compaction constants by name) ·
  [`test_tasks.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/test/test_asyncio/test_tasks.py)
  (the six-way C/Python parity matrix, 2710–2900) ·
  [`test_futures.py`](https://github.com/python/cpython/blob/v3.13.11/Lib/test/test_asyncio/test_futures.py)
  (`test_isfuture` 138–159).

Earlier tags, fetched only to date changes:
[`Modules/_asynciomodule.c` at `v3.11.0`](https://github.com/python/cpython/blob/v3.11.0/Modules/_asynciomodule.c)
(3505 lines) ·
[`v3.12.0`](https://github.com/python/cpython/blob/v3.12.0/Modules/_asynciomodule.c)
(3815) ·
[`v3.13.0`](https://github.com/python/cpython/blob/v3.13.0/Modules/_asynciomodule.c)
(3749); and `Lib/asyncio/base_events.py` at the same three tags.

### PEPs

- [PEP 3156 — Asynchronous IO Support Rebooted: the "asyncio" Module](https://peps.python.org/pep-3156/)
  Guido van Rossum, BDFL-Delegate Antoine Pitrou. Created 12 Dec 2012, Status
  **Final**, Python-Version 3.3. **The design document this whole subject is a
  reading of.** Use for:
  [§ Basic Callbacks](https://peps.python.org/pep-3156/#basic-callbacks) — strict
  serialisation of callbacks, FIFO `call_soon`, the `call_later`/`call_at`
  equivalence, the undefined order of same-deadline timers, the permitted clocks;
  [§ Thread interaction](https://peps.python.org/pep-3156/#thread-interaction) —
  `call_soon_threadsafe` as *the only* thread-safe method;
  [§ Starting, Stopping and Closing](https://peps.python.org/pep-3156/#starting-stopping-and-closing)
  — `stop()`; [§ Handles](https://peps.python.org/pep-3156/#handles) —
  `add_reader` returns nothing;
  [§ Futures](https://peps.python.org/pep-3156/#futures) — callbacks are never
  called inline; [§ The Scheduler](https://peps.python.org/pep-3156/#the-scheduler)
  — the scheduler may use only the *public* loop API, the constraint that produced
  `_asyncio_future_blocking`;
  [§ Coroutines and the Scheduler](https://peps.python.org/pep-3156/#coroutines-and-the-scheduler)
  — coroutines are optional over a callback core.
  **Caveat:** two of its statements no longer describe CPython. See lesson 15.
- [PEP 492 — Coroutines with async and await syntax](https://peps.python.org/pep-0492/)
  Yury Selivanov, Final, Python 3.5. Use for
  [§ Await Expression](https://peps.python.org/pep-0492/#await-expression): every
  `await` chain bottoms out in a `yield`. **Caveat:** it prescribes
  `__await__ = __iter__` on `asyncio.Future`; CPython does the reverse.
- [PEP 567 — Context Variables](https://peps.python.org/pep-0567/)
  Yury Selivanov, Final, Python 3.7. Use for
  [§ asyncio](https://peps.python.org/pep-0567/#asyncio) and
  [§ Backwards Compatibility](https://peps.python.org/pep-0567/#backwards-compatibility)
  — the normative statement that `call_soon`, `call_later`, `call_at` and
  `add_done_callback` run callbacks in the context they were called in.
- [PEP 703 — Making the Global Interpreter Lock Optional in CPython](https://peps.python.org/pep-0703/)
  Sam Gross. Use for
  [§ Container Thread-Safety](https://peps.python.org/pep-0703/#container-thread-safety)
  — per-object locks give GIL-like, not atomic, protection — and
  [§ Python Critical Sections](https://peps.python.org/pep-0703/#python-critical-sections)
  — the mechanism `swap_current_task` uses.

PEP 525 and PEP 530 (asynchronous generators, `async` comprehensions) were
considered and are deliberately not cited: the async-generator hooks in
`_run_forever_setup` touch them, but nothing this topic teaches turns on
generator semantics.

### Python 3.13 documentation

The authority for what is **[guaranteed]**. All quotations were taken from the
reST sources at tag `v3.13.11` so they are exact and line-citable; each links to
the rendered 3.13 page.

- [Event Loop](https://docs.python.org/3.13/library/asyncio-eventloop.html)
  (`Doc/library/asyncio-eventloop.rst`, 2060 lines) — `run_forever` and `stop`
  (115–163), `call_soon` (218–233), `call_soon_threadsafe` (235–253),
  `call_later`/`call_at` and the clock-resolution note (281–340), `loop.time`
  (342–350), `add_reader`/`add_writer` (1004–1030), `sock_recv` (1049–1063).
- [Coroutines and Tasks](https://docs.python.org/3.13/library/asyncio-task.html)
  (`Doc/library/asyncio-task.rst`, 1472 lines) — `sleep(0)` (478), the Eager Task
  Factory section and its semantic-change warning (609–651).
- [Futures](https://docs.python.org/3.13/library/asyncio-future.html)
  (`Doc/library/asyncio-future.rst`) — `isfuture` (22–31), the *only* place
  `_asyncio_future_blocking` appears in the documentation at all.
- [Developing with asyncio](https://docs.python.org/3.13/library/asyncio-dev.html)
  (`Doc/library/asyncio-dev.rst`, 248 lines) — Debug Mode (18–58), Concurrency and
  Multithreading (63–117), Running Blocking Code (119–130).
- [Runners](https://docs.python.org/3.13/library/asyncio-runner.html) — `asyncio.run`,
  and the clause making the *caller's* `loop_factory` responsible for
  `set_event_loop`.
- [`collections.deque`](https://docs.python.org/3.13/library/collections.html#collections.deque)
  (`Doc/library/collections.rst:458-461`) — the thread-safe append/pop guarantee
  the `_ready` idiom rests on.
- [Python support for free threading](https://docs.python.org/3.13/howto/free-threading-python.html)
  — § Thread safety (74–90), which labels built-in container locking as a
  description of the implementation rather than a guarantee.
- What's New, for dating features —
  [3.11](https://docs.python.org/3.11/whatsnew/3.11.html#asyncio) (575–617) ·
  [3.12](https://docs.python.org/3.12/whatsnew/3.12.html#asyncio) (642–679) ·
  [3.13](https://docs.python.org/3.13/whatsnew/3.13.html) (§ asyncio 681–757;
  § Free-threaded CPython 311–369; § Optimizations 1485–1509, which contains **no**
  asyncio entry). **Caveat:** the 3.13 `create_task` `**kwargs` entry describes
  three signatures and only one of them has it. See lesson 15.

## Wisdom (Communities)

Checked against the Python Software Foundation's own
[community pages](https://www.python.org/community/) on 12 September 2026.

- [python-dev on Discourse](https://discuss.python.org/c/core-dev/23) — where
  CPython's core development is discussed in the open. Use for: finding out *why*
  a piece of the loop is shaped the way it is. Searching for a feature name is
  usually more informative than the release note, because the objections survive.
- [The CPython issue tracker](https://github.com/python/cpython/issues) — the
  right place to settle "is this a bug or an accepted approximation?", which is
  exactly the question lesson 12's counter observation raises. Search before
  filing; a semantic search for that behaviour found nothing, which is itself a
  finding rather than a licence to assert.
- [`python/cpython` pull requests touching `Lib/asyncio/`](https://github.com/python/cpython/pulls?q=is%3Apr+asyncio)
  — the review threads are the single best source of design rationale in this
  subject. `Task.cancel` carries a source comment pointing directly at
  [PR #31394](https://github.com/python/cpython/pull/31394#issuecomment-1053545331)
  as "controversial", which is an invitation to read it.
- [Python Discourse, Async-SIG category](https://discuss.python.org/c/async-sig/20)
  — the async special-interest group. Use for: questions that are about asyncio's
  direction rather than its current code.
- [uvloop](https://github.com/MagicStack/uvloop) — not a community but the
  sharpest available test of understanding. It replaces exactly the layer this
  topic opens up, so reading its `loop.pyx` against `base_events.py` shows which
  of these lessons describe *asyncio* and which describe *CPython's loop*.

No preference for or against joining communities has been stated. Record it here
if one is.

## Gaps

Areas the mission touches where the record is thin. These are gaps in the
sources, not omissions from this workspace.
`docs/research/cpython-asyncio-event-loop.md` §9 lists all ten.

- **The `_timer_cancelled_count` staleness is an observation, not a known issue.**
  It is reproducible and the code path is short, but a semantic search of
  `python/cpython` issues found nothing describing it. It is taught in lesson 12
  as an observation, and deliberately not as a bug.
- **The historical motivation for the `ntodo` idiom was not traced.** Lesson 3 is
  argued from the in-source comment, from `test__run_once_schedule_handle`, from
  the documented `run_forever` behaviour and from the `deque` guarantee. The
  original Tulip-era changeset was not found.
- **No free-threaded interpreter was available.** Every claim about the
  `Py_GIL_DISABLED` build is read from `#ifdef` branches, PEP 703 and the
  free-threading how-to. None of it was executed.
- **`ProactorEventLoop` was not read**, so nothing about the selector, the
  self-pipe or the `await` round trip should be transferred to Windows.
- **The two `_run_once` changes between 3.12 and 3.13 have no cited issue
  numbers.** Diffing tags establishes *that* and *when* they changed, not *why*.
- **The benchmark numbers are single-machine, best-of-three.** They establish
  orders of magnitude and nothing finer. No CPU pinning, no `pyperf`.
- **`asyncio.free_running_loop` does not exist.** It was on the research brief as
  a "verify, don't assume" item and could not be found in the source, in the
  documentation, or on the interpreter. No such API is described anywhere in this
  workspace.
