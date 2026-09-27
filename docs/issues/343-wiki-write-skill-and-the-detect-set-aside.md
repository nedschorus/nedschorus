---
issue: "[wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343)"
---

# wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call

## What is wanted

Two parts, user-ruled 2026-09-13 in a walk.

**1. A `wiki-write` skill** — the procedure for creating or revising a page under
`docs/nedschorus-wiki/` (renamed from `docs/wiki/` by PR [docs/wiki becomes docs/nedschorus-wiki, so the Obsidian vault has a name](https://github.com/nedschorus/nedschorus/pull/347) on 2026-09-14, after this issue was filed; the search receipt below quotes the old name because that is what was searched). The name is the user's, chosen to match `ghi-write`. This is not a
family of four skills: `ghi-write` already owns GitHub issues and queue files,
so this covers the wiki page only.

Model it on `ghi-write`, on the user's direction: "the ghi-write skill does a lot
of smart things so that we don't duplicate or mess up the ghis. I'd do very
similar stuff for the wiki-write process." The anti-duplication machinery is what
carries across — ask the index first, revise an existing page rather than add a
second on the same subject, route by state, write for a fresh reader, make every
reference openable.

That machinery already paid once. A seat was about to write a testing-technique
wiki page, ran `scripts/ghi-info-ask.py`, and found
GHI [Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)](https://github.com/nedschorus/nedschorus/issues/18) already owned the
subject with a sharper formulation. Nothing was written.

**2. The enforcement, which is the half that matters.** A Stop hook that compares
the working tree against `origin/main` for protected paths, **sets the change
aside**, and tells the agent to walk it with the user.

## Why a Stop hook and not a PreToolUse block

The user rejected the pre-emptive approach outright: "there is no way to know if
BASH or some other tool or code will write/edit a wiki page ... there are
infinite ways to do that."

A pre-emptive gate screens **tool calls**. This one checks the **file**, so it
catches bash heredocs, `sed`, Python scripts, and subagents alike.

Measured 2026-09-13, which is what settled it. `.claude/hooks/instruction-file-guard.py`
is PreToolUse on `Edit|Write|NotebookEdit`. Two payloads naming the same
`CLAUDE.md` were fed to it: the `Edit` payload exited 2 (denied, with the
walk-approval message), the `Bash` heredoc payload exited 0 (allowed). Two
independent causes — `.claude/settings.json` never invokes the hook for Bash, and
the hook reads only `tool_input.file_path`/`notebook_path`, so a Bash payload has
no target to check. The seat that measured it had written every file in that
walk by `cat > ... <<EOF` heredoc, under a mode that instructs exactly that.

**Set aside, do not delete** (user-accepted refinement): a new wiki page is
untracked, so `git checkout --` would not remove it anyway, and discarding the
text means rewriting it if the user approves. Move it into the session scratchpad
and name the path in the message, so approval restores the work.

## Open question, not ruled

Does this mechanism also replace the PreToolUse guard for `CLAUDE.md`,
`CLAUDE.local.md` and `.claude/`? Those carry the same incompleteness, measured
above, and are higher-stakes than a wiki page. The user ruled on the wiki case
only. Note the PreToolUse guard has value the Stop hook lacks: it refuses
*before* the write and teaches the `.walk-approved` override in the denial
itself, so adding rather than replacing may be right.

## Precedent

`nc-systems/main-gatekeeper/main-gatekeeper.py` — "the single program through which every change
reaches main" — checks the content pushed rather than how it was authored.
`scripts/checkout-freshness-catch-up.py` is an existing Stop hook already doing
git work at every turn end.

## Next action

Build the Stop hook first: it has value whether or not the skill exists, and it
is the half that does not depend on an agent remembering anything. Then the
skill.

A new skill gets the full cold-read run of six fresh reviewers before it lands —
user-ruled the same day: "I'd be very careful with skills."

## Search receipt

`gh issue list --state all --limit 60 --search "wiki page skill OR wiki-write OR
docs/wiki"` and a second search for "ghi-write skill OR cold-read skill OR
wiki-write OR instruction-file-guard OR walk approved", 2026-09-13. Nearest are
GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168) (overview-write),
GHI [Project vocabulary wiki page: define this project's own terms so a zero-context reader can resolve them](https://github.com/nedschorus/nedschorus/issues/213) (vocabulary page) and
GHI [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256) (four small skills).
None covers how a wiki page is created or what stops one being created
unasked.



## Ruled 2026-09-15: the walk is the mechanism, for a batch or a single change, and it runs at once

Asked at the cold-read-research seat whether a dedicated wiki-update subsystem should let him rule on a change immediately rather than set it aside for a later walk, the user ruled, verbatim: "Normally changes to wiki files will come in batches, so a walk is good at that. If it's only one or two changes, then maybe we don't need a walk, but since the walk comes with all sorts of review stuff, probably a walk is fine. And just because its a walk doesn't mean it's not immediately (except the review delay, which I don't mind)."

So the shape above stands: the hook sets an unwalked page change aside, and the skill walks it, and the walk is run then and there. The same day he ruled the narrower case of a single new glossary term the other way ("I think a walk is overkill for something as simple as this"): a new project term is proposed to the user, and that rule now sits in CLAUDE.md's naming bullet (PR [Glossary: project terms are hyphenated phrases, abbreviations or slash names; the seat model's words become headwords; CLAUDE.md says so](https://github.com/nedschorus/nedschorus/pull/384)). Evidence that the hook is needed, from the same afternoon: two seats wrote or drafted glossary changes in parallel with no mechanism to notice each other, and merge-lane would not have either, since reviewers report nothing about prose under docs/.
