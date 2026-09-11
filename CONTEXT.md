# researcher

A personal learning repo. Each subject is taught by the `/teach` skill into its
own workspace, and the result is published so it can be read anywhere and
referred back to as the trusted account of that subject.

## Language

### The unit of study

**Topic**:
One subject being learned, and the directory that holds everything taught about
it.
_Avoid_: Course, module, subject, section

**Topic workspace**:
The directory `topics/<topic-slug>/`, containing exactly the file set `/teach`
operates on. The unit `/teach` is pointed at.
_Avoid_: Project, folder, workspace root

**Mission**:
The reason the learner wants this topic, recorded once per topic workspace. Every
lesson in the topic ties back to it.
_Avoid_: Goal, objective, why

### What gets written

**Lesson**:
One self-contained HTML page teaching one tightly-scoped thing, numbered in
sequence within its topic.
_Avoid_: Chapter, article, tutorial, page

**Reference document**:
A compressed, screen-only HTML page for fast lookup of things a lesson
establishes — syntax, algorithms, a glossary. Revisited, where a lesson is not.
_Avoid_: Cheat sheet, summary, docs

**Learning record**:
A dated note capturing a non-obvious lesson or insight the learner reached,
numbered in sequence within its topic. The evidence used to judge what to teach
next.
_Avoid_: Journal entry, log, retro

**Glossary**:
A topic's own vocabulary. Canonical in `GLOSSARY.md` and rendered as a reference
document, so what the learner reads and what an agent checks against are one
thing.
_Avoid_: Terms, dictionary

### Sourcing

**Primary source**:
The authority a claim rests on and is quoted from: a specification, official
documentation for a named version, an original paper, or a recognised textbook.
Not a blog post, and never the agent's own recall.
_Avoid_: Citation, reference, link, docs

**Excerpt**:
A quotation from a primary source, carrying attribution and a link, shown as the
source's words rather than the lesson's.
_Avoid_: Quote block, blockquote, snippet

### The published site

**Shared presentation layer**:
The stylesheet, syntax highlighter, highlighter theme, and quiz widget in root
`assets/`. The only thing shared across topics, and presentation rather than
knowledge.
_Avoid_: Theme, framework, design system

**Front door**:
The root `index.html` that lists the topics. Navigation only, maintained by hand.
_Avoid_: Home page, landing page, dashboard, TOC
