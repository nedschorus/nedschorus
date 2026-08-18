# Slice 6, the review-evidence check — designed, then ruled not built

Issue: [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3) · Instruction-file class: [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31) · Specification: [`git-gatekeeper-design.md`](../cross-project/git-gatekeeper-design.md) · Build order: [`3-git-gatekeeper-build-slice-plan.md`](3-git-gatekeeper-build-slice-plan.md)

**The decision, user-ruled 2026-08-17: slice 6 — the review-evidence check — is not built, and no walked-approval evidence format is adopted.** This document records why, what was designed before being declined, and what replaces it, so a future reader can act on the decision, or reopen it against evidence, without recovering the conversation that produced it.

Terms used below, defined here because this document is meant to stand alone. **The gate** is `scripts/git-gatekeeper.py`, the program through which changes reach `main`. **The privileged lane** is the gate running with the project's one `main`-capable credential, invoked through a sudoers rule as a dedicated Unix user — the specification's C2. Activating it is what "activation" means throughout. **`choirmaster`** was an agent seat, now retired; sessions are named by the hex id the harness assigns. **Break-glass** is the specification's C5: a password-prompted escape for a check-in the gate wrongly refuses.

## What slice 6 was going to be

*Walked approval* is the user's approval given item by item rather than as one yes to a bundle. It is recorded today by quoting his words into `.walk-approved` at the repository root, where [`.claude/hooks/instruction-file-guard.py`](../../.claude/hooks/instruction-file-guard.py) reads it, **deletes it**, and on that basis permits one write to a protected file. The marker is spent by the write it authorizes, so nothing survives to a later check-in.

Slice 6 would have turned approval into an artifact the gate could check at check-in: a field on the check-in request carrying the approval, verified before an instruction-bearing change reached `main`.

It was scheduled on 2026-08-10 as a prerequisite of activation, on the reasoning that the deployed root-owned copy of the gate updates itself from `main`, so an unapproved change reaching `scripts/git-gatekeeper.py` on `main` would become the running gate.

## Why it is not built

**The threat it defended against is not evidenced.** The design assumed a forgery risk: an agent fabricating the user's approval to land a change he never saw. Before adopting it, that assumption was tested against the project's record rather than argued.

Method, run on both machines the project uses: every `*.jsonl` session transcript under `~/.claude/projects/` searched for writes of the `.walk-approved` marker — both as tool calls and as shell commands, which a tool-call-only search misses — and for the guard's deny message. Each marker's text was compared against the user's own turns, across all sessions rather than only the one containing the write, because session recycling routinely leaves the approving words in an earlier transcript.

