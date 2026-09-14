# The Matt Pocock Skills, and the Workflows They Actually Support

A study guide, built from primary sources.

**Scope.** This is a working reference for someone who has the
`mattpocock-skills` Claude Code plugin installed and wants to use it to do real
engineering rather than to admire it. It covers what is installed and how the
set is organised, how a skill actually gets fired (which is not obvious, and is
where most of the reported breakage lives), what `/setup-matt-pocock-skills`
writes and why each file matters, a complete inventory of every skill with its
exact triggering `description`, the evidence for how the skills chain into each
other, and then five ordered recipes: develop a small feature, fix a bug,
develop a big multi-part feature, brainstorm an idea, and kickstart a big
project from scratch. It closes with the anti-patterns the skills name
themselves and the gaps they leave.

The target is the **installed plugin, version 1.2.3**, at git
`8b78b531ab965735c5dc74f6f7a219e1e37326df` (2026-08-13), read on disk at
`/home/qas/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.3/`.
The public repository `mattpocock/skills` is used as a **secondary** source,
and only to date changes that have not yet reached this install; its `main` at
`3cca18b368ae95cdbdebbff572ccafa662551015` (2026-09-04) is **34 commits ahead**
of the installed tree while still carrying version 1.2.3. Every place the two
disagree is stated in §2.4 and flagged where it bears on a recipe.

