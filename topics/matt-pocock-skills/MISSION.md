# Mission: The Matt Pocock Skills, and Choosing Between Them

## Why

To reach for the right flow without looking it up, and to know — before running
it — what that flow will and will not do. These skills are already the declared
default engineering workflow in `~/.claude/CLAUDE.md`, but only two or three
have actually been run. The gap that matters is not knowing what each skill
contains; it is **routing**: standing at the start of a piece of work and
picking correctly between "just build it", "spec it and split it", "diagnose
it", and "chart a map" — and recognising, mid-session, when a skill has
misfired and is quietly doing the wrong thing.

## Success looks like

- Naming which of the twenty-five skills the agent can fire on its own and which
  only a human can, and explaining the one-line frontmatter flag that decides it.
- Reading an instruction inside a skill that says "run `/setup-matt-pocock-skills`"
  and knowing it is addressed to you, not to the agent — and being able to say why.
- Choosing between `/implement`, `/to-spec`, and `/wayfinder` from one
  measurement, and saying what that measurement is.
- Stating what `/setup-matt-pocock-skills` silently gets wrong if it is skipped —
  not "it breaks", but the specific wrong default it falls back to.
- Reciting the grilling contract: what the agent owes the session, what the
  learner owes it, and the sentence that ends it.
- Naming the gate `/diagnosing-bugs` will not cross, and what has to be true —
  four properties — before it crosses.
- Listing the four things that must be done by hand because no skill in the set
  does them, and saying which flow stalls if each is skipped.
- Working the phase-boundary tree in order and explaining why `/compact` sits at
  the bottom rather than the top.
- Separating what a skill's text instructs from what users report it actually
  does, and citing the right kind of source for each.

## Constraints

- **Durable retrieval is the goal**, not a project shipping this week. Lessons
  carry retrieval practice and are written to be spaced over days.
- **Near-zero starting point.** Two or three skills have been run; the
  spec-and-tickets chain, `/wayfinder` and `/triage` have not. Nothing is taught
  as "you will recognise this from having run it".
- Built in one pass. The spacing is advice inside the lessons, not a delivery
  schedule.
- **The version is pinned and the pin is load-bearing**: plugin **1.2.3**,
  git `8b78b53`, read on disk. The public repo is 34 commits ahead while
  reporting the same version string, so "1.2.3" alone identifies nothing.
- Every claim is traceable to a quoted line of the installed tree, or is
  labelled as a user report, or is labelled as synthesis.

## Out of scope

- **Writing skills.** `/writing-for-agents` is indexed as part of the set but not
  taught. Authoring skills is a different mission from operating them.
- **The four non-plugin buckets.** `misc/` and `in-progress/` are not reachable
  through the plugin, so they are named once and never planned around.
- **Superpowers in depth.** The four skills that fill this set's gaps are named
  where the gap appears; their own workflows are not taught here.
- **Harness internals.** How Claude Code loads a plugin, resolves a namespace, or
  injects a skill listing is treated as observed behaviour, not explained
  mechanism — no source for it was read.
- **Any judgement on whether the set is worth adopting.** The mission is to
  operate it correctly, and evaluation would pull every lesson toward argument.
