# Working notes

## Teaching preferences

**How a page looks is documented once, at `docs/agents/design-system.md`** —
dark theme, mobile responsiveness, the verified palette, the highlight.js
setup, and the page boilerplate. Read it before authoring.

**The teaching contract is `docs/agents/teaching-standard.md`** — this topic is
a `mattpocock-skills:teach` workspace, and that file records what the skill
requires of every lesson, what the quiz rules are, and how to check them
(`uv run python docs/agents/check-lessons.py`). Added 2026-09-11 at Ayman's
instruction that everything here adhere to the skill.

The rules that remain here are specific to this topic:

- **Illustrative code is Python.** SQL and DDL stay SQL; HTTP exchanges stay
  HTTP.
- **No code trees in the workspace.** Ground claims in primary sources.
- **Recall, not recognition.** One-attempt quizzes and free-recall prompts.

## Workspace conventions

- **This topic stands alone.** It must not refer to, link to, or assume any
  other topic in this repo. Stated by Ayman on 2026-09-11 and applied the same
  day; the rule is in `docs/agents/topic-independence.md` and what it cost here
  is in `learning-records/0001`. Concepts the lessons need are explained in
  place, briefly, wherever they are used.
- Lessons: `lessons/NNNN-dash-case.html`, linking `../../../assets/lesson.css`
  and `../../../assets/quiz.js`.
- **Assets are shared, and there is exactly one copy** — `assets/` at the repo
  root, hoisted there on 2026-09-11 when Ayman asked for the shared style to
  live at the root. A fix to `lesson.css` or `quiz.js` is applied once. **Do not
  copy it into a topic.** Shared *styling* is not a cross-topic reference; the
  independence rule is about content.
- Markdown wraps at 80 columns. Long URLs go in reference-style definitions.

## Teaching backlog

Sequenced by dependency:

1. ~~**Lesson 01 — the key and the server's algorithm.**~~ Delivered
   2026-09-11. The ambiguous failure, RFC 9110's retry rule as the hook, the
   four-step algorithm, the three duplicate cases with their status codes, the
   claim-and-work transaction, and three real APIs with three different key
   shapes.
2. ~~**Lesson 02 — what to store, and for how long.**~~ Delivered 2026-09-11.
   The five fingerprint strategies (draft §2.4) and why the fingerprint is
   compared *after* the lookup rather than folded into it (see
   `learning-records/0002`); the stored-versus-not table, including the
   discovery that the `409` is *not* cached; `Idempotent-Replayed`; the
   reconciled `500` whose cached response stays wrong; retention argued from
   two independent requirements rather than quoted; a reaper that flags
   stranded `in_progress` rows. Opens with a two-question retrieval warm-up on
   Lesson 01 — the first spacing in this topic.
3. ~~**Lesson 03 — the key across a trust boundary.**~~ Delivered 2026-09-11.
   The composite lookup key (draft §5) and the rule that the scope value must be
   derived server-side; why the leak is worse than an ordinary one — **the
   replay path returns before the endpoint runs, so handler-level ownership
   checks never execute**; AWS Regional/Zonal as the worked contrast, and from
   it the three-bucket rule (scope / fingerprint / ignored) in
   `learning-records/0003`; the availability price of a wider scope; the time
   axis of scope via Stripe's "within your account over the last 24 hours";
   key validation and the published-format rule; and the two replay contracts
   in `learning-records/0004`. Opens with a two-question warm-up on Lesson 02.
4. ~~**Lesson 04 — foreign state mutations.**~~ Delivered 2026-09-11. Brandur's
   atomic-phase model: the foreign state mutation and why the test is
   rollback-ability rather than ownership (Kafka counts); the two failures of
   putting the call inside the transaction; the three mechanical rules for
   cutting phases, recovery points, and the handler as a DAG state machine in
   which Lesson 01's replay is simply the terminal state; the derived key on
   *your own* outbound call; the staged-job drain named as a transactional
   outbox and taught in place (`learning-records/0005`); the completer versus
   the reaper; and the inversion of "indeterminate" when the far side has no key
   (`learning-records/0006`). Opens with a two-question warm-up drawing on
   Lessons 01 and 03.

**The topic is complete as scoped.** Nothing further is queued. See "If the
topic is reopened" below.

## Debts carried by Lesson 01

- **Nothing in this topic has been run.** Every claim is cited to a primary
  source; none is measured. That is deliberate (see `MISSION.md`), but it means
  the lesson must never state a number as though it were observed.
- **The `SELECT … FOR UPDATE` claim step is argued, not benchmarked.** It is
  a standard primitive put to a purpose it is not usually benchmarked for, and
  the contention profile is unusual (one row per client request rather than a
  batch). Unmeasured.
- **`409` versus "block and wait" is stated as a choice without a
  recommendation.** The draft says respond with a conflict; a real server could
  also hold the connection until the original finishes. No source examined
  compares them.
- **The lesson asserts that most implementations return the cached response
  with the original status code.** Verified for Stripe explicitly. Inferred for
  AWS and Google from "the retry succeeds without performing any further
  actions" / "return the response for the previously successful request", which
  is weaker. Flagged in the lesson.
- **Structured-Field quoting is a footnote, not a section.** Draft §2.1 makes
  the value a Structured Header String, so it is quoted on the wire; no vendor
  does this. If Ayman pulls on it, it belongs in Lesson 02.

## Debts carried by Lesson 02

