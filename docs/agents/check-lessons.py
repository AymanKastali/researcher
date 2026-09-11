#!/usr/bin/env python3
"""Check every lesson and reference sheet against docs/agents/teaching-standard.md.

    uv run python docs/agents/check-lessons.py

Reports violations and exits non-zero if any are found. A clean run is
necessary, not sufficient: nothing here can tell you whether a lesson sits in
the zone of proximal development.
"""

import collections
import glob
import html
import os
import re
import sys

# Options that are code are held to character parity only — padding SQL to hit
# a whitespace-token count makes it less idiomatic, and plausible code is the
# thing being tested. See teaching-standard.md.
CODE_OPTION = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|BEGIN|COMMIT)\b", re.I
)
AFFIRMATIVE = re.compile(
    r"^(correct|yes\b|right answer|right\b|exactly|precisely|indeed)", re.I
)
CHAR_SPREAD_LIMIT = 12


def text_of(fragment):
    """Visible text of an HTML fragment, whitespace collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", fragment))).strip()


def questions(src):
    for m in re.finditer(r'<li class="q" data-answer="(\w)">(.*?)\n  </li>', src, re.S):
        answer, body = m.group(1), m.group(2)
        prompt = re.search(r'<p class="q-text">(.*?)</p>', body, re.S)
        options = [
            (k, text_of(v))
            for k, v in re.findall(r'<button data-opt="(\w)"[^>]*>(.*?)</button>', body, re.S)
        ]
        feedback = {
            k: text_of(v)
            for k, v in re.findall(
                r'<div class="feedback" data-for="(\w)">(.*?)</div>', body, re.S
            )
        }
        yield answer, text_of(prompt.group(1)) if prompt else "", options, feedback


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(root)

    lessons = sorted(glob.glob("topics/*/lessons/*.html"))
    references = sorted(glob.glob("topics/*/reference/*.html"))
    if not lessons:
        print("no lessons found — run this from anywhere inside the repo")
        return 1

    problems = []
    exemptions = []
    positions = collections.Counter()
    total = 0

    for path in lessons + references:
        src = open(path).read()
        name = path[len("topics/") :]
        is_lesson = "/lessons/" in path

        if is_lesson:
            # Per-lesson requirements from the skill.
            if "ask-teacher" not in src:
                problems.append((name, "no .ask-teacher reminder"))
            if not re.search(r"primary source", src, re.I):
                problems.append((name, "no recommended primary source"))
            nav = re.search(r'<p class="nav-links">(.*?)</p>', src, re.S)
            if not nav:
                problems.append((name, "no nav-links block"))
            else:
                hrefs = re.findall(r'href="([^"]*)"', nav.group(1))
                siblings = [h for h in hrefs if re.match(r"^\d{4}-", h)]
                if not siblings:
                    problems.append((name, "nav-links reaches no other lesson"))
                if not any("index.html" in h for h in hrefs):
                    problems.append((name, "nav-links has no Contents link"))
                if not any("../reference/" in h for h in hrefs):
                    problems.append((name, "nav-links has no reference-sheet link"))
            # A lesson describing an existing sibling should link to it.
            coming = re.search(r"Coming next</h2>(.*?)(?=<p class=\"ask-teacher\")", src, re.S)
            if coming and "href=" not in coming.group(1):
                problems.append((name, "'Coming next' names a lesson without linking it"))

        for answer, prompt, options, feedback in questions(src):
            total += 1
            positions[answer] += 1
            label = f'{name} · "{prompt[:48]}"'

            if sorted(k for k, _ in options) != sorted(feedback):
                problems.append((label, "options and feedback blocks disagree"))
            if answer not in feedback:
                problems.append((label, f"no feedback for the correct option ({answer})"))
                continue

            affirming = [k for k, v in feedback.items() if AFFIRMATIVE.match(v)]
            if answer not in affirming:
                problems.append((label, f"feedback for {answer} does not read as correct"))

            texts = [t for _, t in options]
            words = {len(t.split()) for t in texts}
            lengths = [len(t) for t in texts]
            spread = max(lengths) - min(lengths)

            if any(CODE_OPTION.match(t) for t in texts):
                if len(words) > 1:
                    exemptions.append((label, f"code options, word counts {sorted(words)}"))
                if spread > CHAR_SPREAD_LIMIT:
                    problems.append((label, f"code options differ by {spread} characters"))
                continue

            if len(words) > 1:
                problems.append((label, f"word counts differ: {sorted(words)}"))
            if spread > CHAR_SPREAD_LIMIT:
                problems.append((label, f"character counts differ by {spread}"))

    # Answer position should not cluster. Flag any letter more than 50% off even.
    print(f"{len(lessons)} lessons, {len(references)} reference sheets, {total} questions")
    if total:
        even = total / 4
        spread = ", ".join(f"{k}={positions[k]}" for k in "abcd")
        print(f"correct-answer positions: {spread}  (even would be ~{even:.0f} each)")
        for letter in "abcd":
            if abs(positions[letter] - even) > even * 0.5:
                problems.append(
                    ("whole repo", f"answer position {letter} appears {positions[letter]} times")
                )

    for label, note in exemptions:
        print(f"  exempt  {label} — {note}")
    for label, note in problems:
        print(f"  FAIL    {label} — {note}")

    print("clean" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
