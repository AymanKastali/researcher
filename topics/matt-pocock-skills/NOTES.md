# Notes

Working notes and stated preferences for this topic.

## Learner preferences

- **Sources over assertion.** Every substantive claim carries a quotation with a
  `path:NNN` citation into the pinned tree. Three grades of evidence are kept
  visibly distinct and never merged into one voice: what a skill's text
  **instructs**, what a docs page **reports users observed**, and what is
  **synthesis** across the two.
- **Batch, don't drip.** The whole topic is built in one pass. Spacing is advice
  inside the lessons, not a delivery schedule.
- **Dark only, mobile first.** Every page is read at phone width before it ships.
  The skill index and the routing table are the two that need checking there.

## Stated starting point

Answered at the start of the build: the goal is **durable retrieval** rather than
a project needing these flows this week; the skills have been **barely run** —
installed, two or three tried; and the emphasis is **"depends on the use case"**.

That last answer is the one that shaped the curriculum. It is not a refusal to
choose — it names the actual skill being sought. The thing to learn is not five
recipes but the **routing decision** that selects among them. Recorded as
learning record 0001.

## Where this topic came from

Built from `docs/research/matt-pocock-skills-workflows.md` in this repo — a
1,627-line study guide written against the installed plugin tree.

## Sourcing checked beyond the research document

The research document was **not** taken on trust. Its load-bearing claims were
re-derived from the tree on 14 September 2026, before any lesson was written:

- **The invocation split was recounted from the files, not quoted from the
  research.** `grep -l 'disable-model-invocation: true'` across the 25 promoted
  `SKILL.md` files returns **14**; the complement is **11**. Both match. The
  eleven model-invoked names were checked one by one against the skill listing
  this session was given, and they are the same eleven.
- **Version and pin re-read from disk.** `package.json` and
  `.claude-plugin/plugin.json` both say `1.2.3`; `git rev-parse HEAD` returns
  `8b78b531ab965735c5dc74f6f7a219e1e37326df`, dated 2026-08-13.
  `plugin.json`'s `skills` array has **25** entries.
- **The cross-references to user-invoked skills were re-grepped**, and this
  produced the one correction below.
- **Thirty-five load-bearing quotations were checked verbatim** with a fixed
  string grep across `skills/`. Three initially failed and all three were
  encoding, not substance: `3–5` is an en-dash, `Do NOT interview the user —`
  is an em-dash, and `**Don't** reference file paths` uses a curly apostrophe.
  Every lesson quotation uses the tree's own characters.

## One correction to the research document

The research document states, at §5.2: *"In 1.2.3 there are seven such
references: five `setup-matt-pocock-skills` preconditions and the
`diagnosing-bugs` → `improve-codebase-architecture` hand-off."* Five plus one is
six, and the grep returns **seven matching lines** of which **six are
instructions**:

| Line | Kind |
| --- | --- |
| `to-spec/SKILL.md:9` | precondition |
| `to-tickets/SKILL.md:11` | precondition |
| `code-review/SKILL.md:13` | precondition |
| `wayfinder/SKILL.md:25` | precondition |
| `triage/SKILL.md:43` | precondition |
| `diagnosing-bugs/SKILL.md:140` | hand-off |
| `to-tickets/SKILL.md:60` | **descriptive mention, not an instruction** |

Lesson 2 teaches **six inoperative instructions** and shows the seventh line as
the distinction between naming a skill and instructing the agent to run it. The
correction does not change the conclusion — it sharpens what the conclusion is
about.

## Teaching decisions made

- **Routing is the spine, and it sits in the middle rather than at the front.**
  The learner's stated need is choosing correctly, but the choice cannot be
  taught first: it depends on knowing what a user-invoked skill is (lesson 1) and
  what the primitives underneath the flows do (lessons 4–6). Lesson 7 is
  therefore the hinge, and lessons 8–17 are five worked answers to it.
- **The invocation axis is lesson 1, before any flow.** It is one YAML line, and
  it decides which of the twenty-five skills will ever fire on its own, why half
  of them look uninstalled, and why six instructions inside the set cannot
  execute. Teaching a flow before it produces someone who types a chain and
  cannot tell a skipped step from a broken one.
- **Version drift is taught as a lesson, not a caveat.** Both the installed tree
  and a tree 34 commits ahead report `1.2.3`. That is not trivia: it is why a
  correct-sounding instruction from a blog post may not match the file on disk.
- **The two bug lessons split at the Phase 1 gate, not at a page count.** The
  gate is the whole skill; everything after it is described by the skill itself
  as mechanical. Splitting there makes the gate the thing remembered.
- **Every flow lesson leads with its trigger condition**, because the mission is
  routing. The recipe is second.
- **The manual patches are taught as first-class content, not errata.** Four
  things no skill does — create the labels, check the branch, commit before
  review, close the ticket — each stall a flow. They get a reference document of
  their own because they are what a checklist is actually for.
- **No claim is made about what any flow produces in practice.** Nothing was
  executed. Lessons say what a skill's text instructs, and separately what users
  are reported to have observed.

## Open questions for a future session

- **Nothing here has been run.** This is the topic's largest weakness and it is
  stated on the pages. The first real `/to-tickets` or `/wayfinder` session
  should produce a learning record, and lesson 14 or 16 will probably need
  revising against what actually happened.
- **The install is 34 commits behind and that gap will close.** When the
  marketplace pin moves, lessons 1 and 2 need re-checking first: the unreleased
  changesets replace `` Run a `/grilling` session `` with
  `Call the Skill tool with "grilling"`, and delete the `diagnosing-bugs` Phase 6
  hand-off. Lesson 2's count of six drops to five if only the hand-off is removed.
- **The skill listing observation is first-hand and undocumented.** That this
  session sees exactly eleven `mattpocock-skills:*` entries is what the harness
  showed, not what any document states. If a future harness shows all
  twenty-five, lesson 2's first section is wrong and should be rewritten rather
  than patched.
- **`/triage` is indexed but thinly taught.** It appears in lesson 7's routing
  table and lesson 11's step 0, and nowhere else. If incoming issues ever become
  real work, it deserves a lesson of its own.
- **No lesson covers `/improve-codebase-architecture` or `/codebase-design` as
  flows.** Both are named where they are reached from; neither is taught. That
  was a scope decision, not an oversight — module design is its own mission.