- **Still nothing run.** The reaper snippet is shape, not a benchmarked
  implementation, and the lesson says so in the caption.
- **The fingerprint reading is an argument from mechanism, not a citation.** No
  source says the draft is ambiguous at §2.6. See `learning-records/0002`.
- **"Most implementations set a replay header" is not claimed** — only Stripe's
  `Idempotent-Replayed` was verified. Neither AWS nor Google documents an
  equivalent, and the lesson does not imply they do.
- **Payload retention is raised as a push-back prompt, not answered.** Storing
  `request_params` for 72 hours is itself a data-retention question and no
  source examined addresses it.
- **No source compares hashing strategies empirically.** The five approaches in
  §2.4 are listed with trade-offs argued from mechanism only.

## Debts carried by Lesson 03

- **Still nothing run**, and now the stakes are higher: this lesson makes a
  security argument. The leak is the draft's claim, but the explanation of *why*
  it evades authorisation — the replay returning before the endpoint — is argued
  from Lesson 01's own handler, not quoted. Flagged inline in the lesson.
- **Which identity belongs in the scope column is unsourced.** No source chooses
  between account, user, organisation and API credential. The "scope on the
  boundary the data is drawn on, not on the credential" rule is mine. So is the
  claim that credential-scoped keys break across a rotation.
- **No source examined covers multi-region deployments with separate key
  tables.** AWS's Regional/Zonal note describes their own product, not a recipe.
  This gap was already in `RESOURCES.md`; Lesson 03 raises it as a push-back
  prompt and does not pretend to answer it.
- **The injection bullet in draft §5 is quoted but not developed.** What an
  injection through an idempotency key actually looks like depends entirely on
  the store, and no source gives an example. Left as a reason to validate rather
  than a demonstrated attack.
- **Stripe's account scoping is inferred from one sentence** about client-side
  key uniqueness. The API reference examined does not state the server's lookup
  key anywhere.

## Debts carried by Lesson 04

- **Still nothing run.** The phase machine is shape, not a tested implementation,
  and the lesson's caption says so. Brandur's original is Ruby with
  `SERIALIZABLE` transactions; the Python here is a translation of structure, not
  of behaviour.
- **The lock-contention argument against in-transaction API calls is mine.**
  Brandur gives only the correctness reason (commit before calling out). The
  claim that holding the claim-row lock across a network call exhausts the
  connection pool follows from Lesson 01's `SELECT … FOR UPDATE` step and is
  unmeasured. Flagged inline; the lesson's own push-back prompt invites Ayman to
  demand proof, and the honest answer is that there is none here.
- **The "indeterminate inverts" reading is a synthesis, not a citation.** Both
  halves are quoted (Stripe to clients, Brandur to callers) but no source puts
  them side by side. Flagged in the lesson and in `learning-records/0006`.
- **The completer's security risk is my observation.** Brandur notes it needs
  *"a specialized internal authentication path that allows it to retry anyone's
  request"* without comment. That it deliberately bypasses Lesson 03's scope, and
  therefore needs to be small and unable to return a body, is not in any source.
- **No source examined says what to do when the far side is non-idempotent and
  the operation must happen.** "Mark it failed and get a human" is an admission,
  not a design. Concede this if pushed.
- **The MongoDB example is dated and the lesson says so.** Brandur wrote it in
  2017; multi-document transactions landed in MongoDB 4.0 in 2018. The structural
  claim survives, the example does not. *This correction is from parametric
  knowledge and was not fetched* — verify before repeating it anywhere it
  matters.

## If the topic is reopened

Nothing is queued, and the four lessons cover the mechanism end to end. The
candidates, in rough order of value:

- **Run something.** Every debt above starts with "nothing has been run", and
  that is the single biggest weakness of the topic. A Postgres container, a
  handler, a killed process mid-phase — that would convert three inferences into
  observations.
- **The completer and the enqueuer as working code**, which is also the natural
  place to test the scope-bypass worry.
- **The multi-region question**, which `RESOURCES.md` lists as a gap no source
  examined settles. This needs a new source, not a new lesson.

## Open questions to revisit

- ~~How deep does this topic go?~~ Answered: interview depth, four lessons
  requested and delivered on 2026-09-11.
- **No quiz results have been observed yet, for any lesson.** Every lesson after
  01 opens with a two-question warm-up on its predecessors, so the retrieval
  data exists in the browser — it has just never been reported back. Worth
  asking for directly. Without it there is no evidence about what is retained
  rather than merely covered, which is the only signal this workspace has.
- **No interleaving is available, and it is worth knowing what that costs.**
  Interleaving — mixing questions from two confusable mechanisms — is the
  strongest retrieval format there is, and Lesson 04 briefly used it before the
  independence rule of 2026-09-11 removed the option. What remains inside a
  topic is spacing: each warm-up draws on earlier lessons here. Useful, weaker.
  See `learning-records/0001`.
- **Ayman asked for all lessons up front, to study in one weekend** (stated
  2026-09-11). This is the opposite of the skill's intended cadence, and the
  lessons were built anyway because it is his call. The mitigation given: take
  each quiz *before* reading its lesson (a pretest works without a gap), split
  the weekend into blocks rather than one sitting, re-derive from the reference
  cards instead of rereading, and — the part that actually matters — come back
  about five days later for a cold mixed test. **That follow-up test is now the
  most valuable thing this workspace can produce.** It does not exist yet.
- Interview timeline still unknown. If a date exists, the spacing of the
  re-test should be planned backwards from it.
