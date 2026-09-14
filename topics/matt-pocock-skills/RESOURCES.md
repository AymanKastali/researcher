# The Matt Pocock Skills Resources

The subject of this topic is a body of text that ships on disk, so the primary
source is unusually easy to reach: it is a directory you can `grep`. Everything
below was read while building the lessons.

## Knowledge

### The primary source — the installed plugin tree

- **`mattpocock-skills` plugin, version 1.2.3**, read on disk at
  `/home/qas/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.3/`
  Git `8b78b531ab965735c5dc74f6f7a219e1e37326df`, dated 2026-08-13. Use for:
  **everything**. A `SKILL.md` is what the agent actually executes, and is the
  only authority on what a skill does. Every `path:NNN` citation in this topic
  refers to this tree at this commit.

- **`.agents/invocation.md`** — the one-axis split between user-invoked and
  model-invoked skills, and the invariant that nothing but a human can fire a
  user-invoked one. Use for: lesson 1, and any question beginning "why didn't
  that fire".

- **`.agents/adr/0001-explicit-setup-pointer-only-for-hard-dependencies.md`** —
  the hard-dependency / soft-dependency split. Use for: what actually breaks if
  `/setup-matt-pocock-skills` is skipped.

- **`.agents/adr/0002-ship-as-a-claude-code-plugin.md`** — records that the
  official marketplace listing pins a commit sha, so a release reaches users when
  the pin moves rather than when a tag lands. Use for: why an install can sit 34
  commits behind while reporting the current version.

- **`skills/engineering/ask-matt/SKILL.md`** — the router: the main flow, the
  on-ramps, the standalones, and one-paragraph summaries of all twenty-five.
  Use for: routing. But note it is a **secondary source over the skills it
  describes** — its own docs page says so — and it is hand-maintained.

- **`skills/engineering/ask-matt/PHASE-BOUNDARIES.md`** — the ordered five-question
  tree for continue / clear / handoff / subagent / compact. Use for: every
  decision about what to do with a context window.

- **`CHANGELOG.md`** — release history, and the record of every renamed and
  retired skill. Use for: working out why a name from a blog post fires nothing.

- **`docs/engineering/*.md` and `docs/productivity/*.md`** (20 pages) — one
  human-facing page per promoted skill, in question-and-answer form, recording
  problems users actually hit. Use for: observed failure modes and known gaps.
  **Do not use to establish what a skill does** — the repo declares these a lower
  authority than the `SKILL.md` they describe, and they lag it.

### Secondary — the public repository

- [mattpocock/skills on GitHub](https://github.com/mattpocock/skills)
  `main` at `3cca18b368ae95cdbdebbff572ccafa662551015` (2026-09-04), **34 commits
  ahead** of the installed tree while carrying the same version string `1.2.3`.
  Use for: checking whether a surprising behaviour has already been changed, and
  for the unreleased `.changeset/` entries that explain why. Where it disagrees
  with the installed tree, the installed tree is what runs.

- Published per-skill pages at `https://aihero.dev/skills-<skill-name>`.
  Not fetched — the same pages ship in the tree under `docs/`, which is the copy
  that matches this install.

### Context on this machine

- **`~/.claude/CLAUDE.md`** — declares this set the default engineering workflow
  and carries the precedence table over `superpowers:*`, plus the four
  superpowers skills kept for what this set does not cover. Use for: the gap
  list in lesson 19.
- **This repository's `CLAUDE.md`, `CONTEXT.md`, `docs/agents/` and
  `docs/adr/0001`** — a worked example of everything
  `/setup-matt-pocock-skills` and `/domain-modeling` produce. Use for: lessons 3
  and 5, where seeing the output beats reading the template.

### The research this topic was built from

- **`docs/research/matt-pocock-skills-workflows.md`** in this repository — the
  1,627-line study guide these lessons sequence. Use for: the long form of any
  lesson, the full skill inventory, and the handoff-map evidence. Its one
  arithmetic slip is corrected in `NOTES.md` and in lesson 2.

## Wisdom (Communities)

Not yet established, and this is a real gap rather than an omission — see below.

- [GitHub Issues on `mattpocock/skills`](https://github.com/mattpocock/skills/issues)
  The set's own defect and request tracker, and the place the docs pages' issue
  numbers point. Use for: checking whether a gap taught in lesson 19 has since
  been closed, and for filing one. The nearest thing to a practitioner forum that
  is verifiably first-party.

## Gaps

- **No practitioner community was located.** The docs pages quote user reports
  ("multiple people have reported this", "one field report describes…") without
  naming where those reports were made. Whether there is a Discord, a forum, or
  only the issue tracker is unknown, and no search for one was run. Until that is
  resolved, the issue tracker above is the only verified place to test a
  conclusion against other users.
- **No first-party documentation of the harness side.** How Claude Code resolves
  a `mattpocock-skills:` prefix, and on what basis it excludes user-invoked
  skills from the listing it shows the model, is observed in this session and
  described second-hand in the tree's docs pages. Claude Code's own plugin
  documentation has not been read, and should be if lesson 2 is ever revised.
- **No record of any of these flows being run.** Every claim in this topic is
  about what the text instructs or what a docs page reports. The most valuable
  resource this workspace could acquire is a transcript of an actual
  `/to-tickets` or `/wayfinder` session.
