# The Matt Pocock Skills Glossary

The vocabulary of the `mattpocock-skills` plugin at version 1.2.3. Terms are the
set's own words wherever it has one; where this workspace has had to name
something the set leaves unnamed, the entry says so.

## Invocation

**Skill**:
A directory holding a `SKILL.md` whose frontmatter names it and whose body is the
instruction an agent follows. The unit the plugin ships.
_Avoid_: Command, prompt, macro

**Promoted skill**:
A skill in the `engineering/` or `productivity/` bucket, and therefore listed in
`plugin.json` and shipped by the plugin. There are twenty-five.
_Avoid_: Installed skill, available skill

**User-invoked skill**:
A skill carrying `disable-model-invocation: true`, reachable only by a human
typing its name. No other skill can reach it. Fourteen of the twenty-five.
_Avoid_: Manual skill, slash command, explicit skill

**Model-invoked skill**:
A skill with no such flag, reachable by the agent on its own as well as by the
human. Eleven of the twenty-five.
_Avoid_: Automatic skill, auto-skill

**Context pointer**:
The `description:` string in a model-invoked skill's frontmatter. It is
permanently loaded and it is what the agent matches a request against, so it is
the trigger rather than a summary.
_Avoid_: Summary, blurb, docstring

**Inoperative instruction**:
A line inside a skill telling the agent to run a user-invoked skill. The
invocation invariant makes it unexecutable, so it can only be read as a message
to the human. This workspace's term; the set has none. Six exist in 1.2.3.
_Avoid_: Broken link, bug, dead reference

## Structure

**Flow**:
A path through several skills. The set has one **main flow** and three
**on-ramps** that merge onto it.
_Avoid_: Workflow, pipeline, process

**Main flow**:
`grill-with-docs → to-spec → to-tickets → implement → code-review`. The route
most work travels, printed identically in four places in the tree.
_Avoid_: The chain, the happy path

**On-ramp**:
A starting situation that generates work and then merges onto the main flow:
`/triage`, `/diagnosing-bugs`, `/wayfinder`.
_Avoid_: Entry point, trigger

**Vocabulary layer**:
A model-invoked skill that runs beneath the others as the single source of truth
for a set of words — `/domain-modeling` for the domain, `/codebase-design` for
module shape. Consulted, not run as a session.
_Avoid_: Helper, library, utility skill

**Precondition**:
`/setup-matt-pocock-skills`, run once per repo before the first engineering flow.
_Avoid_: Setup step, install, bootstrap

## The interview

**Grilling**:
The interview primitive: relentless questioning in rounds until a shared
understanding is reached. Five skills run it internally.
_Avoid_: Interview, Q&A, discovery

**Design tree**:
The structure grilling maps a problem onto — every decision branching into the
decisions that hang off it.
_Avoid_: Decision tree, outline

**Frontier**:
Every decision whose prerequisites are already settled — the questions askable
now without guessing. The word carries a second, related sense in `/to-tickets`
and `/wayfinder`: every ticket whose blockers are all done.
_Avoid_: Open questions, backlog, next up

**Facts/decisions split**:
Grilling's contract. Finding facts is the agent's job, always; making decisions
is the human's, always. An agent that answers its own question has broken the
skill rather than interpreted it liberally.
_Avoid_: Division of labour, roles

**Shared understanding**:
The state that ends a grilling session, and it must be confirmed by the human
before anything is acted on. The frontier being empty is the condition; the
confirmation is the gate.
_Avoid_: Agreement, sign-off, alignment

## Building

**Spec**:
The document `/to-spec` synthesises from a conversation without interviewing, and
publishes to the tracker labelled `ready-for-agent`.
_Avoid_: PRD, requirements, design doc

**Seam**:
The point at which a feature is tested. Agreed with the human before any test is
written — in `/to-spec` step 2 during the full chain, or in `/tdd`'s first
exchange when running it alone.
_Avoid_: Boundary, interface, test point

**Tracer-bullet ticket**:
A slice cutting a narrow but complete path through every layer, demoable on its
own, sized to fit one fresh context window.
_Avoid_: Story, task, issue, vertical slice

**Blocking edge**:
A declared dependency from one ticket to another, native on a real tracker and
plain text on a local one. What makes a frontier computable.
_Avoid_: Dependency, link, blocker

**Wide refactor**:
One mechanical change whose blast radius fans across the codebase, so no vertical
slice can land green. Sequenced expand–migrate–contract instead.
_Avoid_: Big refactor, sweeping change

**Fixed point**:
The commit, branch, tag or merge-base `/code-review` compares against, via
`git diff <fixed-point>...HEAD`. Committed work only.
_Avoid_: Base, baseline, start point

## Mapping

**Map**:
The `wayfinder:map` issue holding a destination and pointers to its decision
tickets. An index, never a store — a decision lives in exactly one place.
_Avoid_: Plan, roadmap, epic

**Destination**:
What a map is finding its way to, settled first because it fixes the scope.
_Avoid_: Goal, outcome, target

**Fog**:
The part of the work that cannot yet be stated as a question, held in the map's
**Not yet specified** section. The test for graduating it is whether the question
can be _stated_ precisely now, not whether it can be answered.
_Avoid_: Unknowns, TBD, backlog

**Decision ticket**:
A child of the map that produces a decision rather than a deliverable. One of
four types: research, prototype, grilling, task.
_Avoid_: Spike, investigation, chore

**HITL / AFK**:
Whether a ticket resolves through live exchange with a human, or is driven by the
agent alone.
_Avoid_: Manual/automatic, interactive/batch

## Sessions

**Phase**:
A chunk of work inside a session — the grilling, the implementation, the QA. It
ends when you think "ok, we're done with that".
_Avoid_: Stage, step, sprint

**Phase boundary**:
The gap between two phases, and the only place the continue/clear/handoff/
subagent/compact decision belongs.
_Avoid_: Checkpoint, breakpoint

**Smart zone**:
The window — about 150k tokens — within which the model still reasons sharply.
The budget the context-hygiene rules are spending.
_Avoid_: Context window, token limit

**Primary source (of a session)**:
The session as it happened, unsummarised. Every phase-boundary move except
Continue converts it into a secondary source. Distinct from a primary source of
_knowledge_, which is what this repo cites claims to.
_Avoid_: Full context, raw history
