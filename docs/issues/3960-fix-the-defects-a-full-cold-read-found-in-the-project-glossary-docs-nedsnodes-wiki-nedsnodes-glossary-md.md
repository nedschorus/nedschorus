---
issue: "[Fix the defects a full cold read found in the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`](https://github.com/nedsnodes/nedsnodes/issues/3960)"
---

# Fix the defects a full cold read found in the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`

## What is wrong

On 2026-11-20 the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, had a cold-read-full-run, because pull request [3948](https://github.com/nedsnodes/nedsnodes/pull/3948) changes one sentence of its opening and three phrases of its agent-crash-watcher and failed-restart-notice entries. Its seven reviewers, and an eighth that answered which rules should be code, raised 228 findings. All but a handful are about text that pull request does not change, so the triage deferred them to this issue rather than fixing them there: fixing them changes glossary entries, which needs the user's approval, and the glossary has no section of its own to hold deferred findings.

The reports, and the triage that lists each finding on one line, are in the cold-read-record `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/nedsnodes-glossary-2026-11-20-3`. Each report quotes the glossary as it stood at commit `fde57e0b1`. The findings come from these report files in that cold-read-record: `claude-hunt-deep.md` (52), `claude-hunt-second-strongest-model.md` (54), `claude-terminology-deep.md` (42), `codex-hunt-deep.md` (25), `codex-hunt-second-strongest-model.md` (22), `agy-hunt-gemini-4-argon-high.md` (15), `codex-terminology-deep.md` (7) and `question-4-what-should-be-code-answer.md` (11). Many findings repeat one another across reports.

Examples of what they found, each checked against the glossary on main on 2026-11-20:

- The page's title is "nedschorus glossary" and its NC entry names the project NedsChorus, while every path it gives uses nedsnodes. Seven entries are named with the prefix nc- and two with nn-, and the nc-system entry writes its own plural as "nn-systems"; the page says what neither prefix stands for. Report: `claude-hunt-deep.md` 1.
- The opening says "Generic SDLC vocabulary is deliberately absent", but entries such as nc-head-commit, nc-topic-branch and nc-test-suite open with that generic vocabulary. Report: `claude-hunt-deep.md` 2.
- The opening says a project-term takes one of four forms, but "case fix" has no hyphen and "ready" is one ordinary word. Report: `claude-hunt-deep.md` 3.
- The rule that a project-term or system-term "has one definition" is broken on the page itself: what a system-term is is stated in the opening twice and again in the project-term and system-term entries, and the copies already differ. Report: `claude-hunt-deep.md` 5.
- Some entries use terms that only a system glossary defines, such as handoff-deferral in the ready entry, though the opening says a term more than one system uses is defined here. Reports: `claude-hunt-deep.md` 6, `question-4-what-should-be-code-answer.md` 1.
- The agent-crash-watcher and failed-restart-notice entries state twice the cases in which the user is shown a notice, and leave out a fourth case that `nn-systems/handoff/handoff-agent-crash-watcher.py` handles: an agent-seat started outside the user's systemd manager. The agent-seat fleet-restart-at-login has no entry. Reports: `agy-hunt-gemini-4-argon-high.md` 6, `claude-hunt-deep.md` 16, `claude-terminology-deep.md` 15.
- The opening says `scripts/system-glossaries-listed-on-the-project-glossary-test.py` fails until a new system glossary is listed, but the test sees only git-tracked files whose names end `-glossary.md`. Report: `claude-hunt-deep.md` 8.
- Rules the writer alone enforces could be code: a test that each term fits one of the four forms, a test that each hyphenated term used inside an entry has an entry in some listed glossary, and a program that prints a term's entry and the glossary it is in. Reports: `question-4-what-should-be-code-answer.md` 2 and 3. The defects listed above, such as "case fix" and the ready entry's handoff-deferral, are cases these tests would have caught, so the user decides whether each is built.

Why it matters: every agent is told to read the glossary when it meets a term it does not know, and to use a term as the glossary spells it. Where the glossary contradicts itself, two agents read the same term two ways; where an entry is missing or points nowhere, an agent cannot find the meaning it was sent to look up.

## The work

1. Once pull request 3948 has merged, sort the 228 findings into distinct defects against the glossary as it then stands on main, dropping each one main has fixed since, and write the list of defects, each with the findings it covers, in a supporting document beside this GHI-MD. Start the broken references from the 22 lines marked UNRESOLVED in the cold-read-record's `cold-read-reference-check.md`, checked again against main.
2. Fix every obvious-error-fix, as the project glossary defines it, together in one pull request. A defect whose fix you are unsure is an obvious-error-fix goes to work item 3 instead.
3. Bring the user every other defect, each with a proposed change, and the three proposed programs above, in one approval-walk. Once the pull request of work item 2 has merged, carry out what he approves in one pull request cut from main. A defect he disapproves is left as it is; one he defers stays listed in the supporting document.

## Next action

The agent-seat agent-instructions-editor, which makes changes to the files the instruction-file guard protects, does work item 1, then opens the pull request of work item 2 and runs the approval-walk of work item 3.
