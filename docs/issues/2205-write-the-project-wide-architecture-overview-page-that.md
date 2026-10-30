---
issue: "[Write the project-wide architecture overview page that names each system and each critical component](https://github.com/nedschorus/nedschorus/issues/2205)"
---

# Write the project-wide architecture overview page that names each system and each critical component

## Why

No page describes the project as a whole: the glossary's nc-architecture-overview is one wiki page per system under `nc-systems/`, and nothing above those pages names every system and the parts outside the project's own code that all of them stand on. When such a part fails, an agent has nowhere to look to learn that the failure is one it must report to the user and must not work around.

The user asked for this page on 2026-10-30 at 10:26, in item 5 of the approval-walk prime-intellect-handed-over-items-2026-10-29. The item proposed a `CLAUDE.md` bullet naming ned-box, git and GitHub as critical components, and he disapproved it. Its minutes, `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, record his answer at line 37 and the result at line 39; `docs/walk/` is not committed, so until the approval-walk closes the minutes are read on ned-box at that path. When it closes, `scripts/walk-files-ship.py` copies them to the log-store, at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, which is then the copy to cite. His words:

- "I really like to keep Claude.md as small as possible because ... the more that's in it, the more diluted the things that are in it."
- "Git and GitHub ... are quite important, and I think we've guarded them to some extent, but they are in the long term very uncommon."
- "I've seen a lot of projects that do have ... some sort of overall architecture, and that architecture explains all the critical components. And if we did have that, that seems like a good thing to have, and that would be another place where we could explain that the critical components, most of them can't be worked around, and they can only be reported on and our system can't fix it. Some external thing has to fix it."
- "a wiki page for the system architecture of this system, the NC system architecture, and what's in it and what we say about each piece. With the idea that when there's problems with the system architecture or changes the system architecture, agents will look there and go, 'Oh, this one is a mission. This one's a showstopper if it breaks, so I can't fix it or I can't work around it.'"

In this GHI-MD, a critical component is a part the project does not own and whose failure stops work that has no other way to go on, so only someone outside the project, usually the user, can fix it.

## What the page says

- It names each system under `nc-systems/`, in one line each, and links that system's nc-architecture-overview where one exists. GHI [Rationalize the repository layout: group components by owning system under nc-systems/](https://github.com/nedschorus/nedschorus/issues/224) defines the systems and plans a one-line-per-system repository map in `nc-systems/`; when that map exists, the page links it as well.
- It names each critical component and says what the project uses it for.
- For each critical component, it says that a failure of it is a showstopper: an agent reports the failure to the user, with what the failing command said and its remedy if it gave one, and does not build a workaround, a fallback or a second source, such as another machine or service set up to do the same job. A retry of a passing fault, such as one dropped connection, on an operation safe to repeat and with a limit on attempts, stays allowed, as `CLAUDE.md`'s bullet on guards and workarounds says; a failure that outlasts it is reported.
- It says what counts as a failure of a critical component: the component itself being unavailable, such as GitHub not answering, ned-box unreachable, or the Claude account logged out or over its usage limit. A command that reaches the component and gets its answer is not a failure of that component, even when it ends with a nonzero exit: a git merge that stops on a merge conflict, a push GitHub refuses, or a script that ssh starts on ned-box and that exits nonzero. The agent handles such an exit as part of its work, and the showstopper rule does not apply.
- `CLAUDE.md` already states this rule for ned-box alone, in its bullet on the two machines: "When ned-box cannot be reached, or a program reports that ned-box's `claude` is logged out, tell the user what the failing command or program said, with its remedy if it gave one. Do not find another way to do a step that needs ned-box: leave that step until ned-box is fixed or the user says otherwise, and meanwhile carry on with work that does not need ned-box." The page states the same rule for every critical component.
- It names the critical components in a section of their own, apart from any list of the project's files. `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md` says a system's overview lists no programs from outside the repository, such as `claude` or `git`, among its components; this page names such parts on purpose, because the user asked for a page that names them.

## The critical components

Checked on main at c33ed03d4 against what the project's work cannot go on without:

- ned-box, its disk included: most agent-seats, merge-lane-2 and the log-store run there (`CLAUDE.md`, bullet on the two machines).
- The user's Mac, its disk included: the user reads and answers from it, and its own agent-seats run there.
- The network between the Mac and ned-box: the Mac reaches ned-box and the log-store only over it.
- git: every change reaches main as a commit on a topic branch.
- GitHub: every change merges as a pull request, and every GHI lives there.
- The Claude account and its usage limit: every agent-seat on both machines runs Claude Code under it; when the limit is reached, those agent-seats stop.
- Codex: `scripts/pull-request-review-plan.py` gives every pull request that changes code a review tier that includes the Codex reviewer, so such a pull request does not merge without it.

Gemini is not on the list: the cold-read programs, its only users found (`grep -rlE '\bagy\b' scripts nc-systems`), fall back to another model when Gemini's reviewer gives no report (the `FELL BACK:` line in `.claude/skills/cold-read/SKILL.md` step 6).

## What the page does not repeat

Two open GHIs already cover parts of this ground, and the page links their pages instead of repeating them; while either page has not merged, the page names its GHI instead, and is updated to link the page when it lands:

- GHI [Write the wiki page that lists the system's requirements](https://github.com/nedschorus/nedschorus/issues/1908) lists every part the project stands on, for someone setting the project up. Its starting text lists eight parts, the machines' disks and Gemini among them; the list above counts each machine's disk as part of the machine. Once that page merges, the page this GHI asks for checks the list above against it.
- GHI [Write the wiki page that gives each system requirement's fallback and escalation paths when it fails](https://github.com/nedschorus/nedschorus/issues/1910) gives, for each part, what stops when it fails and what happens next. The page this GHI asks for says only that a critical component's failure is a showstopper, with the rule above, and links that page for the detail. What an agent does when the failed part is its own path to the user, such as the network, and how a waiting agent learns that the part is fixed, are among GHI 1910's open questions, not this page's.

On 2026-10-24 the user ruled, in GHI 1908, that the list of parts and what to do when each fails are two pages, written in that order. His 2026-10-30 words above describe one architecture page that names the components and says their failures are reported. This GHI reads the two rulings together: the overview names the systems and critical components and states the rule; the two pages of GHI 1908 and GHI 1910 keep the detail.

GHI 1910 also proposes widening `CLAUDE.md`'s ned-box bullet to every hard dependency. His 2026-10-30 wish to keep `CLAUDE.md` small bears on that proposal; this GHI does not settle it.

## Where the page lives, and its shape

The page's place and shape follow the page that names each kind of document, which ned-box-helper is drafting as its task #162, "Item 5.3.1 (approved): draft one page naming each kind of document, test it on the handoff-system" (`nedlern@ned-box:/home/nedlern/.claude/tasks/nedschorus-ned-box-helper-tasks/162.json`). That task had not started on 2026-10-30; ned-box-helper asked prime-intellect to file this GHI without waiting for it.

prime-intellect's task #63 (`nedlern@ned-box:/home/nedlern/.claude/tasks/nedschorus-prime-intellect-tasks/63.json`) plans overviews at three levels, project, system and subsystem, with a project overview at `docs/nedschorus-wiki/nedschorus-project-architecture-overview.md` linking every system's overview. That name is a candidate for this page, not yet ruled: the page takes the path task #162's page gives, and this name only if that page gives none.

## Related work

- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168): the process that writes and checks an overview.
- `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`: how a system's nc-architecture-overview is written today.
- GHI 224, above: in the same answer, the user wanted git and GitHub described in the architecture overviews of the "getting work onto main" system and the "GitHub issues" system that GHI 224 names, as well as on this page.

## Next action

When ned-box-helper's task #162 page has landed on main, write this page in the place and shape it gives: its path, its sections and its length. The content is what "What the page says" lists, with the list under "The critical components" checked again against main. Give the page its /cold-read, which for a wiki page is a cold-read-full-run, and open its pull request to merge-lane-2. When it merges, record the outcome in this GHI-MD and close the GHI.
