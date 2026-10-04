---
issue: "[Build the explain skill: re-say a message for a reader who does not carry the session's context — the draft exists, and the hold's reason expired](https://github.com/nedschorus/nedschorus/issues/603)"
---

# The explain skill — GHI-MD for issue [Build the explain skill: re-say a message for a reader who does not carry the session's context — the draft exists, and the hold's reason expired](https://github.com/nedschorus/nedschorus/issues/603)

The /explain skill is installed on main; the Outcome section says what was built and where it lives. Every section after the Outcome is the design record as written on 2026-09-21, kept so the reasons for the skill's design stay findable. Where the record says "today", "current" or "not yet", it means 2026-09-21. The cold read of this outcome edit corrected a few of its statements of fact in place. Where the record and the installed skill or its supporting file differ, the installed files are in force.

## Outcome

Times and dates in this section are UTC.

**Installed.** PR [The explain skill is installed, with the script that gives a draft reply its fresh read](https://github.com/nedschorus/nedschorus/pull/894) merged on 2026-10-02T04:12:37Z, after three review rounds:

- Round 1: the independent reviewer and merge-lane-2 both requested changes.
- Round 2: the independent reviewer approved the fix-round, and asked, without blocking the merge, for one more test case.
- Round 3: both approved one commit carrying that test case and two lines that the fresh-read script prints for the agent. The two lines had their own cold-read-fast-read, and the user approved their new wording.

What is on main:

- `.claude/skills/explain/SKILL.md`, the skill. Its check 13 has one fresh-reader read the agent's draft reply, a cold-read-fast-read, before the reply is sent; this document calls that read the fresh read. `/explain fast` skips the fresh read.
- `nc-systems/skills/explain/explain-how-to-write-an-identifier-instructions.md`, the skill's supporting file: the identifier table ruled on 2026-09-16, as the skill's reviews revised the table. Check 7 of the skill names the file.
- `nc-systems/skills/explain/explain-reply-cold-read-fast-read.py`, the script that runs the fresh read, with its test under `nc-systems/skills/explain/tests/`.
- The project glossary's line for /explain.

The sequence the 2026-09-16 walk ruled (see "The cold read is ruled, not open", below) was followed:

1. The identifier table was folded in.
2. The skill had two cold-read-full-runs. Their cold-read-records are `explain-skill-draft-2026-09-29-2` and, after the text was restructured on 2026-09-30 from 261 lines to 203, `SKILL-explain-skill-draft-2026-09-30-2`, both under `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/`.
3. The user read and approved the text, and ruled on both runs' findings, in the approval-walk explain-skill-draft-2026-09-29-2, which ran from 2026-09-29 to 2026-10-01; walk-minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/explain-skill-draft-2026-09-29-2-minutes.md`.
4. The skill was installed.

The walk-minutes of the 2026-09-16 walk, which the design record calls at risk, are in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/2026-09-16-merge-lane-sixteen-open-items-small-first-minutes.md`.

**Agents may use the skill.** An advisor's report of 2026-09-30 proposed installing the skill so that only the user could start it, and opening it to agents once eight of its first ten uses succeeded. Both proposals rested on the agent-seat merge-lane-backlog's misreading of a remark of the user's as a user-ruling. He corrected the misreading on 2026-09-30: "I did not rule that agents cant use explain. They can't use it because it's not built yet". So the skill is installed as a normal skill that agents can start, and the ten-use trial was dropped.

**One later change.** Check 7 of the skill said "that" used as a noun; the part of speech meant is pronoun, so the phrase became "that" used as a pronoun, in check 7 and in the pronoun bullet of the project's `CLAUDE.md`. The user approved both on 2026-10-01 in the approval-walk claude-md-sentences-the-pronoun-rule-catches-2026-10-01 (walk-minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/claude-md-sentences-the-pronoun-rule-catches-2026-10-01-minutes.md`), and PR [CLAUDE.md: name the noun in four sentences the pronoun rule catches, and call "that" a pronoun](https://github.com/nedschorus/nedschorus/pull/932) merged both on 2026-10-02.

**Two cases not pursued.** Two cases the 2026-09-16 walk left undecided, a process ID shown as evidence and a link to one section or line, are not in the supporting file and were not pursued; either is ruled when an agent is seen getting it wrong.

## Problem

The user reads agent messages cold. He works in other seats' terminals and arrives at one
without the context that session has been accumulating, so an explanation written by an agent
that knows what every term and number refers to routinely fails for the one reader it is
written for. He has typed some form of "I don't understand", "too much", or "explain assuming
zero context" thousands of times.

Nothing on main does this job today. `/walk-me-through` covers multi-part material presented item by item; it does not cover re-saying a single message that did not land. The drafting register for durable MDs (a register here is one kind of explanatory writing, with its own reader and rules, in the sense of the title of GHI [Clarity registers](https://github.com/nedschorus/nedschorus/issues/138)) is GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142), which is about documents, not about live explanation to the user.

## Why it was held, and why that reason no longer exists

Item 7 of the clarity-registers walk, 2026-08-22, ruled the skill HELD, recorded on GHI
[Clarity registers: explanations and drafted instruction text land without the user's repeated
corrections](https://github.com/nedschorus/nedschorus/issues/138):

> An "explain" skill for one-shot explanations: HELD (user-ruled 2026-08-22) — the output style makes the explaining register standing for every session and the walk skill covers multi-part material, so the skill would add only an invocation name; no observed failure remains post-style. Reopen condition: clarify-corrections still being typed at one-shot explanations in sessions running under the Zero-Context Explanation style — those failed explanations become the skill's design evidence.

Three things have happened to that reasoning, and together they are why this issue exists.

**The mechanism it deferred to lived on main for 28.8 hours.** PR [Zero-Context Explanation
output style, activated fleet-wide](https://github.com/nedschorus/nedschorus/pull/156) merged
2026-08-31T18:54:03Z. PR [Remove the Zero-Context Explanation output
style](https://github.com/nedschorus/nedschorus/pull/232) merged 2026-09-01T23:41:11Z. The
skill was held on 2026-08-22 in favour of a mechanism that had not yet landed and that then
survived a little over a day.

**The removal was right, and its reasoning argues for a skill.** A custom output style's text sits in the system prompt, is never repositioned, and so competes with everything newer as a session grows; the built-in Proactive and Concise styles compensate with a per-turn reminder that a custom style cannot declare, because the frontmatter schema is strict. PR [Remove the Zero-Context Explanation output style](https://github.com/nedschorus/nedschorus/pull/232) concludes that "A rule that must survive to turn 200 belongs in a hook that fires late or blocks, or in a test", not in a style file. A skill is nearer to that than a style: it is invoked, so its text arrives at the point of use instead of decaying in the system prompt. The 2026-08-22 ruling dismissed the skill as adding "only an invocation name" — but an invocation name delivers the skill's text at the point of use, which a style file cannot.

**The reopen condition can no longer fire, and the ancestor issue was closed for that reason.** The condition names failures observed "in sessions running under the Zero-Context Explanation style". No session can start under the style now that the style is off main. GHI [Clarity registers](https://github.com/nedschorus/nedschorus/issues/138) was closed not planned on 2026-09-21 on exactly this reasoning. So the hold has no live exit, and the job has no owner.

## Where the material lived, and why that was a problem

Resolved: this document put the draft and the table into the repository, and the 2026-09-16 walk-minutes are in the log-store (see Outcome).

Three documents matter here and **none of them is in git**. All three are untracked files in
one agent-seat's checkout on one machine:

| Document | Location | Size, mtime |
|---|---|---|
| The skill draft | `/Users/el/agents/merge-lane/docs/drafts/explain-skill-draft.md` | 3,194 bytes, 2026-09-15 16:50 |
| The ruled identifier table | `/Users/el/agents/merge-lane/docs/drafts/identifier-presentation-rules-draft.md` | 9,124 bytes, 2026-09-16 17:15 |
| The walk that ruled it | `/Users/el/agents/merge-lane/docs/walk/2026-09-16-merge-lane-sixteen-open-items-small-first-minutes.md` | 28,442 bytes, 2026-09-16 17:24 |

`docs/drafts/` holds the first two untracked; `docs/walk/` is gitignored at `.gitignore:32`. The walk record was never shipped to the log-store, and it is the only written record of the user's rulings at items 12, 14 and 15; the table draft also records item 13's. One `git clean -fdx` in that checkout destroys all three.

**That is why this document reproduces the draft in full, and the table in substance, rather than citing them.** Landing this GHI-MD puts their content into git for the first time.

An earlier pre-revision copy of the draft does survive elsewhere, frozen into a
cold-read-record by the fast read of 2026-09-15:
`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-15-explain-skill-draft/`.
That copy is **superseded** — the revision that answered the fast read came after it. Do not
build from it.

## The draft, 2026-09-15 post-revision

Reproduced verbatim. The installed skill, `.claude/skills/explain/SKILL.md`, supersedes it; the draft is kept as the design record and is not the text to work from.

```markdown
---
name: explain
description: Re-say what you just told the user, for a reader who does not carry this session's context. Use when the user types /explain, or says he does not understand, is confused, or asks what a term or a number refers to.
---

# Explain

The user reads your messages cold. He works in the terminals of other agents on
other machines, and arrives at yours without the context you have been
accumulating all session. When he cannot follow something you said, the cause is
almost never sentence length. Most often it is one of two things:

- **a project word used as though already defined** — slice, cell, drain, gate,
  head, seat;
- **a bare identifier cited as though he would recognise it** — #379, 40b5ee7,
  task #191.

Both are invisible to you while you write, because you know what they refer to.

## What to do

Find the message he is reacting to: your last one that was not a bare status
line. Do not defend it, do not apologise for it, and do not add to it.

1. **Answer the words first.** List the project words and identifiers that his
   understanding depends on, and say what each one is, one clause each: "#379 is
   a pull request. A slice is one numbered chunk of a build." Cover all of them,
   not only the ones he asked about — he asked about the ones he noticed. If a
   definition needs a second word he may not know, define that one too, in the
   same clause, and stop there rather than chasing a third.
2. **Then retell the point concretely.** Prefer one particular thing happening to
   one particular file, run or branch: what happens, in order, and how it ends. If
   what you said was a choice or a state rather than a sequence, give the smallest
   real case that shows it — something that would be true or false, work or break.
   Invent nothing to make a story: an accurate flat answer beats a fluent
   fictional one.
3. **Stop.** Same content, no new content.

## What not to do

- **Do not add information.** If you are introducing something the original
  message did not contain, you have answered a question he did not ask. The
  definitions in step 1 are the exception.
- **Do not define a project word with other project words.**
- **Do not restate at the same level, only longer.** Repetition is not
  explanation.

## When he aims it

`/explain <thing>` — and equally "what is X?" or "what does Y mean?" in ordinary
words — narrows this to that one thing, whether it is a word, a number or a
sentence. Define or explain the thing itself, and retell the surrounding point
only if the thing makes no sense without it.

## When you cannot tell what was unclear

Say that you are guessing, name the two or three things you think were opaque,
and explain those. Then say in one line what else you could unpack, and carry on
— do not ask him which part confused him and then wait. He is usually reading
across several agents at once, so a question costs him a round trip that a guess
does not.

If the confusion was not a word or a number at all — a step that does not follow,
a claim resting on something you never said — name that instead and repair it.
The two causes above are the common ones, not the only ones.
```

## What the fast read raised, and what the revision already did

A cold-read-fast-read ran against the pre-revision draft on 2026-09-15 and raised seven
defects. The revision above answered them the same day. They are recorded here so nobody
re-solves them:

| The fast read's finding | How the revision answered it |
|---|---|
| The purpose-before-mechanism rule had no place to live between steps 1 and 2 | Cut, not patched |
| `seat` used operatively while listed as an example of the failure the draft forbids | Stopped using it — "the terminals of other agents on other machines" |
| Define *all* the terms contradicted guess *one or two* | One procedure now |
| Confusion claimed to be *only* terms or identifiers | "the common ones, not the only ones", with the escape hatch for a step that does not follow |
| "Offer the rest" read as asking a question the draft forbids three lines later | "say in one line what else you could unpack, and carry on" |
| "Same content, different footing" — an undefined metaphor | Cut; now "Same content, no new content" |
| Step 2 forced a story even where the subject was a choice or a state | "the smallest real case", plus "an accurate flat answer beats a fluent fictional one" |

One change the revising agent made on its own judgement and flagged for the user to
overrule: step 2's retreat from "a story about a file, run or branch" to "the smallest real
case". It has not been overruled.

## The identifier table — ruled 2026-09-16, now folded in

The table is now the skill's supporting file, `nc-systems/skills/explain/explain-how-to-write-an-identifier-instructions.md`. The user ruled on its five rows that needed a judgement at walk items 13.1 through 13.3 on 2026-09-16, dropping the first and approving the other four; the remaining rows were not ruled one by one. The draft above predates the table by a day and does not contain it. Reproduced in substance, condensed, because on 2026-09-21 its only copy was untracked. Where this table and the installed file differ, the installed file is in force: the reviews of the skill changed several rows, for example a GitHub issue is written `GHI` with its title and link, not `issue #386`.

His requirement, in his own words:

> "I hate it when agents show me IDs instead of clear titles, names and types. Is #139 a
> task, a PR, a GHI, who knows. Is 123129743 a session ID, a wtf. ... They should have a
> useful title or name. If they are actual files or things that can be opened they should be
> clickable links. Bare identifiers are useless to humans, but any identifier that is not
> clear is also painful."

The measurements below come from two transcript surveys of agent-to-user prose, made for the table on 2026-09-16: 8,168 messages across merge-lane, fleet-restart-at-login, reboot-test and reboot-test-2, and 6,556 across MD-skills, cold-read-research, mac-ubuntu-bridge, git-infra and the reference checkout.

**Two failure modes, not one.** *Bare* is an identifier with no title. *Ambiguous* is an
identifier whose type the reader cannot determine — and that is the worse one, measured: of
359 distinct `#N` values appearing with a type word, 184 (51%) are used for two or more
different types. `#116` is a pull request, an issue, a walk item and a task. `#N` occurs
6,492 times in one transcript corpus and 3,848 in the other, bare in 48% and 62%.

**The rule, in one sentence:** every identifier shown to the user carries a type word and a
human name; and where the thing can be opened, the identifier is a link.

### Group A — openable, and a title is cheap: type + title + link

| Kind | Present as |
|---|---|
| Pull request | the word `PR`, then the title as the link text, then the URL — the number may appear but is never the only identifier |
| GitHub issue | `issue #386, "<title>"` with its URL |
| Commit | ``commit `89e9dfe` ("<subject line>")`` with its URL |
| Repository file | "<what it is>" as the link text, on a `file://` absolute path |
| GHI-MD pair document | already carries number, type and slug; link it |
| Skill | ``/explain`` — "<what it does>", linked to its `SKILL.md` |
| Wiki page | "<page title>", linked |
| Walk file | "<walk name>", linked |

The user's words at item 13.1: *"I'm fine with PR for pull request. The numbers mean almost
nothing to me. The titles of the PRs are usefull, as are clickable links I can click on to
open."*

Measured gaps this closes: pull requests are named by number in about 2,500 messages and
linked in 125. Commit hashes are named in 632 messages and linked in **zero**. About 85% of
file-path mentions are not clickable. Titles are cheap in every row — `gh pr view N --json
title`, `git log -1 --format=%s <sha>`, or the file's own first heading.

### Group B — a title exists, nothing to open: type + title, no link

| Kind | Present as |
|---|---|
| Native task | `task #244, "<subject>"` |
| Walk item | `item 4 of 10 of the "<walk name>" walk — "<item heading>"` — name WHICH walk |
| Finding in a report | `finding 3 of "<which report>" — "<one-line summary>"` |
| Row in a table | `row 19 of "<which table>" — "<the row's own text>"` |
| Ruling date | `ruled 2026-09-15 at "<which walk or file>"` |

Three measurements from that survey worth keeping: tasks have the worst
openability-to-frequency ratio in the fleet, 409 mentions and nothing openable; of 173
explicit "ruled `<date>`" citations **not one resolves** to a transcript, minutes file or
URL; and `item N of M` appears in 13.3% of messages while a walk name appears in 2.4%, with
two walks often live at once.

### Group C — type is clear, no human title exists

| Kind | Present as |
|---|---|
| Review | never the bare id — a link on its pull request's title, ending `#pullrequestreview-<id>` |
| Comment | the same shape, `#issuecomment-<id>` or `#discussion_r<id>` |
| Branch | `origin/<name>` — the prefix types it |
| Model or runtime | the vendor model id: `gpt-5.6-luna`, `gpt-6-astra`, Gemini 3.8 for "gem38". A nickname no record resolves is written "the model nicknamed <x>" |

### Group D — do not show at all

Not "format better" — omit. Background shell ids; subagent ids (a human description sits in
the sibling metadata, the one exception being a worktree cleanup where the id *is* the thing
being deleted); subagent task-output paths, which rot; scratchpad paths;
epoch-millisecond timestamps; harness worktree branch names; `.partial` and dot-prefixed
in-progress files; and the `pull-request-review-write` probe marker, ruled out 2026-09-15 and
still being written into permanent GitHub review records.

Left to the user: **process ids**, useless as identity but used in the transcripts as
evidence ("stale lock is confirmed stale (PID 1679703, not alive)"), where the number is the
proof.

A clean negative worth recording: the harness's own internal ids — `toolu_*`, `msg_*` — leak
zero times in either corpus. The leaks are the project's own.

### Four decisions the walk settled

1. **The planned-PR ordinal is DROPPED.** A planned pull request has no link, so it is named
   by what it will do, never by an ordinal.
2. **Glossary headwords are NOT marked.** A defined term already carries a spottable form,
   and the glossary now defines a word only where its project meaning is hard to guess.
3. **Seat name versus session name:** always write the type word — "the merge-lane seat",
   "session merge-lane-51 of the merge-lane seat", never the bare name. No checker unless the
   confusion recurs in messages.
4. **Model nicknames:** write the vendor model id.

Not ruled by that walk: `§174`, a section or line number whose link points at the whole
document.

## Where the rule lives — settled

The table's own closing question was whether a rule this proactive belongs somewhere that
binds always, since `/explain` is reactive and fires only after the user is already
confused. Walk items 14 and 15 answered it, and both landed:

- `/Users/el/.claude/CLAUDE.md` gained the one-bullet form as its third bullet (item 14).
- The project's `CLAUDE.md` gained the same bullet without its ruling-date tail (item 15), through a pull request authored by the merge account and approved by an independent reviewer. It is in `CLAUDE.md` on main, with "type word" since renamed to "link-type" and then, on 2026-09-22, to "ID-type".

**The full table still goes into this skill either way** — that was stated in the walk item itself, and it is done: the table is the skill's supporting file (see Outcome). The one-bullet form in the two instruction files is the always-on summary; the table is the reference.

## The cold read is ruled, not open

Walk item 12, 2026-09-16, asked whether this draft needs the cold-read-full-run of six
reviewers or whether the fast read plus the user's own reading suffices. The question had
been asked four times across earlier sessions without an answer. **The user answered "y": no
exception.** The minutes record the outcome as "`docs/drafts/explain-skill-draft.md` takes
the cold-read-full-run once items 13 to 15's identifier rulings are folded in."

So the sequence is fixed and not a matter of judgement: fold the table in, then run the full
six-cell cold read, then the user reads it, then it is installed.

## Design evidence, observed 2026-09-21

The 2026-08-22 hold asked for failed one-shot explanations as the skill's design evidence. Two were produced at the merge-lane-backlog seat during its approval-walk merge-lane-backlog-triage-result, with the project's output style removed from main:

1. Given a one-shot explanation of a closed task, the user replied "confused. explain 2". The retelling succeeded, and it succeeded by doing the draft's step 2 — one concrete case, told from the failure it guards against — while skipping its step 1 entirely: it never defined the terms and identifiers first. The draft predicts that omission and forbids it.
2. Earlier in the same walk, after a recommendation had been stated plainly, the user asked "what do you want to do and why?" — the same class, a message that did not land as written.

## Next action

None for the skill, which is installed (see Outcome). When this outcome edit is on main, the agent-seat merge-lane-backlog reruns edit-GHI on this file and closes the issue as completed.

## Search receipts

- `scripts/ghi-info-ask.py` with `--include-closed`, asked 2026-09-21 for any issue covering an
  explain skill for one-shot explanations: returned GHI [Clarity
  registers](https://github.com/nedschorus/nedschorus/issues/138) (closed not planned), GHI
  [Build draft-md](https://github.com/nedschorus/nedschorus/issues/142) and GHI [Runtime-behavior
  research bundle](https://github.com/nedschorus/nedschorus/issues/29), and stated that no issue
  proposes an explain skill as a live candidate.
- `gh issue list --state all --limit 200`, titles scanned for `explain`, `clarity`,
  `identifier`: only GHI [Clarity registers](https://github.com/nedschorus/nedschorus/issues/138).
- `git log --all` and `git grep` across every branch for `explain-skill` and `explain skill`,
  2026-09-21: no such file in this repository, on any branch.
- `ls .claude/skills/` on main, 2026-09-21: `cold-read`, `ghi-write`, `handoff`,
  `pull-request-review-write`, `sanity-check`, `walk-me-through`. No `explain`.

## Relations

- GHI [Clarity registers: explanations and drafted instruction text land without the user's
  repeated corrections](https://github.com/nedschorus/nedschorus/issues/138) — the ancestor; held
  this skill on 2026-08-22 and closed not planned on 2026-09-21.
- GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled
  2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142) — the sibling register, for
  drafted MDs rather than live explanation.
- GHI [overview-write skill: how an overview of a system is written and checked before it
  lands](https://github.com/nedschorus/nedschorus/issues/168) — the third register, for
  explaining a whole system to a reader who must act on it.