Corpus: 360 transcripts, 407 MB (128 files on the Ubuntu box, 232 on the user's Mac, where the walk machinery mostly runs).

Findings:

- **61 marker writes exist** — 59 through tool calls, 2 through the shell.
- **Zero fabrications.** No marker records an approval the user did not give. Four initially unmatched cases were single-word approvals ("approved", "y", "merge") below the matching method's four-word resolution, and each was confirmed against an exact user turn in its own transcript.
- The guard's deny message appears in 12 box transcripts, so agents do attempt instruction-file edits and are stopped at those tool calls. None escalated into an invented approval. This count bounds tool calls, not agents: the same agent could proceed by shell, which the guard does not see.

**One defect class was found, and it recurred.** Twice, a marker mixed the user's words with an agent's framing and marked neither:

- **2026-08-12**, session `ea663864`, resolving a `CLAUDE.md` merge conflict. The guard blocked the edit; the agent asked for approval through the multiple-choice question tool; the user selected an option. Having a click rather than words, the agent wrote a summary of its own proposal into the marker, and the change landed.
- **2026-08-15**, a memory approval. The first sentence is the user's verbatim words; the second is an agent paraphrase folded into the quotation, matching no user turn.

Both approvals were genuine. What failed was the record's ability to show whose words it held — [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31) Part 1 check 3's failure class (a statement *about* an approval standing in for the approval), reached by accident rather than malice.

**The fix for that is a labelling habit, and it is deliberately not being built into anything (user-ruled 2026-08-17).** Writing a marker so that the user's verbatim words are marked as his and the agent's framing as the agent's would have prevented both incidents, at no cost. It is recorded here as a practice, not a mechanism: the marker file is consumed and deleted by the write it authorizes, so it is not a durable record at all — the durable trace is the transcript — and the entire cost of leaving this alone is that a later auditor must do some work to separate the two voices, which is exactly the work the 2026-08-17 audit did in an afternoon. Neither incident is the guard failing a promise: it is this project's own hook (user-walked 2026-08-07, nedschorus#45), and its docstring states plainly that it is a soft block whose value is a visible quoted approval, "not tamper-proofing."

**The benefit in ordinary use is thin, and the cost is real.** When the user tells an agent to submit a change, his approval already *is* the instruction, so an evidence field would record what has already happened rather than prevent anything. Its cost is that instruction-bearing changes on the gated paths could not land unattended. The user judged the trade not worth taking. The deciding standard: machinery is not built merely because an earlier ruling implied it.

## What was designed before being declined

Recorded so a reopening starts from the analysis rather than from zero — including the places the analysis was wrong, which matter more than the places it was right. None of it is built.

- **Binding to the content digest.** The evidence would name the check-in's digest, computed by the program and not supplied by the caller, so an edit made after approval would produce a different digest and fail to match. **Correction:** this defeats post-approval edits only. It does nothing against fabrication, because an agent can make its edit first, write an invented approval, and let the program digest its own content — the evidence then verifies perfectly. The draft claimed tampering "would not need detecting"; that claim was wrong as written.
- **Shape, not prose.** The gate would check presence, form, and digest match, never reading text to decide whether it means yes. Free-prose matching fails on quoted approvals: a document displaying an example approval reads as one.
- **An honest non-verbal marker**, for approvals that did not arrive as words. **Correction:** this removes the agent's *excuse* for inventing prose, not the *slot*. A form-only check cannot distinguish a true non-verbal claim from a false one, nor a verbatim quote from invented text in the same field. It was described in the draft as the direct fix for the recorded defect; it is not.
- **Path set.** Decided during the design and made moot by the ruling: evidence would have been required for `CLAUDE.md`, `CLAUDE.local.md`, `.claude/`, and `scripts/git-gatekeeper.py`, and not for `docs/wiki/` or the seat briefs under `docs/agents/` — instruction-bearing under the 2026-08-04 designation (recorded on nedschorus#31: CLAUDE.md files, agent identity files, skills with their prompt templates, injected system prompts, and the wiki) but edited routinely, with no incident record, and deliberately kept cheap to edit. Note that `.claude/` is not uniform: the guard itself exempts `.claude/worktrees/` and `.claude/jobs/`, so a path set naming `.claude/` wholesale would not have matched the guard's live scope. The dominant cost of listing a path is the approval it forces on every change to that path, not the request field.
- **An owner-signed rung for the gate's own source**, considered and dropped: an agent posts the proposal and its digest as an issue comment, the user reacts from his own account, and the gate asks GitHub whose account reacted. **Two corrections.** The agent owns the comment and can edit it after the reaction lands, while the reaction stays attached — so asking who reacted does not establish what they reacted to. And "unforgeable" assumed no agent ever holds a credential authenticated as the user — which is false here: the Mac-side agent's `gh` is authenticated as `nedlern`, an org owner, so an agent on that machine could post the owner's reaction. The rung would have secured nothing against the one agent best placed to defeat it.

## What replaces it

The exposure C2 names is real, but it does not exist today and activation is what would create it. Today every ordinary change reaches `main` through a pull request the user's Mac-side agent reviews before merge, so the gate's source is read by a party other than its author. (Not an absolute: the owner can push directly, and break-glass exists. The point is that the routine path carries review.) A live gate, by contrast, requires no review of what passes through it.

**Ruled 2026-08-17 and built with this document — the gate refuses its own source.** A check-in whose declared paths include `scripts/git-gatekeeper.py` refuses with `gatekeeper-source-refused`, whose next action names the pull-request lane. The gate's source therefore keeps reaching `main` the reviewed way. This holds even once the gate can review, and that is the stronger reason for it: a reviewing gate asked to admit a change to its own source would be reviewing the code that performs the review. Keeping that path out of its own door removes the self-reference. Acceptance test T13, in the specification's index.

**Ruled 2026-08-17 and OWED — the push allow-list.** Main's push allow-list must name the user's own account alongside the gatekeeper account, because merging a pull request is itself a push to `main`: an allow-list naming the gatekeeper account alone would close the pull-request lane for everyone, leaving the gate's source refused by the gate and unmergeable by pull request. **This is not applied.** It is a GitHub change requiring an org owner — the user's to make — and it ships with the credential work, not with this document. Stated honestly rather than softened: listing the owner does concede a standing direct-push path that bypasses review, which is not the same as his existing power to alter branch protection (that takes a separate, visible configuration act). The trade was accepted because the single-door property was always aimed at agents, and closing the pull-request lane would break the replacement above.

**What now gates activation**, the question slice 6's removal left open: two things. The credential work, and **review-at-the-gate** — the user ruled on 2026-08-17 that the gate is not activated until the path itself can review what passes through it. His sequencing, recorded here because it is otherwise undocumented: get every change through a single path first, then attach review, deployment and fuller testing to that path, plausibly as a script invoking a heavy Claude and Codex review. The specification already reserves the gate as the growth point where checks attach, and [nedschorus#63](https://github.com/nedschorus/nedschorus/issues/63) holds the open question of which mechanical checks belong there.

The break-glass alternative — routing the gate's own source through the gate behind a password prompt — was declined, because it would put a per-change cost on the user for every gate change.

## Considered and rejected: read-only file modes

Raised by the user during the design and withdrawn by him the same day, recorded so it is not re-proposed.

Its appeal is real: the instruction-file guard is a harness hook wired on the Edit, Write and NotebookEdit tool calls, so a write arriving through a shell command (`sed -i` on `CLAUDE.md`) passes it unseen, while a mode bit is enforced by the kernel whichever tool writes.

It fails because **git does not carry the read-only bit.** Git records the executable bit and nothing else of a file's permissions, so a file made read-only in one checkout is writable in any fresh clone unless something reapplies it. The mode protects a working copy, not the project — and the gate compares content only, so a permissions-only change refuses as `unchanged-path` (its "nothing differs" refusal), meaning mode changes cannot travel through the gate either. Two further costs: git rewrites these files during pull, merge and checkout, and while the exact behaviour varies by code path and filesystem, a read-only `CLAUDE.md` can turn an ordinary merge conflict into a confusing failure — and the project's one real marker incident was exactly a `CLAUDE.md` merge. And the bit is not a boundary: an agent can `chmod +w`, or replace the file by rename in a writable directory without ever writing through the read-only inode.

## What would reopen this

The ruling rests on an empirical claim with a stated method, so the same method can falsify it. Reopen if a marker is ever found recording an approval the user did not give.

**How to run it, including the trap.** Search the session transcripts on both machines for `.walk-approved` writes — tool calls and shell commands both — and compare each marker's text against the user's own turns across all sessions, not only the one containing the write. Then note what the comparison cannot tell you: **an unmatched marker is not evidence of fabrication.** Both recorded incidents produced markers with no matching user text, and both approvals were real — one was a click, one was a paraphrase around genuine words. An unmatched marker means only that the check must continue by hand, asking whether an approval happened at all, which is what resolved every case in the 2026-08-17 audit.

The in-session guard is unaffected by this ruling and remains the protection in force for instruction files — a soft block, by its own description, which shell writes bypass and whose path list carries exemptions. Changing it is an instruction-class change and takes its own walked approval.