**Sourcing.** Every substantive claim below is tied to a file that was read in
full while writing this document, cited by path and line number and quoted
rather than paraphrased. Two source classes are kept visibly separate. A
`SKILL.md` (and its supporting files) is what the agent actually executes and is
treated as the **primary** source. A page under `docs/` is a human-facing page
about a skill, written by hand and explicitly declared a lower authority by the
repo itself — `docs/engineering/ask-matt.md` says of its own subject: *"It is a
[secondary source] over the skills it describes. Where the router and a
`SKILL.md` disagree, the `SKILL.md` is right."* Docs pages are used here for
observed failure modes and for questions real users asked, never to establish
what a skill does. Where a recipe's **order** is my own synthesis rather than a
quoted instruction, it says so in place, and names the quotes it rests on.
Anything that could not be verified is collected in
[§10](#10-what-could-not-be-verified).

---

## Contents

1. [The Set: What Is Installed, and How It Is Organised](#1-the-set-what-is-installed-and-how-it-is-organised)
2. [Trigger Mechanics: How a Skill Actually Fires](#2-trigger-mechanics-how-a-skill-actually-fires)
3. [Prerequisites: `/setup-matt-pocock-skills` and What It Writes](#3-prerequisites-setup-matt-pocock-skills-and-what-it-writes)
4. [Skill Inventory](#4-skill-inventory)
5. [The Handoff Map](#5-the-handoff-map)
6. [The Five Workflows](#6-the-five-workflows)
7. [Anti-Patterns the Skills Name Themselves](#7-anti-patterns-the-skills-name-themselves)
8. [Gaps, and What Fills Them](#8-gaps-and-what-fills-them)
9. [Sources](#9-sources)
10. [What could not be verified](#10-what-could-not-be-verified)

---

## 1. The Set: What Is Installed, and How It Is Organised

### 1.1 Buckets, and which ones ship

The repository sorts every skill into one of five bucket folders. The rule is
stated in the repo's own `CLAUDE.md`, lines 1–9:

> Skills are organized into bucket folders under `skills/`:
>
> - `engineering/` — daily code work
> - `productivity/` — daily non-code workflow tools
> - `misc/` — kept around but rarely used, not promoted
> - `in-progress/` — beta: public on purpose, feedback wanted, not shipped in the plugin
> - `deprecated/` — no longer used
>
> Every skill in `engineering/` or `productivity/` (the **promoted** buckets) must have a reference in the top-level `README.md` and an entry in `.claude-plugin/plugin.json`'s `skills` array (the Claude Code plugin ships exactly the promoted set). Skills in `misc/`, `in-progress/`, and `deprecated/` must not appear in either.

That last sentence is the operative fact for anyone using the plugin: **the
plugin ships exactly the promoted set, and nothing else.** The installed
`.claude-plugin/plugin.json` lists 25 skill directories — 18 under
`skills/engineering/`, 7 under `skills/productivity/`.

`skills/deprecated/README.md` is one paragraph and matters mostly for what it
rules out:

> Skills I no longer use. This bucket is currently empty — a retired skill is deleted, and the changeset that removes it names whatever replaced it.

So there is no deprecated skill to avoid. There *are* retired names that will
turn up in older blog posts and prompts; they are enumerated in §4.5.

`skills/in-progress/README.md` is explicit that the beta bucket is not reachable
through the plugin at all:

> Beta. These skills are public on purpose — try them and tell me what breaks. They're excluded from the plugin and the top-level README until they graduate to a stable bucket, they get no docs pages, and they can change or disappear without warning.
>
> The plugin won't give you these. Install one directly:
>
> ```bash
> npx skills@latest add mattpocock/skills --skill=<name>
> ```

`skills/misc/README.md` is similar: *"Tools I keep around but rarely used — not
promoted in the plugin."*

**Neither `in-progress/` nor `misc/` is available to a plugin user, so neither
belongs in a daily workflow.** They are listed in §4.4 for completeness and
because two of them (`setup-ts-deep-modules`, `claude-handoff`) are referenced
in the docs pages as things people reach for.

### 1.2 Two install routes, and they are exclusive

`.agents/install-block.md` is the single source of truth for install wording and
states the exclusivity in its own section (lines 55–57):

> ## The two routes are exclusive
>
> The plugin is a managed, read-only bundle you subscribe to. skills.sh writes files you own and edit. Installing both leaves the user with every skill twice — always say "pick one".

The two commands, quoted from the canonical block (lines 9–21):

```bash
claude plugins install mattpocock-skills
```

> Or, from inside a session:
>
> ```
> /plugin install mattpocock-skills
> ```
>
> It's in Claude Code's official marketplace, so there's nothing to add first, and updates arrive automatically.

The "updates arrive automatically" claim is sourced in the same file (line 5):

> `mattpocock-skills` is listed in **Claude Code's official marketplace** — configured name `claude-plugins-official`, source repo `anthropics/claude-plugins-official` — which every Claude Code install has out of the box. There is no marketplace to add first. Official Anthropic marketplaces have auto-update enabled by default ([discover-plugins](https://code.claude.com/docs/en/discover-plugins)), so "updates arrive automatically" is a true claim, not a hope.

There is a consequence worth holding onto. `.agents/adr/0002-ship-as-a-claude-code-plugin.md`
records, in its 2026-08-05 update, that the official listing pins a commit sha:

> The listing's `source` is `{"source": "url", "url": "https://github.com/mattpocock/skills.git", "sha": …}` — the **sha is pinned**, so a release reaches installed users when that pin moves, not the moment we tag. At the time of writing the pin sits two commits behind `main`, which is why it lists 22 skills rather than the 24 in `plugin.json`.

That is exactly the situation this install is in, at a larger distance: the
installed tree is 34 commits behind `main` (§2.4).

### 1.3 The plugin is read-only, so do not edit a `SKILL.md`

`docs/engineering/ask-matt.md` records the advice and why it does not hold:

> **It told me to edit a SKILL.md.**
>
> That advice is often correct and rarely durable. Someone asked it how to make [implement] close tickets, got told to add a line to the skill, and immediately spotted the problem: `npx skills update` overwrites the file, and the plugin install is read-only. Put standing behaviour in your own `CLAUDE.md` or `AGENTS.md`, or say it in the invocation. Prompt-level adaptations survive updates.

This is the correct place for every customisation named later in this document
(one-question-at-a-time grilling, "don't diagnose, just answer", browser tests
after the behaviour works, and so on).

---

## 2. Trigger Mechanics: How a Skill Actually Fires

This is the section to read before any of the recipes. The set splits on one
axis, and getting it wrong is the cause of most of the reported failures.

### 2.1 User-invoked versus model-invoked

`.agents/invocation.md`, lines 3–8, is the primary statement:

> Every `SKILL.md` in this repo is a skill. The one axis that splits them is **invocation** — who can reach it:
>
> - **User-invoked** — reachable **only by the human typing its name**. Set `disable-model-invocation: true` in the frontmatter (Claude Code) and `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (Codex). The `description` is **human-facing**: a one-line summary read by a person browsing slash-commands. Strip trigger lists ("Use when the user says…").
> - **Model-invoked** — reachable by **model or user**. The default: omit `disable-model-invocation` and the `policy` block from `agents/openai.yaml`. The `description` is **model-facing** and keeps rich trigger phrasing ("Use when the user wants…, mentions…, asks for…") so auto-invocation fires. The test for whether a skill should stay model-invoked: _could the model usefully reach for this autonomously?_ (Reuse is the reason to extract a skill, not the test.)
>
> Each harness excludes a user-invoked skill from the model's reach in its own way, so nothing but the human can fire it — no other skill can. A user-invoked skill may invoke model-invoked skills, but it can never reach another user-invoked skill.

The same invariant appears in the top-level `README.md` (line 186):

> These split on one axis — who can invoke them. **User-invoked** skills are reachable only when you type them (e.g. `/grill-me`); their job is to orchestrate. **Model-invoked** skills can be invoked by you _or_ reached for automatically by the agent when the task fits; they hold the reusable discipline. A user-invoked skill may invoke model-invoked skills, but never another user-invoked one.

`skills/productivity/writing-for-agents/SKILL-MECHANICS.md` lines 9–12 adds the
cost model behind the choice:

> - A **model-invoked** skill keeps a `description`, so the agent can fire it autonomously — and other skills can reach it. You can still type its name: model-invocation always _includes_ user reach; a description only ever adds agent discovery, never removes the human's. The description is the skill's top-level context pointer, forced to stay loaded at all times — permanent context load in exchange for discoverability. […]
> - A **user-invoked** skill strips the description from the agent's reach: only the human typing its name can invoke it, and no other skill can. Zero context load, but it spends cognitive load — you are the index that must remember it exists. Mechanics: set `disable-model-invocation: true`; the `description` becomes human-facing — a one-line summary, trigger lists stripped.

**Three practical consequences.**

1. The `description:` string in a model-invoked skill's frontmatter *is* the
   trigger. `writing-for-agents/SKILL.md:12` calls it a **context pointer**:
   *"The pointer's _wording_, not its target, decides when the agent reaches the
   material — and how reliably."* The exact strings are in §4, because they are
   what you are matching against when you phrase a request.
2. **Fourteen of the twenty-five promoted skills can only be fired by you
   typing them.** Nothing in the chain will fire `/to-spec`, `/to-tickets`,
   `/implement`, `/wayfinder`, `/triage` or `/grill-with-docs` on your behalf.
   Every recipe in §6 that names one of those is an instruction to the human.
3. A user-invoked skill's `description` is not written to trigger anything, so
   asking for "a relentless interview to sharpen a plan" will not fire
   `/grill-me`. It may fire `grilling`, whose description *is* written to
   trigger.

### 2.2 Slash-command form and the plugin namespace

In Claude Code the skills are also reachable as slash commands. `docs/engineering/code-review.md`
records what the plugin install does to the names:

> Via the plugin marketplace, everything is aliased under a `mattpocock-skills:` prefix and the built-in becomes hard to reach at the unqualified name; via a plain skills install, the local file wins and this skill shadows the built-in.

That is confirmed by this session's own environment: the model-visible skill
listing names them `mattpocock-skills:tdd`, `mattpocock-skills:grilling`,
`mattpocock-skills:code-review`, and so on. The observation is first-hand rather
than documentary; it is flagged as such in §10.

**Observed in this session, and it matches the documented mechanism exactly:**
the model-visible listing contains **eleven** `mattpocock-skills:*` entries —
`diagnosing-bugs`, `tdd`, `prototype`, `research`, `domain-modeling`,
`codebase-design`, `code-review`, `resolving-merge-conflicts`, `wizard`,
`grilling`, `writing-for-agents` — which is precisely the model-invoked set
(9 engineering + 2 productivity). The fourteen user-invoked skills are absent
from the listing. They are installed; they are simply not shown to the model.

This is the mechanism behind a bug the router's docs page records:

> **It told me half the skills aren't installed.**
>
> A known bug, unfixed. Most of the skills the router routes you through set `disable-model-invocation: true`, which means the harness leaves them out of the skill list it injects into the agent's context. The agent reads that list as exhaustive and reports them missing. One reported session had it declare the whole spec-and-tickets flow absent and reroute to bare `/grilling` and `/tdd`. Thirteen of the plugin's twenty-two skills carry the flag, so this is the common case rather than an edge. They are installed. Type the slash command anyway, or check `.claude-plugin/plugin.json`, which is the authority on what is present.
>
> — `docs/engineering/ask-matt.md`

(The counts in that paragraph are stale against this install: `plugin.json` lists
25 skills, 14 of them user-invoked. The mechanism is unchanged.)

### 2.3 How one skill reaches another — the installed form

In the installed 1.2.3 tree, cross-skill dependencies are written as prose
naming a slash command. `.agents/invocation.md:16`:

> Dependencies are expressed as **`/skill`-style prose invocation** ("Run the `/grilling` skill"), not deep `../other-skill/FILE.md` cross-references. Shared reference docs live inside the skill that owns them; other skills reach that material by invoking the skill, not by linking across folders.

Two whole skills consist of nothing but that prose invocation. In full:

```
skills/productivity/grill-me/SKILL.md:7
Run a `/grilling` session.
```

```
skills/engineering/grill-with-docs/SKILL.md:7
Run a `/grilling` session, using the `/domain-modeling` skill.
```

This is the weakest joint in the whole set, and the repo's own docs say so:

> **`grill-with-docs` ran, but it never loaded `grilling`.**
>
> A real and unfixed rough edge, reported across [harnesses] and models: a skill that names another skill does not reliably cause that skill to load, and `grill-with-docs` names two. The tell is a session that asks everything at once with no recommendations attached — that is the model improvising an interview rather than running this one. Asking the agent directly whether it loaded `grilling` and `domain-modeling` usually recovers it.
>
> — `docs/productivity/grilling.md`

**Working practice, and this is synthesis:** when you type `/grill-with-docs`,
check the trace for `grilling` and `domain-modeling` actually loading, and name
them explicitly if they did not. The two quotes above are the support — the
skill is one line of prose delegation, and the delegation is documented as
unreliable.

### 2.4 Where the installed tree and the public repo disagree

The installed tree is 34 commits behind `mattpocock/skills@main`. Both report
version 1.2.3, so the version string will not tell you. Four of the differences
change how you should read this document.

| Difference | Installed 1.2.3 (`8b78b53`) | Public `main` (`3cca18b`) |
| --- | --- | --- |
| Cross-skill invocation | `` Run a `/grilling` session. `` | `Call the Skill tool with "grilling".` |
| Two skills at one step | `` Run a `/grilling` session, using the `/domain-modeling` skill. `` | `Call the Skill tool twice, for "grilling" and "domain-modeling".` |
| `setup` precondition | `` …should have been provided to you — run `/setup-matt-pocock-skills` if not. `` | `` …If not, tell the user to run `/setup-matt-pocock-skills`. `` |
| `diagnosing-bugs` Phase 6 | "Phase 6 — Cleanup + post-mortem", ending in a hand-off to `/improve-codebase-architecture` | "Phase 6: Cleanup" — the hand-off is **removed** |

The reasoning is in the unreleased changesets. On the invocation convention
(`.changeset/skill-tool-invocation-terminology.md`):

> A skill that names another skill in prose ("run the `/grilling` skill") does not reliably cause it to load. This is the documented rough edge behind `grill-with-docs`'s most-reported problem. Naming the tool directly (`Call the Skill tool with "grilling"`) is intended to raise the hit rate. Dropping the leading `/` also makes the instruction harness-neutral rather than less: it no longer assumes Claude Code's trigger syntax.

On the removed hand-off (`.changeset/user-invoked-skill-invocation.md`):

> `to-spec`, `wayfinder`, `to-tickets`, `triage`, and `code-review` each carried a precondition ("...run `/setup-matt-pocock-skills` if not") that PR #878 rewrote into a literal `Call the Skill tool with "setup-matt-pocock-skills"` instruction. `setup-matt-pocock-skills` is user-invoked, so none of these skills (user-invoked or model-invoked) can call it. Reworded all five as instructions for the agent to tell the human to run it instead.
>
> `diagnosing-bugs`'s Phase 6 post-mortem hand off to `improve-codebase-architecture` (also user-invoked) the same way, from an autonomous, often-unattended bug-fixing flow with no human in the loop to catch the failed call. Removed the hand-off outright rather than softening it, since it rarely fired in practice.

**The general rule this establishes, and it applies to the installed tree even
though the installed tree does not say it:** any instruction inside a skill that
tells the agent to run a *user-invoked* skill is an instruction the agent
cannot execute. It can only tell you. On `main` this is now written down, in
`.agents/invocation.md`:

> This whole convention only holds when the named skill is **model-invoked**. A user-invoked skill can never be reached this way, full stop: per the invariant above, no other skill can call it, including by naming it to the Skill tool. When a step's precondition is a user-invoked skill (e.g. `setup-matt-pocock-skills`), phrase it as an instruction for the human to act on: "tell the user to run `/setup-matt-pocock-skills`", never as a Skill tool call.

`main` also adds two in-progress skills the installed tree does not have
(`implement-spec`, `retro`) and has removed every em-dash from the prose, which
is why several `description` strings differ typographically between the two
trees. §4's table quotes the **installed** strings, since those are what this
harness is matching against.

---

## 3. Prerequisites: `/setup-matt-pocock-skills` and What It Writes

### 3.1 What it is for

`skills/engineering/setup-matt-pocock-skills/SKILL.md:9-15`:

> Scaffold the per-repo configuration that the engineering skills assume:
>
> - **Issue tracker** — where issues live (GitHub by default; local markdown is also supported out of the box)
> - **Triage labels** — the strings used for the five canonical triage roles
> - **Domain docs** — where `CONTEXT.md` and ADRs live, and the consumer rules for reading them
>
> This is a prompt-driven skill, not a deterministic script. Explore, present what you found, confirm with the user, then write.

Its frontmatter closes with the sequencing rule: *"Run once before first use of
the other engineering skills."* `ask-matt` repeats it under the heading
**Precondition** (`SKILL.md:90`):

> **`/setup-matt-pocock-skills`** — run before your first engineering flow to configure the issue tracker, triage labels, and doc layout the other skills assume. Custom issue trackers also work.

### 3.2 Hard versus soft dependency — what actually breaks if you skip it

`.agents/adr/0001-explicit-setup-pointer-only-for-hard-dependencies.md` is the
authoritative answer, and it is more precise than "everything breaks":

> We split these into **hard-dependency** and **soft-dependency** skills:
>
> - **Hard dependency** (`to-tickets`, `to-spec`, `triage`) — include an explicit one-liner: _"… should have been provided to you — run `/setup-matt-pocock-skills` if not."_ Without the mapping, output is wrong, not just fuzzy.
> - **Soft dependency** (`diagnose`, `tdd`, `improve-codebase-architecture`) — reference "the project's domain glossary" and "ADRs in the area you're touching" in vague prose only. If the docs aren't there, the skill still works; output is just less sharp.

In the shipped 1.2.3 tree the hard-dependency pointer appears in four more
places than that ADR lists — `code-review/SKILL.md:13`, `to-spec/SKILL.md:9`,
`to-tickets/SKILL.md:11` and `:60`, `triage/SKILL.md:43`, and
`wayfinder/SKILL.md:25`. `wayfinder` states the fallback explicitly:

> **Where the map, its child tickets, blocking, and frontier queries physically live is tracker-specific.** The issue tracker should have been provided to you — run `/setup-matt-pocock-skills` if not. Consult the tracker doc's "Wayfinding operations" section for how _this_ repo expresses them. If no tracker has been provided, default to the local-markdown tracker.

So the failure mode of skipping setup is not an error — it is a **silent wrong
default**. A repo with GitHub issues and no `docs/agents/issue-tracker.md` gets
markdown files in `.scratch/`.

### 3.3 The five steps

`setup-matt-pocock-skills/SKILL.md` runs a fixed process. Step 1, **Explore**,
reads `git remote -v`, `AGENTS.md`/`CLAUDE.md`, `CONTEXT.md`/`CONTEXT-MAP.md`,
`docs/adr/`, `docs/agents/`, `.scratch/`, whether the `triage` skill is
installed, and monorepo signals.

Step 2, **Present findings and ask**, is three sections, and the skill is
explicit that most of them should not be asked at all:

> Lead each section with the recommended answer so the user can accept it in a word. Give a one-line explainer only when the choice genuinely branches; skip the section entirely when exploration already settled it (Section B when `triage` isn't installed, Section C when there's no monorepo).

| Section | Decision | Options / default |
| --- | --- | --- |
| A | Issue tracker | GitHub (`gh`), GitLab (`glab`), Local markdown under `.scratch/`, or **Other** — *"ask the user to describe the workflow in one paragraph; the skill will record it as freeform prose"* |
| B | Triage labels | Skipped entirely if `triage` is not installed. Otherwise one question: *"Do you want to keep the default triage labels? (recommended: **yes**)"* |
| C | Domain docs | *"Default to **single-context** … This fits almost every repo; write it without asking."* Multi-context offered only on monorepo signals |

Step 3 is **Confirm and edit** — the drafts are shown before anything is
written. Step 4 is **Write**, and carries a rule worth quoting because it is the
documented source of a Codex failure:

> **Pick the file to edit:**
>
> - If `CLAUDE.md` exists, edit it.
> - Else if `AGENTS.md` exists, edit it.
> - If neither exists, ask the user which one to create — don't pick for them.
>
> Never create `AGENTS.md` when `CLAUDE.md` already exists (or vice versa) — always edit the one that's already there.

The docs page notes the consequence: *"The file-selection rule is 'edit
`CLAUDE.md` if it exists, else `AGENTS.md`' — it checks which file exists, not
which [harness] is running. A repo with a `CLAUDE.md` left over from Claude Code
will get its `## Agent skills` block somewhere Codex never reads."*

### 3.4 What it writes

Four artifacts. The block injected into `CLAUDE.md`/`AGENTS.md`
(`SKILL.md:86-100`), verbatim:

```markdown
## Agent skills

### Issue tracker

[one-line summary of where issues are tracked]. See `docs/agents/issue-tracker.md`.

### Triage labels

[one-line summary of the label vocabulary]. See `docs/agents/triage-labels.md`.

### Domain docs

[one-line summary of layout — "single-context" or "multi-context"]. See `docs/agents/domain.md`.
```

That block is the **indirection layer**, and it is load-bearing. The CHANGELOG
records what happened when one skill bypassed it:

> `to-issues`, `to-prd`, and `triage` never name a path — they resolve the tracker through the `### Issue tracker` block that `setup-matt-pocock-skills` writes into `CLAUDE.md` / `AGENTS.md`, which points at the tracker doc wherever it lives. Wayfinder instead pinned the literal `docs/agents/issue-tracker.md`, so in a repo that keeps its agent docs elsewhere it silently fell back to the local-markdown tracker — even one whose `CLAUDE.md` clearly declares GitHub issues.
>
> — `CHANGELOG.md`, 1.1.0 patch notes, PR #472

The three files under `docs/agents/`:

| File | Written from | Carries |
| --- | --- | --- |
| `issue-tracker.md` | `issue-tracker-{github,gitlab,local}.md`, or written from scratch for "other" | CLI conventions, a "PRs as a request surface" flag defaulted **off**, what *"publish to the issue tracker"* and *"fetch the relevant ticket"* mean here, and a **Wayfinding operations** section |
| `triage-labels.md` | `triage-labels.md` | A two-column identity table mapping the five canonical roles to this tracker's label strings. Only written when `triage` is installed |
| `domain.md` | `domain.md` | Where `CONTEXT.md` and ADRs live, the instruction to read them before exploring, and the rule to flag ADR conflicts |

`domain.md` carries one instruction that explains why a freshly-set-up repo is
supposed to look empty:

> If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

### 3.5 A worked example: this repository

`/home/qas/Documents/me/researcher` is a repo that has been through setup. Its
`CLAUDE.md` carries the block, compressed to the same three sub-headings:

> ### Issue tracker
>
> Issues live as GitHub issues in `AymanKastali/researcher`, driven by the `gh` CLI. See `docs/agents/issue-tracker.md`.
>
> ### Triage labels
>
> The five canonical triage roles, each label named after itself. See `docs/agents/triage-labels.md`.
>
> ### Domain docs
>
> Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

`/home/qas/Documents/me/researcher/docs/agents/issue-tracker.md` is the GitHub
seed template, essentially unedited, including the flag left at its default:

> **PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

`/home/qas/Documents/me/researcher/docs/agents/triage-labels.md` is the identity
table — every canonical role mapped to itself — which is the intended common
case rather than an unfinished step:

> If your tracker already uses the canonical names, the mapping is an identity table and there is nothing to configure. That is the intended common case, not a missing step.
>
> — `docs/engineering/setup-matt-pocock-skills.md`

`/home/qas/Documents/me/researcher/docs/agents/domain.md` is the seed template
with the single-context choice written in: *"This repo is **single-context**:
one `CONTEXT.md` and one `docs/adr/` at the root."*

The two files setup does **not** create are present as well, because they are
created lazily by `/domain-modeling`: `CONTEXT.md` at the root (a glossary of
this repo's own terms — *Topic*, *Lesson*, *Primary source*, each with an
`_Avoid_` list, exactly the `CONTEXT-FORMAT.md` shape) and
`docs/adr/0001-shared-stylesheet-across-independent-topics.md`.

That ADR is a good check on the three-gate rule in §6.4, because it passes all
three visibly: it is hard to reverse (*"Every page hard-codes its depth to the
root … This is what makes the decision hard to reverse — it is written into
every page ever produced"*), surprising without context (it **contradicts** what
`/teach` specifies, putting assets at the repo root rather than inside each
workspace), and the result of a real trade-off (it carries a **Considered
options** section with two rejected alternatives).

### 3.6 What setup does *not* do

Three limits, each documented, and each a thing you have to do by hand:

- **It does not create labels.** *"`docs/agents/triage-labels.md` is a *mapping*
  … It does not run `gh label create`. On a fresh GitHub repo the labels
  genuinely do not exist yet, and this has been filed as a bug more than once."*
  And specifically for §6.5: *"[wayfinder]'s `wayfinder:map` and
  `wayfinder:<type>` labels are not created here either, and `gh issue create
  --label <missing>` fails outright rather than creating the label. Create them
  by hand before the first wayfinder run on a GitHub repo."*
  (`docs/engineering/setup-matt-pocock-skills.md`)
- **It does not hold your preferences.** *"It configures three things: tracker,
  labels, doc layout. There have been direct requests to make it the home for
  per-user preferences, and the standing answer is that skills stay opinionated:
  'Config is death.' Preferences belong in your `CLAUDE.md` as plain
  instructions."* (same page)
- **There is no user-level mode.** *"Not today. There is an open request for
  exactly this from someone running the skills across many repos, and no
  user-level mode exists. Every repo carries its own `docs/agents/`."* (same
  page)

There is also no verify mode, and that is a deliberate refusal recorded in the
repo's own out-of-scope knowledge base
(`.out-of-scope/setup-skill-verify-mode.md`):

> The intended workflow is: **run `/setup-matt-pocock-skills` and tell it to verify your current setup.** The skill is prompt-driven, so the maintainer can scope it to a verification pass ("don't rewrite anything, just check my existing files against the current seed templates and report drift") without needing a separate code path.

---

## 4. Skill Inventory

`description` strings are quoted **verbatim** from the installed
`SKILL.md` frontmatter, because that string is the trigger (§2.1). "Sub-agents"
records whether the skill's own body instructs it to dispatch them.

### 4.1 Engineering — user-invoked (9)

These can only be fired by you typing them.

| Skill | `description:` (verbatim) | Sub-agents | Supporting files |
| --- | --- | --- | --- |
| `ask-matt` | Ask which skill or flow fits your situation. A router over the skills in this repo. | no | `PHASE-BOUNDARIES.md` |
| `grill-with-docs` | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. | via `grilling` | none — the body is one line |
| `triage` | Move issues and external PRs through a state machine of triage roles — categorise, verify, grill if needed, and write agent-ready briefs. | via `grilling` | `AGENT-BRIEF.md`, `OUT-OF-SCOPE.md` |
| `improve-codebase-architecture` | Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick. | **yes** — *"spawn a sub-agent to walk the codebase"* | `HTML-REPORT.md` |
| `setup-matt-pocock-skills` | Configure this repo for the engineering skills — set up its issue tracker, triage label vocabulary, and domain doc layout. Run once before first use of the other engineering skills. | no | `domain.md`, `triage-labels.md`, `issue-tracker-github.md`, `issue-tracker-gitlab.md`, `issue-tracker-local.md` |
| `to-spec` | Turn the current conversation into a spec and publish it to the project issue tracker — no interview, just synthesis of what you've already discussed. | no | none (inline `<spec-template>`) |
| `to-tickets` | Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published to the configured tracker — edges as text in one file per ticket locally, or native blocking links on a real tracker. | no | none (inline templates) |
| `implement` | Implement a piece of work based on a spec or set of tickets. | no | none — the body is 9 lines |
| `wayfinder` | Plan a huge chunk of work — more than one agent session can hold — as a shared map of decision tickets on your issue tracker, and resolve them one at a time until the way to the destination is clear. | **yes** — fires a `/research` subagent per research ticket | none; reads the tracker doc's "Wayfinding operations" |

### 4.2 Engineering — model-invoked (9)

These the agent can reach for on its own, and other skills can reach.

| Skill | `description:` (verbatim) | Sub-agents | Supporting files |
| --- | --- | --- | --- |
| `prototype` | Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic feels right, or explore what a UI should look like. | no | `UI.md`, `LOGIC.md` |
| `diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow. | no | `scripts/hitl-loop.template.sh` |
| `research` | Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent. | **yes** — *"Spin up a **background agent** to do the research"* | none — the body is one line plus three numbered steps |
| `tdd` | Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests. | no | `tests.md`, `mocking.md` |
| `domain-modeling` | Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a CONTEXT.md, or recording or editing an ADR. | no | `CONTEXT-FORMAT.md`, `ADR-FORMAT.md` |
| `codebase-design` | Shared vocabulary for designing deep modules. Use when the user wants to design or improve a module's interface, find deepening opportunities, decide where a seam goes, make code more testable or AI-navigable, or when another skill needs the deep-module vocabulary. | **yes**, in `DESIGN-IT-TWICE.md` — *"Spawn 3+ sub-agents in parallel"* | `DEEPENING.md`, `DESIGN-IT-TWICE.md` |
| `code-review` | Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to "review since X". | **yes** — two, in parallel | none |
| `resolving-merge-conflicts` | Use when you need to resolve an in-progress git merge/rebase conflict. | no | none — the body is 5 steps |
| `wizard` | Generate an interactive bash wizard that walks a human through steps only they can perform. Use when provisioning infrastructure, setting up credentials or CI secrets, walking an unfamiliar third-party dashboard, or running a one-off migration or cutover. Don't invoke this for steps the agent can perform itself. | no | `template.sh` (204 lines) |

### 4.3 Productivity (7)

| Skill | Invocation | `description:` (verbatim) | Supporting files |
| --- | --- | --- | --- |
| `grill-me` | user | A relentless interview to sharpen a plan or design. | none — the body is one line |
| `handoff` | user | Compact the current conversation into a handoff document for another agent to pick up. | none; `argument-hint: "What will the next session be used for?"` |
| `teach` | user | Teach the user a new skill or concept, within this workspace. | `MISSION-FORMAT.md`, `RESOURCES-FORMAT.md`, `GLOSSARY-FORMAT.md`, `LEARNING-RECORD-FORMAT.md` |
| `to-questionnaire` | user | Turn a decision you can't fully answer into a questionnaire for someone else to fill in. | none (inline template) |
| `wait-what` | user | Stop. That last message did not land — re-pitch it. | none — the body is one sentence |
| `grilling` | **model** | Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases. | none |
| `writing-for-agents` | **model** | Writing documents for agents. Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md. | `SKILL-MECHANICS.md` |

One documented gap in `teach`: *"the skill ships a `GLOSSARY-FORMAT.md` that
`SKILL.md` no longer links to, so you will only get one if you ask ([issue
#559])"* (`docs/productivity/teach.md`). Verified against the installed tree —
`teach/SKILL.md` links `MISSION-FORMAT.md`, `RESOURCES-FORMAT.md` and
`LEARNING-RECORD-FORMAT.md`, and never mentions `GLOSSARY-FORMAT.md`.

### 4.4 Not in the plugin — do not plan around these

**`misc/` (4).** *"Tools I keep around but rarely use — not promoted in the
plugin."* `git-guardrails-claude-code` (PreToolUse hook blocking `git push`,
`reset --hard`, etc.), `migrate-to-shoehorn`, `scaffold-exercises`,
`setup-pre-commit`.

**`in-progress/` (6).** Beta channel, installable one at a time through
skills.sh only. `claude-handoff` (launches a background agent with
`claude --bg` instead of writing a file), `loop-me`, `setup-ts-deep-modules`
(wires dependency-cruiser so each package is a deep module — repeatedly asked
for in `codebase-design`'s docs page, and *"it is a beta-channel skill with no
docs page, and it has no lint rule shipped with it"*), `writing-beats`,
`writing-fragments`, `writing-shape`.

**`deprecated/` (0).** Empty by policy.

### 4.5 Retired and renamed names

Collected from `CHANGELOG.md`, because they still circulate and a stale prompt
that names one now fires nothing.

| Old name | Status |
| --- | --- |
| `/diagnose` | → `/diagnosing-bugs` (1.0.0). *"the old `/diagnose` name no longer exists"* |
| `to-prd` | → `to-spec` (1.1.0). *"'spec' is now the only term in the shipped text"* |
| `decision-mapping` | → `wayfinder` (1.1.0) |
| `writing-great-skills` | → `writing-for-agents` (1.2.0). *"Reinstall under the new name; the old name is gone (no alias)"* |
| `to-plan`, `to-issues` | merged into `to-tickets` (1.1.0) |
| `review` | → `code-review`, promoted out of `in-progress/` (1.1.0) |
| `ubiquitous-language` | removed → absorbed by `/domain-modeling` |
| `design-an-interface` | removed → absorbed by `/codebase-design` (ships as `DESIGN-IT-TWICE.md`) |
| `qa` | removed → absorbed by `/triage` and `/to-tickets` |
| `request-refactor-plan` | removed → absorbed by `/to-spec` and `/improve-codebase-architecture` |
| `caveman`, `zoom-out`, `write-a-skill`, `edit-article`, `obsidian-vault`, `batch-grill-me` | removed |

---

## 5. The Handoff Map

This is the evidence for how the skills chain: every explicit cross-reference
between installed `SKILL.md` files and their supporting documents, found by
grepping for skill names across `skills/**/*.md`. Router prose in `ask-matt`
(which names almost everything, by design) is excluded from the count and
treated separately.

### 5.1 Who names whom

| Caller | Names | Where | Nature |
| --- | --- | --- | --- |
| `grill-me` | `grilling` | `SKILL.md:7` | the whole body |
| `grill-with-docs` | `grilling`, `domain-modeling` | `SKILL.md:7` | the whole body |
| `implement` | `tdd`, `code-review` | `SKILL.md:9`, `:13` | *"Use /tdd where possible, at pre-agreed seams"* / *"Once done, use /code-review to review the work"* |
| `tdd` | `codebase-design` | `SKILL.md:26` | vocabulary reference, explicitly **not** a session |
| `triage` | `grilling`, `domain-modeling` | `SKILL.md:76` | *"run the `/grilling` and `/domain-modeling` skills together"* |
| `triage` | `setup-matt-pocock-skills` | `SKILL.md:43` | precondition |
| `wayfinder` | `grilling`, `domain-modeling` | `SKILL.md:111`, `:124` | both invocation modes |
| `wayfinder` | `research` | `SKILL.md:77`, `:115` | subagent per research ticket |
| `wayfinder` | `prototype` | `SKILL.md:78` | one of four ticket types |
| `wayfinder` | `setup-matt-pocock-skills` | `SKILL.md:25` | precondition |
| `improve-codebase-architecture` | `codebase-design` | `SKILL.md:13`, `:54`, `:71`; `HTML-REPORT.md:42`, `:108`, `:123` | vocabulary, enforced verbatim |
| `improve-codebase-architecture` | `grilling` | `SKILL.md:64` | step 3 |
| `improve-codebase-architecture` | `domain-modeling` | `SKILL.md:66` | inline during step 3 |
| `diagnosing-bugs` | `improve-codebase-architecture` | `SKILL.md:140` | post-mortem hand-off — **removed on `main`**, see §2.4 |
| `code-review` | `setup-matt-pocock-skills` | `SKILL.md:13` | precondition |
| `to-spec` | `setup-matt-pocock-skills` | `SKILL.md:9` | precondition |
| `to-tickets` | `setup-matt-pocock-skills` | `SKILL.md:11`, `:60` | precondition |
| `codebase-design` | `DEEPENING.md`, `DESIGN-IT-TWICE.md` | `SKILL.md:113-114` | disclosed reference |
| `prototype` | `UI.md`, `LOGIC.md` | `SKILL.md:14-15` | branch |
| `setup-matt-pocock-skills` (`domain.md`) | `domain-modeling` | `domain.md:11`, `:45` | names `/grill-with-docs` and `/improve-codebase-architecture` as its routes |
| tracker templates | `wayfinder`, `triage` | `issue-tracker-*.md` | the "Wayfinding operations" section, the PR flag |

### 5.2 What the map shows

Five facts fall out of that table, and they are what the recipes in §6 are built
on.

1. **`grilling` is the hub.** Five skills reach it: `grill-me`,
   `grill-with-docs`, `triage`, `wayfinder`, `improve-codebase-architecture`.
   `ask-matt:78` says so: *"`/grill-me` and `/grill-with-docs` are the two named
   ways in, and `/triage`, `/wayfinder` and `/improve-codebase-architecture` all
   run it internally."*
2. **`domain-modeling` always travels with `grilling`.** Four of the five
   `grilling` call sites name it in the same breath.
3. **`implement` is the only skill that drives the build loop**, and it drives
   exactly two others: `tdd` and `code-review`.
4. **`codebase-design` is consumed, never driven.** `tdd:26` states it as a
   rule: *"it is a reference to consult, not a session to run."*
5. **Every cross-reference to a user-invoked skill is broken by construction**
   (§2.4). In 1.2.3 there are seven such references: five `setup-matt-pocock-skills`
   preconditions and the `diagnosing-bugs` → `improve-codebase-architecture`
   hand-off. Read every one of them as a message to you, not an instruction to
   the agent.

### 5.3 The one canonical chain

The chain appears identically in four independent places. `ask-matt`'s main flow
(`SKILL.md:13-26`), the engineering `README.md:16`, and the docs pages for
`to-spec`, `to-tickets`, `implement`, `tdd` and `code-review`, each of which
prints it as a literal code block:

```txt
grill-with-docs → to-spec → to-tickets → implement → code-review
```

Everything else in the set is an on-ramp onto that chain, a standalone off it,
or a vocabulary layer under it.

---

## 6. The Five Workflows

Each recipe below is an ordered list of steps. The **skills named** and the
**instructions quoted** are primary-source. The **ordering** is drawn from
`ask-matt/SKILL.md`, which is the repo's own router; where I have gone beyond it
— adding a step it does not name, or resolving an ambiguity it leaves open —
the step says **[synthesis]** and names the quotes it rests on.

One rule applies to all five, from `ask-matt:90`: **run
`/setup-matt-pocock-skills` once in the repo first.** Recipes 1 and 4 degrade
gracefully without it (§3.2); recipes 2, 3 and 5 do not.

### 6.1 Workflow 1 — Develop a Small Feature

"Small" has a definition in this set, and it is not about lines of code. It is
**whether the work fits one context window**. `docs/engineering/to-spec.md`:

| Where you are | What to run |
| --- | --- |
| Decided, and the work fits one [context window] | [implement] — skip the spec |
| Decided, and the work spans several sessions | `/to-spec`, then [to-tickets] |

`ask-matt:24` puts the same branch as the second half of step 3 of the main
flow: *"**No** → **`/implement`** right here, in the same context window."*

**Step 1 — `/grill-with-docs`.** From `ask-matt:17`:

> **`/grill-with-docs`** — sharpen the idea by interview. Start here whenever you are **working in a working directory**: it's stateful, retaining what it learns in `CONTEXT.md` and ADRs. (No working directory? Use `/grill-me` […] Both run the same `/grilling` primitive; `grill-with-docs` is the one that leaves a paper trail, which makes it the better of the two whenever a repo is there to leave it in.)

Artifacts: terms appended to `CONTEXT.md` inline as they resolve, and an ADR
under `docs/adr/` only if a decision clears all three gates (§6.4). Most small
features produce zero ADRs, and that is correct.

**Step 2 — do not clear.** `ask-matt:30`, under **Context hygiene**:

> Keep steps 1–3 in **one unbroken context window** — don't compact or clear until after `/to-tickets` — so the grilling, spec, and tickets all build on the same thinking.

For a small feature there is no `/to-tickets`, so this collapses to: go straight
from the grilling into the build in the same window. `PHASE-BOUNDARIES.md:21`
gives the reason in general form:

> **1. Can you continue in this session?** Two things make the answer yes: the next phase needs this phase as a **primary source**, or you have enough [smart zone] left (~150k tokens) for the next phase to fit. Grilling → implementation is the standard yes: the implementation wants the reasoning verbatim, not a summary of it. Continue costs nothing and loses nothing, so rule it out before anything else.

**Step 3 — check your branch. [synthesis]** `implement/SKILL.md:15` is
*"Commit your work to the current branch"*, and the skill has no step that
creates one. `docs/engineering/implement.md` states the consequence: *"It does
not create one, and it does not ask. Check you are on the branch you want the
work on before you start."* This is the step where superpowers fills a gap —
see §8.

**Step 4 — `/implement`.** The whole skill, verbatim
(`implement/SKILL.md:7-15`):

> Implement the work described by the user in the spec or tickets.
>
> Use /tdd where possible, at pre-agreed seams.
>
> Run typechecking regularly, single test files regularly, and the full test suite once at the end.
>
> Once done, use /code-review to review the work.
>
> Commit your work to the current branch.

Because the body says *"the spec or tickets"*, say explicitly that the plan is
in the thread. The docs page names this: *"`SKILL.md` says 'the spec or
tickets', which nudges the [model] to go hunting for a file that doesn't exist.
If the plan lives only in the thread, say so when you invoke it."*

**Step 5 — the `/tdd` seam gate fires inside step 4.** This is the one place
`implement` will stop and wait for you. `tdd/SKILL.md:22-24`:

> **Test only at pre-agreed seams.** Before writing any test, write down the seams under test and confirm them with the user. No test is written at an unconfirmed seam. You can't test everything — agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.
>
> Ask: "What's the public interface, and which seams should we test?"

The loop itself is short (`tdd/SKILL.md:36-38`):

> - **Red before green.** Write the failing test first, then only enough code to pass it. Don't anticipate future tests or add speculative features.
> - **One slice at a time.** One seam, one test, one minimal implementation per cycle.
> - **Refactoring is not part of the loop.** It belongs to the review stage (see the `code-review` skill), not the red → green implementation cycle.

**Step 6 — `/code-review`, and commit first. [synthesis]** `implement` runs
`/code-review` *before* committing, and `code-review` reviews only committed
work. `code-review/SKILL.md:21`:

> Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base).

`docs/engineering/implement.md` spells out the collision:

> `code-review` reviews `git diff <fixed-point>...HEAD`, which excludes staged and working-tree changes. `implement` runs it before committing, so unless an interim commit already exists there is nothing in that diff to review. Multiple people have reported this and it is unfixed on both sides. Commit first, then review against the point you branched from.

So the working order is: let `implement` build and commit, then invoke
`/code-review` yourself against the branch point. The same page gives a second
reason to do it separately: *"an agent reviewing the code it just wrote is
biased toward its own solution. Running [code-review] in a fresh session against
a fixed point is a legitimate alternative, and is the same reason that skill
runs its two axes in separate sub-agents."*

What `/code-review` does, in order (`code-review/SKILL.md`): pin the fixed point
and fail fast on a bad ref or empty diff; find the spec (commit-message issue
refs → a path you passed → a file under `docs/`, `specs/` or `.scratch/` → ask
you); collect standards sources plus the twelve-smell Fowler baseline; spawn two
sub-agents in parallel; aggregate. The aggregation rule is a hard one
(`SKILL.md:76-78`):

> Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the two axes are deliberately separate […]
>
> End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

**The summary chain.**

```
/setup-matt-pocock-skills (once)
  → /grill-with-docs        [CONTEXT.md terms, maybe an ADR]
  → (stay in the window; branch check)
  → /implement              [drives /tdd at confirmed seams → commit]
  → /code-review <branch-point>   [two-axis report]
```

### 6.2 Workflow 2 — Fix a Bug

There are two entry points, and which one you take depends on **who filed the
bug**. `ask-matt:38-42`:

> - **Bugs and requests piling up** → **`/triage`**. It moves issues through triage roles and produces agent-ready issues, which **`/implement`** later picks up.
>
>   Triage is only for issues **you didn't create** — bug reports, incoming feature requests, anything that arrives raw. Tickets that `/to-tickets` produced are already agent-ready, so **don't triage them**.
>
> - **Something's broken** → **`/diagnosing-bugs`**. For the hard ones: the bug that resists a first glance, the intermittent flake, the regression that crept in between two known-good states. It refuses to theorise until it has a **tight feedback loop** — one command that already goes red on *this* bug — then fixes with a regression test.

**Step 0 (only if the bug arrived from someone else) — `/triage`.** The relevant
step is step 3 of the triage process (`triage/SKILL.md:74`):

> 3. **Verify the claim.** Before any grilling, check that the claim holds up. For a bug, reproduce it from the reporter's steps. […] Report what happened: confirmed (with code path), failed, or insufficient detail (a strong `needs-info` signal). A confirmed verification makes a much stronger agent brief.

Triage ends by applying a state role and, for `ready-for-agent`, posting an
agent brief. The brief's rules are the durable ones
(`triage/AGENT-BRIEF.md:11-17`):

> The issue may sit in `ready-for-agent` for days or weeks. The codebase will change in the meantime. Write the brief so it stays useful even as files are renamed, moved, or refactored.
>
> - **Do** describe interfaces, types, and behavioral contracts
> - **Do** name specific types, function signatures, or config shapes that the agent should look for or modify
> - **Don't** reference file paths — they go stale
> - **Don't** reference line numbers
> - **Don't** assume the current implementation structure will remain the same

Also note the disclaimer rule (`triage/SKILL.md:13`): *"Every comment or issue
posted to the issue tracker during triage **must** start with this disclaimer:
`> *This was generated by AI during triage.*`"*

Triage's verification is deliberately shallow, and overlaps Phase 1–2 of the
next skill. The docs page is candid: *"Triage's step 3 is essentially a shallow,
bounded instance of diagnosing-bugs Phase 1–2, but neither file mentions the
other."* Expect to redo it properly.

**Step 1 — `/diagnosing-bugs`, Phase 1: build a feedback loop.** This is the
skill. `diagnosing-bugs/SKILL.md:20-22`:

> **This is the skill.** Everything else is mechanical. If you have a **tight** pass/fail signal for the bug — one that goes red on _this_ bug — you will find the cause; bisection, hypothesis-testing, and instrumentation all just consume it. If you don't have one, no amount of staring at code will save you.
>
> Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to give up.**

Ten ways to construct one are listed *"in roughly this order"*: failing test,
curl/HTTP script, CLI with fixture diffed against a snapshot, headless browser
script, replayed trace, throwaway harness, property/fuzz loop, bisection harness
for `git bisect run`, differential loop, and last of all a HITL bash script
driven by the shipped `scripts/hitl-loop.template.sh`.

Then tighten it (`SKILL.md:41-47`):

> Treat the loop as a product. Once you have _a_ loop, **tighten** it:
>
> - Can I make it faster? (Cache setup, skip unrelated init, narrow the test scope.)
> - Can I make the signal sharper? (Assert on the specific symptom, not "didn't crash".)
> - Can I make it more deterministic? (Pin time, seed RNG, isolate filesystem, freeze network.)
>
> A 30-second flaky loop is barely better than no loop; a 2-second deterministic one is tight — a debugging superpower.

For flakes, the target is not a clean repro: *"The goal is not a clean repro but
a **higher reproduction rate**. […] A 50%-flake bug is debuggable; 1% is not —
keep raising the rate until it's debuggable."*

The phase boundary is a hard gate (`SKILL.md:58-66`):

> Phase 1 is done when the loop is **tight** and **red-capable**: you can name **one command** — a script path, a test invocation, a curl — that you have **already run at least once** (show the invocation and its output, redacted), and that is:
>
> - [ ] **Red-capable** — it drives the actual bug code path and asserts the **user's exact symptom** […]
> - [ ] **Deterministic** — same verdict every run […]
> - [ ] **Fast** — seconds, not minutes.
> - [ ] **Agent-runnable** — you can run it unattended […]
>
> If you catch yourself reading code to build a theory before this command exists, **stop — jumping straight to a hypothesis is the exact failure this skill prevents.** No red-capable command, no Phase 2.

And when no loop is possible (`SKILL.md:55`):

> Stop and say so explicitly. List what you tried. Ask the user for: (a) access to whatever environment reproduces it, (b) a redacted captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Do **not** proceed to hypothesise without a loop.

Redaction is a first-class instruction in 1.2.3 (`SKILL.md:14`, added by PR #779):

> This skill has you show commands, outputs and captured artifacts. **Redact every secret first** — write `<REDACTED>` in its place. Build loops against env vars, so the credential stays in the environment rather than in what you show. Captured artifacts carry auth headers: quote only the lines that carry the signal.

**Step 2 — Phase 2: reproduce and minimise.** The gate: *"The loop produces the
failure mode the **user** described — not a different failure that happens to be
nearby. Wrong bug = wrong fix."* Then:

> Once it's red, shrink the repro to the **smallest scenario that still goes red**. Cut inputs, callers, config, data, and steps **one at a time**, re-running the loop after each cut […]
>
> Done when **every remaining element is load-bearing** — removing any one of them makes the loop go green.
>
> Do not proceed until you have reproduced **and** minimised.

**Step 3 — Phase 3: hypothesise, and show the list.**

> Generate **3–5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.
>
> Each hypothesis must be **falsifiable**: state the prediction it makes.
>
> > Format: "If \<X\> is the cause, then \<changing Y\> will make the bug disappear / \<changing Z\> will make it worse."
>
> If you cannot state the prediction, the hypothesis is a vibe — discard or sharpen it.
>
> **Show the ranked list to the user before testing.** […] Don't block on it — proceed with your ranking if the user is AFK.

This is the **only human checkpoint in the skill**, which is worth knowing
before you walk away.

**Step 4 — Phase 4: instrument.** One variable at a time; debugger over logs;
*"Never 'log everything and grep'."* And the cleanup mechanism:

> **Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single grep. Untagged logs survive; tagged logs die.

Performance regressions branch here: *"For performance regressions, logs are
usually wrong. Instead: establish a baseline measurement (timing harness,
`performance.now()`, profiler, query plan), then bisect. Measure first, fix
second."*

**Step 5 — Phase 5: fix, with the regression test first — if there is a seam.**

> Write the regression test **before the fix** — but only if there is a **correct seam** for it.
>
> A correct seam is one where the test exercises the **real bug pattern** as it occurs at the call site. If the only available seam is too shallow […] a regression test there gives false confidence.
>
> **If no correct seam exists, that itself is the finding.** Note it. The codebase architecture is preventing the bug from being locked down.

Then the five sub-steps: turn the minimised repro into a failing test, watch it
fail, apply the fix, watch it pass, re-run the Phase 1 loop against the original
un-minimised scenario.

**Step 6 — Phase 6: cleanup and post-mortem.** A five-item checklist, ending
with *"The hypothesis that turned out correct is stated in the commit / PR
message — so the next debugger learns"*. Then:

> **Then ask: what would have prevented this bug?** If the answer involves architectural change (no good test seam, tangled callers, hidden coupling) hand off to the `/improve-codebase-architecture` skill with the specifics. Make the recommendation **after** the fix is in, not before — you have more information now than when you started.

**Read that hand-off as a note to yourself, not an instruction to the agent.**
`/improve-codebase-architecture` is user-invoked, so nothing can fire it; and on
`main` the hand-off has been deleted for exactly this reason (§2.4).

**Step 7 — `/code-review`. [synthesis]** `diagnosing-bugs` has no review step
and no commit step. `code-review`'s trigger covers it —
*"Use when the user wants to review a branch, a PR, work-in-progress changes, or
asks to 'review since X'"* — and the Spec axis will report *"no spec available"*
if there is no originating issue, which is a legitimate outcome rather than a
failure (`code-review/SKILL.md:32`).

**The summary chain.**

```
(bug arrived from someone else?) → /triage   [verify → agent brief → ready-for-agent]
  → /diagnosing-bugs
      Phase 1 tight red loop   ← hard gate, no theory before this
      Phase 2 reproduce + minimise
      Phase 3 3–5 ranked falsifiable hypotheses  ← the only checkpoint
      Phase 4 instrument, [DEBUG-xxxx] tags
      Phase 5 regression test first, if a correct seam exists
      Phase 6 cleanup; note the architectural finding
  → (you) /improve-codebase-architecture, if the finding was "no seam"
  → /code-review <fixed-point>
```

**One known over-firing risk.** `diagnosing-bugs` is model-invoked, and the docs
page records the most-reported problem with it:

> This is the most-reported problem with the skill, and it is real. On GPT-5.6-Sol especially, users report it triggering on a plain description of a problem […] Until it is graduated, the practical fix is to say what you want ("just answer this, don't diagnose") or to disable model invocation for it in your [harness].

### 6.3 Workflow 3 — Develop a Big / Multi-Part Feature

The trigger for this recipe rather than §6.1 is the same one: the build spans
more than one context window. `ask-matt:23`:

> - **Yes** → **`/to-spec`** (turn the thread into a spec), then **`/to-tickets`** to split it into tracer-bullet tickets, each declaring its **blocking edges**. On a local tracker that's one file per ticket under `.scratch/<feature>/issues/`, worked blockers-first by hand; on a real tracker the edges become native blocking links, so any ticket whose blockers are done can be grabbed — kick off **`/implement`** per ticket, **`/clear`ing context between each one**. Each ticket is self-contained, so the last one's context is disposable.

**Step 1 — `/grill-with-docs`**, as in §6.1.

**Step 2 — `/to-spec`, in the same window.** The skill's defining constraint is
the first line (`to-spec/SKILL.md:7`):

> This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user — just synthesize what you already know.

Its three process steps, in order: explore the repo using the domain glossary
and respecting ADRs; **sketch the seams and check them with you**; write and
publish. Step 2 is the one that matters most downstream (`to-spec/SKILL.md:15-17`):

> 2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.
>
> Check with the user that these seams match their expectations.

That is where `tdd`'s "pre-agreed seam" precondition is actually satisfied in
the full chain, rather than in the first exchange of each `/implement` run.

The spec template's section list is fixed: **Problem Statement**, **Solution**,
**User Stories** (*"A LONG, numbered list"*, *"extremely extensive"*),
**Implementation Decisions**, **Testing Decisions**, **Out of Scope**,
**Further Notes**. Two constraints on its content:

> Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.
>
> Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype.

And the publish instruction (`SKILL.md:19`): *"publish it to the project issue
tracker. Apply the `ready-for-agent` triage label - no need for additional
triage."* The docs page flags the sharp edge that creates: an AFK runner polling
for `ready-for-agent` will try to build the whole spec. *"Until it changes,
exclude the parent spec explicitly in your AFK agent's prompt, or strip the
label once `/to-tickets` has run."*

**Step 3 — `/to-tickets`, still in the same window.** Both docs pages give the
same reason not to clear: a very large spec can outgrow what a tracker issue
serves back cleanly, and *"there is no local copy to fall back on"*. Run them in
one window and the spec is never re-fetched.

The drafting rules (`to-tickets/SKILL.md:29-36`):

> - Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests) — vertical, NOT a horizontal slice of one layer
> - A completed slice is demoable or verifiable on its own
> - Each slice is sized to fit in a single fresh context window
> - Any prefactoring should be done first

Prefactoring is looked for in step 2: *"Look for opportunities to prefactor the
code to make the implementation easier. 'Make the change easy, then make the
easy change.'"*

The **wide-refactor exception** is the one shape that breaks vertical slicing
(`SKILL.md:40`):

> A **wide refactor** is one mechanical change — rename a column, retype a shared symbol — whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch.

Step 4 is a **quiz you are expected to push back in** (`SKILL.md:50-56`):

> Ask the user:
>
> - Does the granularity feel right? (too coarse / too fine)
> - Are the blocking edges correct — does each ticket only depend on tickets that genuinely gate it?
> - Should any tickets be merged or split further?
>
> Iterate until the user approves the breakdown.

This is where the two most-reported failures get caught. The docs page's test for
a horizontal slice is one question: *"Catch it at the quiz step by asking one
question per ticket: what can I demo when this is done? A ticket with no answer
is a horizontal slice."*

Step 5 publishes, in dependency order, blockers first, and ends with two rules:
*"Work the **frontier**: any ticket whose blockers are all done"* and *"Do NOT
close or modify any parent issue."*

**Step 4 — `/clear`, then `/implement` once per ticket.** From `ask-matt:30`:
*"Each `/implement` then starts fresh, working from the ticket."* One ticket per
invocation is not a suggestion — `docs/engineering/implement.md`:

> No. One invocation, one ticket. Batch dispatch across a ticket queue and [subagent] fan-out are both requested repeatedly, and neither exists. Running several `/implement` sessions side by side in one checkout is worse than unsupported: one field report describes a `git commit --amend` in one session landing on another session's commit, a stash vanishing from `refs/stash`, and commits landing on the wrong branch […] Git worktrees are the community workaround.

**Step 5 — `/code-review` per ticket, and once at the branch point. [synthesis]**
`code-review`'s docs page declines to decide and gives both: *"Per-ticket keeps
each diff small enough that the Spec axis has one clear spec to check against,
which is the mode `implement` uses. Batching to the end of a branch catches
interactions between tickets that the per-ticket passes each miss. If you are
unsure, review per ticket and run one final pass against the branch point."*

**Step 6 — close the ticket yourself. [synthesis, and this one is load-bearing.]**
`implement/SKILL.md` ends at the commit and has no completion step. The docs
page:

> Correct, and expected. `implement` has no completion step. It ends at the commit and never touches the work item, confirmed on GitHub Issues and on the local markdown tracker, so it is not a tracker integration problem. It also does not act on the findings `code-review` produced, and does not tick the `- [ ]` boxes on the originating issue. Close the ticket and reconcile the criteria yourself. This bites hardest on a dependency chain, because `to-tickets` defines the frontier as tickets whose blockers are all closed. If nothing gets closed, nothing ever becomes visibly unblocked.

**The summary chain.**

```
/setup-matt-pocock-skills (once)
  → /grill-with-docs ─┐
  → /to-spec          ├─ one unbroken context window
  → /to-tickets      ─┘  [quiz: granularity, edges, merge/split]
  → per ticket, blockers first:
        /clear → /implement #N → (commit) → /code-review → close #N by hand
  → /code-review <branch-point>   [final pass]
```

### 6.4 Workflow 4 — Brainstorm an Idea

**Step 0 — pick the front door.** One binary test, stated in three places.
`ask-matt:77`:

> **`/grill-me`** — the same relentless interview as `/grill-with-docs`, but **stateless**: it saves nothing locally and builds no `CONTEXT.md`. Reach for it when you are **not working in a working directory** — sharpening a plan, a design, a piece of writing, anything with no repo under it. If you are in a working directory, use `/grill-with-docs` instead: it runs the same interview and leaves a paper trail, so it is strictly the better one.

And the second test, for when the idea is too big for one session, from
`ask-matt:44`: *"Where **`/grill-with-docs`** sharpens an idea you can hold in
one session, wayfinder is for the idea you can't"* — that is §6.5.

| Situation | Skill |
| --- | --- |
| No working directory; the subject may not even be software | `/grill-me` |
| A repo, one session's worth of thinking | `/grill-with-docs` |
| More than one session's worth | `/wayfinder` |
| You want the interview with no wrapper | `/grilling` |
| The answers are in someone else's head | `/to-questionnaire` |
| The answer needs something runnable to react to | `/prototype` |
| The answer is an external fact | `/research` |

**Step 1 — run it, and understand the loop you are in.** The `grilling` body is
short enough to quote whole (`grilling/SKILL.md:6-22`):

> Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.
>
> Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.
>
> Each question should be formatted like so:
>
> ```
> ❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>
>
> ➡️ <your recommended answer>
> ```
>
> Each round the user answers reshapes the tree — settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.
>
> Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it — don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report — ask the rest of the frontier now. The _decisions_ are the user's — put each to them and wait.
>
> The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

Two things in that paragraph are the skill's real contract: the **facts/decisions
split** (an agent answering its own decisions has broken the skill, not
interpreted it liberally), and the **confirmation gate** in the last sentence.

**Step 2 — the docs half, if you used `/grill-with-docs`.** `domain-modeling`
runs inline. Its five in-session moves (`domain-modeling/SKILL.md:44-72`) are:
challenge against the glossary, sharpen fuzzy language, discuss concrete
scenarios, cross-reference with code, and update `CONTEXT.md` inline. The
glossary rule is absolute:

> When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. […]
>
> `CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

And the ADR bar — **all three, or no ADR**:

> Only offer to create an ADR when all three are true:
>
> 1. **Hard to reverse** — the cost of changing your mind later is meaningful
> 2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
> 3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons
>
> If any of the three is missing, skip the ADR.

`ADR-FORMAT.md` keeps the artifact tiny: *"An ADR can be a single paragraph. The
value is in recording *that* a decision was made and *why* — not in filling out
sections."*

**Step 3 — detour when you hit an ungrillable question.** `ask-matt:18-21`:

> 2. **Branch — can you settle every question in conversation?** If a question needs a runnable answer (state, business logic, a UI you have to see), detour through a prototype, bridged by **`/handoff`** in both directions […]
>    - **`/handoff`** out, then open a fresh session against that file,
>    - **`/prototype`** to answer the question with throwaway code,
>    - **`/handoff`** back what you learned, and reference it from the original idea thread.

`prototype/SKILL.md:8` is the whole idea: *"A prototype is **throwaway code that
answers a question**. The question decides the shape."* The branch matters —
*"The two branches produce very different artifacts — getting this wrong wastes
the whole prototype"*:

- **"Does this logic / state model feel right?"** → `LOGIC.md`: one
  self-contained HTML file, plain HTML/CSS/JS, no build and no server, with a
  labelled state panel, always-available free-play buttons, and tabbed guided
  walkthroughs. *"Write it for a non-developer. Every label is in **domain
  language**, not code."* The logic itself sits in a pure module *"that could be
  lifted out and dropped into the real codebase later."*
- **"What should this look like?"** → `UI.md`: three variants (default; cap at
  five) on a single route behind `?variant=`, with a floating switcher.
  *"Variants must be **structurally different** — different layout, different
  information hierarchy, different primary affordance, not just different
  colours."*

And the capture rule that applies to both (`prototype/SKILL.md:26`):

> **Capture it when done.** Fold any validated decision into the real code, then capture the prototype itself as a **primary source**: commit it to a throwaway branch, out of main, and leave a context pointer to that branch on the implementation issue. Capture the answer too — the verdict and the question it settled — in the issue or a commit. The main branch keeps only the validated decision.

**Step 4 — the other two detours.** When the missing input is a fact rather than
a decision, `/research` (`research/SKILL.md:6-12`):

> Spin up a **background agent** to do the research, so you keep working while it reads.
>
> Its job:
>
> 1. Investigate the question against **primary sources** — official docs, source code, specs, first-party APIs — not a secondary write-up of them. Follow every claim back to the source that owns it.
> 2. Write the findings to a single Markdown file, citing each claim's source.
> 3. Save it where the repo already keeps such notes; match the existing convention, and if there is none, put it somewhere sensible and say where.

When the missing input is in another person's head, `/to-questionnaire`. Its
defining move (`to-questionnaire/SKILL.md:9`):

> **Grill the send, not the subject.** Interview the user only about the _send_, which they can always answer: who it goes to, and what they need back. The questions in the document then target the **gap** between what the recipient knows and what the user needs.

It writes `to-questionnaire-<slug>.md` in the current directory. Run it in the
**same conversation** as the grilling that stalled — it has no ingest step, so a
fresh session knows nothing about the thread.

**Step 5 — land it.** From `ask-matt`, once the frontier is empty you are at
step 3 of the main flow: `/to-spec` if it is a multi-session build, `/implement`
if not, and nothing at all if the subject was not software. `grill-me`'s docs
page is explicit about the last case: *"If what you grilled does turn out to be
software, you can hand the same conversation to [to-spec] and carry on into the
build flow — an option, not the point of the skill."*

**Step 6 — the phase boundary.** When the grilling phase ends, work
`PHASE-BOUNDARIES.md`'s tree in order — *"The first **yes** wins"*:

| # | Question | Move |
| --- | --- | --- |
| 1 | Can you continue in this session? | **Continue** |
| 2 | Is the context irrelevant to what comes next? | `/clear` |
| 3 | Do you need to hand off — new harness, new directory, a colleague, or a side task forked mid-phase? | `/handoff` |
| 4 | Can the task be done AFK? | **Subagent** |
| 5 | Otherwise | `/compact` |

Two of those are routinely misused, and the file says which:

> `/compact` is the **default, not the first reach**. It sits at the bottom because the four questions above it are all cheaper or more precise. The failure mode when people start here is a fresh session that is confidently wrong about a decision the summary flattened.

> Every move except **Continue** turns a **primary source** into a **secondary source** — the session as it happened, replaced by a summary of it.

And the timing rule (`PHASE-BOUNDARIES.md:5`): *"The **phase boundary** is the
gap between two phases, and it is the only place this decision belongs.
Mid-phase there is no decision to make — continue, or split the work that's left
into subagents. Compacting mid-phase makes the agent lose the thread."*

Finally, `/wait-what` is available at any moment inside any of this. Its whole
body (`wait-what/SKILL.md:7`):

> Wait — I don't understand where you've got to here. Re-pitch that: give me a little bit of context, talk in ASD-STE100 Simplified Technical English, and use the ubiquitous language from `CONTEXT.md`.

**The summary chain.**

```
(repo?) → /grill-with-docs   |   (no repo?) → /grill-me
   ├─ ungrillable question → /handoff → /prototype → /handoff back
   ├─ missing external fact → /research           [background agent, cited .md]
   └─ answer in someone else's head → /to-questionnaire  [same conversation]
  → frontier empty → confirm shared understanding   ← the gate
  → phase boundary: continue / clear / handoff / subagent / compact
  → /to-spec (multi-session)  |  /implement (single-session)
```

### 6.5 Workflow 5 — Kickstart a Big Project from Scratch

`ask-matt:44` names the trigger and the cost in one sentence:

> - **A huge, foggy effort — a greenfield project or a huge feature build, too big for one session** → **`/wayfinder`**, the most cognitively demanding flow here. When the way from here to the destination isn't visible yet, it charts a **shared map** of **decision tickets** on the issue tracker and resolves them one at a time — producing **decisions, not deliverables** — until the fog is pushed back and the way is clear. Where **`/grill-with-docs`** sharpens an idea you can hold in one session, wayfinder is for the idea you can't — and it's slower and denser, so save it for exactly that, never a well-scoped feature.

**Step 0 — setup, and create the labels by hand. [synthesis]** `wayfinder`
writes issues labelled `wayfinder:map` and `wayfinder:<type>`. Setup does not
create labels (§3.6), and `gh issue create --label <missing>` fails outright, so
create `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`,
`wayfinder:grilling` and `wayfinder:task` before the first run. Support:
`setup-matt-pocock-skills/issue-tracker-github.md:40-41` for the label names,
and the docs page's *"Create them by hand before the first wayfinder run on a
GitHub repo."*

**Step 1 — `/wayfinder`, mode one: Chart the map.** Six steps, verbatim
(`wayfinder/SKILL.md:109-116`):

> User invokes with a loose idea.
>
> 1. **Name the destination.** Run a `/grilling` and `/domain-modeling` session to pin down what this map is finding its way to — the spec, decision, or change. The destination fixes the scope, so it's settled first.
> 2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole space rather than deep on any one thread, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** — the way to the destination is already clear, the whole journey small enough for one session — you don't need a map. Stop and ask the user how they'd like to proceed.
> 3. **Create the map** (label `wayfinder:map`): Destination and Notes filled in, Decisions-so-far empty, the fog sketched into **Not yet specified**.
> 4. **Create the tickets you can specify now** as child issues of the map — then wire blocking edges in a **second pass** (issues need ids before they can reference each other). Wiring sorts them into the frontier and the blocked; everything you can't yet specify stays in the fog — the **Not yet specified** section.
> 5. **Fire the research subagents.** For each `research` ticket you just created, spin up a `/research` subagent to resolve it in parallel, capturing its findings on a throwaway `research/<name>` branch with a context pointer from the ticket.
> 6. Stop — charting is one session's work; it hand-resolves nothing.

Step 2's early exit is the honest one to watch for: **if the breadth-first grill
surfaces no fog, you did not need wayfinder.** Drop back to §6.3.

The map body has four fixed sections — `## Destination`, `## Notes`,
`## Decisions so far`, `## Not yet specified`, `## Out of scope` — and one rule
governing all of them (`SKILL.md:23`):

> The map is an **index**, not a store. It lists the decisions made and points at the tickets that hold their detail; a decision lives in exactly one place — its ticket — so the map never restates it, only gists it and links.

**Step 2 — understand the four ticket types before you chart them.**
`wayfinder/SKILL.md:75-80`:

> Every ticket is either **HITL** — human in the loop, worked _with_ a human who speaks for themselves — or **AFK**, driven by the agent alone. A HITL ticket only resolves through that live exchange; the agent never stands in for the human's side of it (a grilling agent that answers its own questions has broken this).
>
> - **Research** (AFK): Reading documentation, third-party APIs, or local resources […] Resolved by a `/research` **subagent**. Use when knowledge outside the current working directory is required.
> - **Prototype** (HITL): Raise the fidelity of the discussion by making a cheap, rough, concrete artifact to react to […] Use when "how should it look" or "how should it behave" is the key question.
> - **Grilling** (HITL): Conversation. The default case. Always invoke the /grilling and /domain-modeling skills.
> - **Task** (HITL or AFK): Manual work that must happen before a _decision_ can be made […] This is the one type that _does_ rather than decides — and it earns its place by unblocking a decision, not by delivering the destination.

The `task` type is the documented trap: *"This is the type that goes wrong most
often in practice: agents interpret it as an implementation step and start
writing product code inside the map."* (`docs/engineering/wayfinder.md`)

**Step 3 — `/wayfinder <map>`, mode two: Work through the map.** Five steps
(`SKILL.md:120-126`), with a session rule stated before them: *"Either way,
**never resolve more than one ticket per session** — with the exception of
research tickets."*

> 1. Load the **map** — the low-res view, not every ticket body.
> 2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket in order. **Claim it**: assign it to yourself before any work.
> 3. Resolve it — **zoom as needed**: fetch the full body of any related or closed ticket on demand; invoke the skills the `## Notes` block names. If in doubt, use `/grilling` and `/domain-modeling`.
> 4. Record the resolution: post the answer as a **resolution comment**, **close** the issue, and **append a context pointer** to the map's Decisions-so-far.
> 5. Add newly-surfaced tickets (create-then-wire); graduate any fog the answer has made specifiable, clearing each graduated patch from **Not yet specified** so it lives only as its new ticket. If the answer reveals a ticket — this one or another — sits beyond the destination, **rule it out of scope** rather than resolving it on the route.

Repeat until nothing is left to decide. The fog/ticket test is one line
(`SKILL.md:88`): *"The test is whether you can state the question precisely now
— _not_ whether you can answer it now."*

**Step 4 — when the map clears, hand off. Do not build from it.**
`ask-matt:46`:

> When the map clears, **it hands off, it doesn't build**: merge onto the main flow at **`/to-spec`**, which collapses the map's linked decisions into a buildable plan, then `/to-tickets` and `/implement` as usual. Looping the map straight into `/implement` skips that collapse and throws the linked detail away — go straight to `/implement` only when the effort turned out genuinely small.

Feed `/to-spec` the **map issue**, not the individual decision tickets. From
`docs/engineering/to-spec.md`'s trigger table: *"A [wayfinder] map has cleared →
`/to-spec #<map_issue>`"*. Then §6.3 from step 3 onward.

**Step 5 — throughout: `/wizard` for anything only a human can do.**
`wizard` is model-invoked, so it can fire on its own, which is the point
(`wizard/SKILL.md:8`):

> A **wizard** is a bash script that walks a human, step by step, through a manual procedure that's tedious to do by hand and tedious to re-explain to an AI every time. It opens each URL, says exactly what to click and copy, captures the values, writes them where they belong (`.env`, GitHub secrets), confirms at every stage, and shows how many stages are left.

Its scoping step reads the repo before it asks: *"`.env`, `.env.example`,
`.env.*`, `README`, `docker-compose*`, framework config, and
`.github/workflows/*` (every `secrets.*` / `vars.*` reference is a value the
wizard must produce)."* And its non-trigger is in the description itself:
*"Don't invoke this for steps the agent can perform itself."*

**The summary chain.**

```
/setup-matt-pocock-skills   +   create the wayfinder:* labels by hand
  → /wayfinder  [chart]
        1 destination (grilling + domain-modeling)
        2 breadth-first grill  → no fog? stop, you don't need a map
        3 create wayfinder:map
        4 create tickets, then wire blocking edges in a second pass
        5 fire /research subagents for the research tickets
        6 stop
  → /wayfinder <map>  [work], once per session, one ticket:
        load low-res → claim by assignment → resolve → comment, close,
        append pointer → graduate fog / rule out of scope
  → map clear → /to-spec #<map_issue>   ← hand off, do not build
  → /to-tickets → per ticket: /clear → /implement → /code-review → close
        (/wizard whenever a step needs a human's hands)
```

**Two mistakes the router calls out by name.** Over-reaching for wayfinder on a
well-scoped feature (*"it's slower and denser, so save it for exactly that,
never a well-scoped feature"*), and looping the map straight into `/implement`
(*"skips that collapse and throws the linked detail away"*). The CHANGELOG
identifies these as *"The two mistakes people most often make with the heaviest,
most cognitively demanding flow."*

---

## 7. Anti-Patterns the Skills Name Themselves

Every item below is quoted from a `SKILL.md` or a supporting file — these are
the set's own warnings, not mine.

**Testing.** `tdd/SKILL.md:30-32`:

> - **Implementation-coupled** — mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
> - **Tautological** — the assertion recomputes the expected value the way the code does […] so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth — a known-good literal, a worked example, the spec.
> - **Horizontal slicing** — writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior […]

`tdd/mocking.md:10-14`: *"Don't mock: Your own classes/modules · Internal
collaborators · Anything you control."*

**Debugging.** `diagnosing-bugs/SKILL.md:66`: *"If you catch yourself reading
code to build a theory before this command exists, **stop — jumping straight to
a hypothesis is the exact failure this skill prevents.**"* And `:98`: *"Single-
hypothesis generation anchors on the first plausible idea."*

**Interviewing.** `grilling/SKILL.md:20`: *"Finding _facts_ is your job, never
the user's. […] The _decisions_ are the user's — put each to them and wait."*
`:22`: *"Do not act on it until the user confirms you have reached a shared
understanding."*

**Ticketing.** `to-tickets/SKILL.md:31`: *"Each slice cuts a narrow but COMPLETE
path through every layer (schema, API, UI, tests) — vertical, NOT a horizontal
slice of one layer."* And `:105`: *"avoid specific file paths or code snippets —
they go stale fast."*

**Triage.** `ask-matt:40`: *"Triage is only for issues **you didn't create** […]
Tickets that `/to-tickets` produced are already agent-ready, so **don't triage
them**."* And `triage/OUT-OF-SCOPE.md:88`: *"Do **not** write here when
something is closed as `wontfix` because it's **already implemented**. That's a
built feature, not a rejected one; recording it would poison the dedup checks
with false rejections."*

**Domain modelling.** `domain-modeling/SKILL.md:64`: *"`CONTEXT.md` should be
totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a
scratch pad, or a repository for implementation decisions. It is a glossary and
nothing else."* `CONTEXT-FORMAT.md:29`: *"General programming concepts
(timeouts, error types, utility patterns) don't belong even if the project uses
them extensively."*

**Module design.** `codebase-design/SKILL.md:65`: *"One adapter means a
hypothetical seam. Two adapters means a real one. Don't introduce a seam unless
something actually varies across it."* `DEEPENING.md:34`: *"Old unit tests on
shallow modules become waste once tests at the deepened module's interface exist
— delete them."* `codebase-design/SKILL.md:12`: *"Use these terms exactly —
don't substitute 'component,' 'service,' 'API,' or 'boundary.'"*

**Prototyping.** `prototype/UI.md:109-112`:

> - **Variants that differ only in colour or copy.** That's a tweak, not a prototype. Real variants disagree about structure.
> - **Sharing too much code between variants.** A shared `<Header>` is fine; a shared `<Layout>` defeats the point.
> - **Wiring variants to real mutations.** Read-only prototypes are fine.
> - **Promoting the prototype directly to production.** The variant code was written under prototype constraints (no tests, minimal error handling). Rewrite it properly when you fold it in.

`prototype/LOGIC.md:62-66`: *"Don't add tests. A prototype that needs tests is no
longer a prototype."* · *"Don't generalise. No 'what if we wanted to support X
later.'"* · *"Don't reach for a framework, bundler, or server."*

**Merge conflicts.** `resolving-merge-conflicts/SKILL.md:10`: *"Do **not**
invent new behaviour. Always resolve; never `--abort`."*

**Mapping.** `wayfinder/SKILL.md:13`: *"The pull to just do the work is usually
the signal you've reached the edge of the map and it's time to hand off."*
`:17`: *"A wall of `#42, #43, #44` is illegible; names read at a glance."*
`:91`: *"Don't pre-slice the fog into ticket-sized pieces."*

**Reviewing.** `code-review/SKILL.md:76`: *"Do **not** merge or rerank findings
— the two axes are deliberately separate."* `:41`: *"Each smell is a labelled
heuristic ('possible Feature Envy'), never a hard violation — and, like any
standard here, skip anything tooling already enforces."*

**Writing for the agent.** `writing-for-agents/SKILL.md:74`:

> **Negation** is the failure mode beside this lever: steering by prohibition drags the forbidden behaviour into context and makes it _more_ available, not less. _Don't think of an elephant_, and the elephant is all there is […] Prompt the **positive** — state the target behaviour ("write one-line comments") so the banned one is never spoken.

And `:81`: *"Hunt **no-ops** sentence by sentence: an instruction the model
already obeys by default pays load to say nothing. […] When a sentence fails,
delete the whole sentence rather than trim words from it."*

**Handing off.** `handoff/SKILL.md:12-14`: *"Do not duplicate content already
captured in other artifacts (specs, plans, ADRs, issues, commits, diffs).
Reference them by path or URL instead."* · *"Redact any sensitive information."*

---

## 8. Gaps, and What Fills Them

### 8.1 Gaps the skills admit to

| Gap | Source |
| --- | --- |
| `implement` never closes a ticket or ticks acceptance criteria | *"`implement` has no completion step. It ends at the commit and never touches the work item"* — `docs/engineering/implement.md` |
| `implement` cannot batch or parallelise; concurrent runs in one checkout corrupt git state | same page |
| `implement` cannot open a PR | *"Not built in. It commits straight to the current branch […] There is no configuration flag and no PR mode."* — same page |
| `tdd` decides *where* seams go, never *whether* a change is worth the loop | *"The skill decides *where* the seams go; nothing in it decides *whether* a change is worth the loop at all […] It is [issue #746] and it is open."* — `docs/engineering/tdd.md` |
| `tdd` has no refactor step, despite "red-green-refactor" in its description | *"the refactor step was removed and the description was not […] filed as [issue #589] and is still open"* — same page |
| `code-review` never converges | *"There is no convergence guarantee. Treat a pass as a list of leads […] do not run it in a loop until it comes back clean, because it will not."* — `docs/engineering/code-review.md` |
| `code-review` sub-agents can re-invoke the skill and fan out | *"one report reached 50-plus agents […] Neither is in the shipped skill yet."* — same page |
| `research` can spawn a duplicate of itself | *"an open bug, [issue #530] […] One reporter measured a single research task costing roughly 450k [tokens] across three overlapping runs"* — `docs/engineering/research.md` |
| `research` has no stopping criterion | *"There is no stopping criterion in the skill […] Scoping is on you."* — same page |
| Nothing re-reads a past research file | *"Nothing auto-loads a past research file; it is a document sitting in the repo until a human or a skill points at it."* — same page |
| `triage` has five states, and no `blocked` / `deferred` / `implemented` | *"the most-filed gap on the skill […] None of it has shipped."* — `docs/engineering/triage.md` |
| No `/refactor` skill for a genuinely out-of-control codebase | *"There is no dedicated `/refactor` skill for that case yet."* — `docs/engineering/improve-codebase-architecture.md` |
| `codebase-design` has no enforcement mechanism | *"It defines what a deep module *is*; it says nothing about how to stop a stray import from reaching past the interface."* — `docs/engineering/codebase-design.md` |
| `setup` creates no labels, has no user-level mode, holds no preferences | §3.6 |
| Grilling has no question cap, by policy | `.out-of-scope/question-limits.md`: *"A fixed cap would either cut off useful exploration on hard problems or feel arbitrary on easy ones."* |

### 8.2 Gaps in coverage, and what the user's `CLAUDE.md` routes to

`/home/qas/.claude/CLAUDE.md` declares Matt's skills the default workflow and
carries a precedence table over `superpowers:*`, then names four things
superpowers keeps:

> Superpowers keeps what Matt's set doesn't cover: `using-git-worktrees`,
> `executing-plans`, `verification-before-completion`, `dispatching-parallel-agents`.

I read each of those four `SKILL.md` files to check the claim. It holds, and
each one lands on a gap §8.1 already names:

| superpowers skill | `description:` (verbatim) | The gap it covers |
| --- | --- | --- |
| `superpowers:using-git-worktrees` | Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace exists via native tools or git worktree fallback | `implement` commits to *"the current branch"* and never creates one; parallel `/implement` runs in one checkout corrupt git state, and *"Git worktrees are the community workaround"* |
| `superpowers:executing-plans` | Use when you have a written implementation plan to execute in a separate session with review checkpoints | `implement` has no review checkpoints and no completion step |
| `superpowers:verification-before-completion` | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always | Nothing in the chain gates the completion claim. Its rule: *"If you haven't run the verification command in this message, you cannot claim it passes."* |
| `superpowers:dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies | `to-tickets` produces a frontier of independently-runnable tickets and then stops: *"The skill stops at the artifact, and there is no auto-dispatch mode."* |

The precedence table itself (same file) maps six task types onto Matt's set:
test-first work → `mattpocock-skills:tdd`; bugs, failures, slowness →
`mattpocock-skills:diagnosing-bugs`; reviewing a branch or PR →
`mattpocock-skills:code-review`; stress-testing a plan → `mattpocock-skills:grilling`
(or `/grill-me`); terminology, CONTEXT.md, ADRs → `mattpocock-skills:domain-modeling`;
module and interface design → `mattpocock-skills:codebase-design`; writing skills
and AGENTS.md/CLAUDE.md → `mattpocock-skills:writing-for-agents`.

One note on that table. It routes "reviewing a branch or PR" to
`mattpocock-skills:code-review` over the bundled `/code-review`, and that is a
real collision rather than a preference — `docs/engineering/code-review.md`
calls it *"the most reported problem with the skill"*, and notes the two do
different jobs: *"Claude Code ships its own `/code-review`, which does something
different — it hunts bugs in the diff, where this one checks spec compliance and
repo standards."* The `mattpocock-skills:` prefix is what disambiguates them.

### 8.3 One thing neither set covers

Nothing in either set decides **whether a change is worth the ceremony**.
`ask-matt` routes by situation, and every route lands on a skill. The set's own
answer, from `docs/engineering/to-tickets.md`, is that the floor is the context
window: *"if the whole change fits in one context window, you don't need this
skill at all. Go straight to [implement]."* Below that floor — a typo, a config
bump, a one-line fix — the honest move is no skill at all, and no document in
either set says so.

---

## 9. Sources

Everything below was read while writing this document. The plugin tree was read
on disk at a pinned version, so every `path:NNN` citation refers to that tree.

### Primary — the installed plugin tree

**Location:** `/home/qas/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/1.2.3/`
**Version:** 1.2.3 (`package.json` and `.claude-plugin/plugin.json` agree)
**Git HEAD:** `8b78b531ab965735c5dc74f6f7a219e1e37326df`, 2026-08-13, *"Merge
pull request #848 from mattpocock/domain-modeling-trigger-context-adr"*
**Clone depth:** shallow; `git log` reaches two commits, which is why release
history below is taken from `CHANGELOG.md` rather than from git.

Read in full:

| Group | Files |
| --- | --- |
| Root | `README.md`, `CLAUDE.md`, `CONTEXT.md`, `CHANGELOG.md`, `package.json`, `LICENSE` (metadata only) |
| Manifests | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| Repo-internal docs | `.agents/install-block.md`, `.agents/invocation.md`, `.agents/writing-docs.md`, `.agents/adr/0001-explicit-setup-pointer-only-for-hard-dependencies.md`, `.agents/adr/0002-ship-as-a-claude-code-plugin.md`, `.changeset/domain-modeling-trigger-context-adr.md` |
| Out-of-scope KB | `.out-of-scope/mainstream-issue-trackers-only.md`, `.out-of-scope/question-limits.md`, `.out-of-scope/setup-skill-verify-mode.md` |
| Engineering skills | `ask-matt/{SKILL.md,PHASE-BOUNDARIES.md}`, `codebase-design/{SKILL.md,DEEPENING.md,DESIGN-IT-TWICE.md}`, `code-review/SKILL.md`, `diagnosing-bugs/{SKILL.md,scripts/hitl-loop.template.sh}`, `domain-modeling/{SKILL.md,CONTEXT-FORMAT.md,ADR-FORMAT.md}`, `grill-with-docs/SKILL.md`, `implement/SKILL.md`, `improve-codebase-architecture/{SKILL.md,HTML-REPORT.md}`, `prototype/{SKILL.md,UI.md,LOGIC.md}`, `research/SKILL.md`, `resolving-merge-conflicts/SKILL.md`, `setup-matt-pocock-skills/{SKILL.md,domain.md,triage-labels.md,issue-tracker-github.md,issue-tracker-gitlab.md,issue-tracker-local.md}`, `tdd/{SKILL.md,tests.md,mocking.md}`, `to-spec/SKILL.md`, `to-tickets/SKILL.md`, `triage/{SKILL.md,AGENT-BRIEF.md,OUT-OF-SCOPE.md}`, `wayfinder/SKILL.md`, `wizard/SKILL.md`, `README.md` |
| Productivity skills | `grill-me/SKILL.md`, `grilling/SKILL.md`, `handoff/SKILL.md`, `teach/{SKILL.md,MISSION-FORMAT.md,RESOURCES-FORMAT.md,GLOSSARY-FORMAT.md,LEARNING-RECORD-FORMAT.md}`, `to-questionnaire/SKILL.md`, `wait-what/SKILL.md`, `writing-for-agents/{SKILL.md,SKILL-MECHANICS.md}`, `README.md` |
| Non-promoted | `skills/misc/README.md` + frontmatter of all 4 misc skills; `skills/in-progress/README.md` + frontmatter of all 6 in-progress skills; `skills/deprecated/README.md` |
| Scripts | `scripts/link-skills.sh`, `scripts/list-skills.sh`, `scripts/sync-plugin-version.mjs`; `skills/engineering/wizard/template.sh` (structure and markers only) |
| Human-facing docs pages | All 20 under `docs/engineering/` and `docs/productivity/` |

`scripts/link-skills.sh` carries a warning worth recording, since it looks like
an installer and is not: *"This is a dev-only script, intended for use by
maintainers of this repo. It is not a supported installer."* It symlinks every
skill except `deprecated/` into `~/.claude/skills` and `~/.agents/skills`.
`sync-plugin-version.mjs` copies `package.json`'s version into
`plugin.json` during `npm run version`, which is why the two always agree.

### Secondary — the public repository

Used only to date changes not yet in this install, via `gh api` on 2026-09-14.
Where it disagrees with the installed tree, §2.4 says so and the installed tree
is preferred.

| Artefact | Value |
| --- | --- |
| `main` HEAD | `3cca18b368ae95cdbdebbff572ccafa662551015`, 2026-09-04 |
| Distance from installed HEAD | 34 commits ahead, 0 behind |
| `main` version | 1.2.3 (both `package.json` and `plugin.json`) |
| Latest release | `v1.2.3`, tagged `835450ef244ab7335f75d95b83e7d979eae22a6d`, 2026-08-06 |
| Releases | v1.0.0 → v1.0.1 (2026-06-17) → v1.1.0 (2026-07-08) → v1.2.0 (2026-08-05) → v1.2.2 (2026-08-05) → v1.2.3 (2026-08-06) |

Files fetched from `main`: `.claude-plugin/plugin.json`, `package.json`,
`.agents/invocation.md`, `skills/engineering/{grill-with-docs,implement,to-spec,triage,diagnosing-bugs}/SKILL.md`,
`skills/productivity/grill-me/SKILL.md`, and the eight unreleased changesets
under `.changeset/` (`user-invoked-skill-invocation`,
`skill-tool-invocation-terminology`, `add-implement-spec-skill`,
`grilling-add-hr-between-questions`, `fix-yaml-frontmatter-colons`,
`wait-what-context-map`, `remove-em-dashes-repo-wide`, `grilling-remove-em-dashes`).

Repository URL: <https://github.com/mattpocock/skills>. Published docs for each
promoted skill live at `https://aihero.dev/skills-<skill-name>`; none was
fetched, because the same pages are in the installed tree under `docs/`.

### Context — this machine

| File | Used for |
| --- | --- |
| `/home/qas/.claude/CLAUDE.md` | The user's precedence table over `superpowers:*` (§8.2) |
| `/home/qas/.claude/plugins/cache/claude-plugins-official/superpowers/6.3.0/skills/{using-git-worktrees,executing-plans,verification-before-completion,dispatching-parallel-agents}/SKILL.md` | The four superpowers skills named in that table. Read to verify the gap claims; version 6.3.0 |
| `/home/qas/Documents/me/researcher/CLAUDE.md` | The `## Agent skills` block as `setup-matt-pocock-skills` writes it (§3.5) |
| `/home/qas/Documents/me/researcher/docs/agents/{issue-tracker,domain,triage-labels}.md` | The three setup artifacts (§3.5) |
| `/home/qas/Documents/me/researcher/CONTEXT.md` | A `CONTEXT.md` in `CONTEXT-FORMAT.md` shape (§3.5) |
| `/home/qas/Documents/me/researcher/docs/adr/0001-shared-stylesheet-across-independent-topics.md` | An ADR that visibly passes all three gates (§3.5) |
| `/home/qas/Documents/me/researcher/docs/research/sql-schema-migrations.md` | House style for this document |

---

## 10. What could not be verified

Six things here rest on something weaker than a quoted instruction. They are
flagged in place and collected so the gaps are countable.

**1. The `mattpocock-skills:` prefix and the eleven-skill listing are a
first-hand observation of this session, not a document.** §2.2 reports that the
model-visible skill listing in this session contains exactly the eleven
model-invoked skills, under a `mattpocock-skills:` prefix, and that the fourteen
user-invoked ones are absent. That is what this harness showed; the only written
support is `docs/engineering/code-review.md`'s sentence about the prefix and
`docs/engineering/ask-matt.md`'s description of the same exclusion. Claude Code's
own plugin documentation was not consulted, so the exact naming and precedence
rules for plugin-namespaced skills are not sourced here.

**2. The workflow orderings in §6 are synthesis on top of a router, and the
router is a self-declared secondary source.** Steps and their contents are
quoted from `SKILL.md` files. The *sequences* come from `ask-matt/SKILL.md`,
which its own docs page describes as *"a [secondary source] over the skills it
describes"* and *"hand-maintained and lags the repo"*. Every step where I went
beyond it is marked **[synthesis]**. Nothing in the repo states the five
workflows as such; the split into these five is mine.

**3. No workflow was executed.** This document is a reading of the skill files,
not a report of running them. Claims about what a skill produces are claims
about what its text instructs. Every observed-failure quote in §6 and §8 comes
from a docs page, which is the repo's own record of user reports — second-hand
by construction, and undated.

**4. The docs pages' issue numbers and counts were not checked against the
tracker.** Issue references (#746, #589, #530, #616, #554, #513, #377, #335,
#559, and the rest) are quoted as the docs pages state them. None was fetched,
so whether any has since been closed is unknown. One count is demonstrably
stale: `docs/engineering/ask-matt.md` says *"Thirteen of the plugin's twenty-two
skills carry the flag"*, where the installed `plugin.json` lists 25 skills and
14 carry `disable-model-invocation: true`.

**5. Whether an updated plugin will change the cross-skill invocation syntax is
an inference.** §2.4 reports that `main` replaces `` Run a `/grilling` session ``
with `Call the Skill tool with "grilling"`, and quotes the changeset explaining
why. Those changesets are unreleased — there is no 1.2.4 in `CHANGELOG.md` and
no tag beyond v1.2.3 — so the statement that this *will* reach plugin users is
an expectation, not a fact. The mechanism by which it would (the official
marketplace's pinned sha moving) is documented in
`.agents/adr/0002-ship-as-a-claude-code-plugin.md` and was not independently
verified.

**6. The claim that a user-invoked skill cannot be reached by another skill is
documented in the installed tree, but the consequence for the seven existing
cross-references is only documented on `main`.** `.agents/invocation.md:8` in
1.2.3 states the invariant plainly (*"nothing but the human can fire it — no
other skill can"*). It does **not** connect that to the seven places where a
1.2.3 skill nonetheless instructs the agent to run `/setup-matt-pocock-skills`
or `/improve-codebase-architecture`. §5.2's conclusion that all seven are
inoperative is drawn from the invariant plus the unreleased changeset that fixes
them, not from any statement in the installed tree. The practical advice — read
them as messages to you — follows from the invariant either way.
