---
issue: "[Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31)"
---

# Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review

## What this captures

Design requirements for any future NC review system, extracted from the legacy system's review-gate defects during its wind-down (boss-directed extraction, 2026-07-27). **Dormant by design**: nothing here is built or scheduled. It wakes the day the boss first decides some class of work requires review; whoever designs that gate starts here instead of re-learning these from incidents.

## Part 1 — three mechanical checks a review gate owes

These are the cheap, directly-checkable facts about an approval artifact. The legacy gate checked none of them, and every one produced real false approvals:

1. **Compare who signed the approval to who authored the change.** The gate refuses an approval whose signer is the change's author; identity comes from something the system itself assigns — not from configuration the authoring environment can set. (Legacy: the gate never compared at all — an audit found 34 merged changes whose only approval was the author's own; and the first detection tool derived authorship from per-machine configuration, a signal any working copy could forge.)
2. **The approval names the exact version it reviewed; the gate refuses one that does not.** An approval without a version referent attests to nothing. This generalizes to every attestation: a test result must name the version and environment it ran against, or it is a claim without a referent. (Legacy: an approval with an unreadable version reference was silently treated as covering the newest version.)
3. **Parse statements, not quotations.** Text that quotes or displays an approval — for example inside a code block, while declining to approve — is not an approval. (Legacy: a reviewer showing what an approval looks like thereby granted one; an author's withdrawal of their own earlier objection was counted as reviewer presence.)

## Part 2 — what a gate cannot check, and the structural lever instead

A gate cannot verify that the reviewer understood the change, exercised hidden behaviors, or did a good job — and should not claim to; there is no obsessive-rechecking regress, because the gate verifies form and provenance, not content or judgment. The only lever on review quality is structural: the author and the checker are different parties, and for consequential changes different kinds of party — the two AI runtimes miss different things, and cross-runtime diversity was the one reliable decorrelator in the commissioned multi-agent research.

## Part 3 — represent expectations that change after an approval

Approvals record which version of the files they reviewed; nothing records which version of the requirements they reviewed against. When a ruling changes what a piece of work must contain and the files themselves do not move, every approval still reads current and the system reports ready-to-merge on work that no longer qualifies. A review system needs a way to record "the expectations changed after this approval," distinct from "the files changed." (Legacy specimen: an approval posted three days before a ruling kept a change mergeable for five days after the ruling it no longer satisfied.)

## Part 4 — every state a sanctioned exit

If the review system has states (on-hold, blocked, approved), each needs a legitimate way out, usable by the party who entered it. (Legacy: a reviewer could put a change on hold but nothing could lift the hold, so the sanctioned workaround was recording an objection the reviewer did not hold — a false state in the audit record the system existed to keep.)

## Part 5 — the identity and versioning model (boss-ruled 2026-07-27)

- **Agent-authored changes are identified by session id** — assigned by the harness, unique, not settable by the identified party. A new or cleared context is a new session id (verified against documentation); persistence of the id across context compaction is believed true in both runtimes but is an UNVERIFIED premise — run the cheap probe (compact a scratch session, compare ids) before building on it. Record the runtime alongside the id.
- **A cleared context is a legitimately independent checker** against anchoring bias — it cannot see its own authoring reasoning. Cross-runtime review remains the stronger requirement for consequential changes, because same-model blind spots survive a context clear.
- **Human-authored changes:** one human exists; a constant name suffices until that changes.
- **Files:** identified by content SHA (the git-gatekeeper's content-digest identity already implements this).
- **External tools and platforms** (OS, Python, git, the database, libraries): not tracked — too many, and compatibility is not the code writer's job. Record an environment detail only where a specific attestation's validity turns on it.
- **Custom long-running components** (daemons, the communications layer): versioned, with the version askable at runtime — the component can report what version it is. (Legacy specimen: the two runtime fleets ran different communication timeouts for six days because a launcher silently overrode a server default and nothing could be asked what version it was running.)

## Review classes are an allowlist (boss-approved 2026-07-31)

- **Review is an allowlist.** A review class exists only where a defined review procedure exists — each class named alongside its procedure, both defined when the review system is built. No procedure, no class, no review.
- **Everything outside the allowlist checks in freely.** No review, no fail-closed escalation into a heavy class. Mechanical checks still apply to everything (the secret scan runs on every check-in regardless of path; the quality gate's checks fire where they apply). Rationale: a review nobody knows how to perform is theater, and the harmless-by-landing majority — records, backups, logs, media — lands as backup, which is part of what the repository is for.
- **Capability-by-landing types are allowlist members from day one.** The few types where landing itself grants execution or changes tool behavior (CI workflow files, consumed tool configs) are understood classes with procedures, never residents of "unknown."
- **Novelty gets visibility, not review.** The first occurrence of a never-before-seen file type produces one flag line at the walk — remind-tier, non-blocking — so the allowlist grows when something new deserves a procedure.
- **Motivating specimen (credit: code-reviewer, nedlern, 2026-07-28):** the legacy classifier had no records tier, so byte-preserved walk ledgers (`tasks/sessions/*.md`) fell through to the heaviest class ("non-doc, or unknown path; fail closed") and cost two full dual-runtime review legs during wind-down. Their design input — "a path-based classifier with no records tier costs two full legs on a walk ledger" — generalized to this allowlist requirement at the 2026-07-31 walk.

## Relations

- The git-gatekeeper's dormant review-evidence growth point is where Part 1 attaches when a class is gated: https://github.com/nedschorus/nedschorus/issues/3
- The multi-agent research behind the cross-runtime lever: https://github.com/nedschorus/nedschorus/issues/26

## Close condition

Closes when NC's first review gate is designed with these requirements dispositioned (adopted or rejected with reasons), or when the boss rules NC will not build review gates.

—
Session: 3b576242-213e-43a2-bd16-80a1a36f67e7 (new-vp)
Requirement added 2026-07-31: session b7c09142 (new-vp)


## The instruction-file reviewed class (boss-ruled 2026-08-04)

The first designated class under this allowlist: instruction-bearing text — each project's CLAUDE.md and every agent's own CLAUDE.md-like file, skills (bodies AND their prompt templates, the most leveraged text in the system), additional system prompts (injected standing instructions: ignition prompts, agent definitions), and the wiki, on every move-in, addition, and change (the closest-to-canonical surface).

Procedure: criticize freely — reviewers are pointed at this class deliberately, never granted immunity from it. The responsible author drafts at a DRAFT path, never by editing the live file (each agent drafts its own file's changes; anyone may draft project-file proposals). The boss walks every update — verbatim before-and-after wording, one change per turn — and the approved change lands through the gate with the approval evidence. Invariant: a live class file matches its last approved version at all times except the moment of an approved landing.

Guards:
1. Gate evidence: a check-in touching the class requires walked-approval evidence — this designation activates the git-gatekeeper design's dormant Gate-evidence growth point.
2. In-session tamper revert: a post-tool hook SHA-compares live class files against last-approved and reverts-plus-errors on unapproved change (the legacy-proven design); built when hooks exist, boot era. Founding-window guard until then: the boss watches every landing.

   **Still unbuilt, and the interim guard has a measured hole (2026-08-24).** What exists today is `.claude/hooks/instruction-file-guard.py`, a **PreToolUse** hook whose matcher is `Edit|Write|NotebookEdit`. It does not fire on `Bash`. Sessions operating under bypass-permissions are instructed to prefer heredocs and `sed` over the Edit and Write tools, so an agent following its own operating instructions routes around the guard without ever seeing it. Specimen: roughly 60 lines of credential reference material accumulated in a seat's `CLAUDE.local.md` on 2026-08-24 before the user noticed; no evasion was intended or required.

   **Do not fix this by widening the matcher to `Bash`.** A Bash command's writes cannot be predicted before it runs — redirection, `sed -i`, `tee`, a python heredoc, a script three layers down. The legacy system tried a command parser for exactly this, deleted it, and recorded the conclusion in its replacement's header: stop predicting, start detecting. Its post-tool guard reverts the change and teaches the actor, on the model that version control already photographs every tracked file for free, so comparing after each tool call costs nothing.

   **Two build decisions this design still owes an answer to.** First, the baseline: for tracked files version control *is* the last-approved copy and the revert is a checkout, but `CLAUDE.local.md` is machine-local and gitignored, so it needs its own stored copy — refreshed at session start and after each approved landing. Second, the protected set. The legacy system kept it deliberately minimal: its `CLAUDE.md`, which auto-pushed to main **unreviewed**, plus the enforcement plumbing itself (settings file, hooks directory) on the reasoning that an agent able to edit the enforcer can disable it. That first rationale does not transfer — nothing reaches this project's `main` unreviewed — which inverts the priority here: **the file with no gate at all is `CLAUDE.local.md`**, gitignored, machine-local, never reviewed by anyone. The enforcement plumbing still earns a gate, because disabling it takes effect in-session, long before any review.
3. Micro-testing: contested or consequential wording changes are measured (old / candidate / no-guidance control, fresh contexts, repeated runs) before adoption; judgment landings by the context-holder remain legitimate.
4. Provenance: rulings dated inline where they bind; landing commits name what was walked; any copy of a class file outside its home declares its canonical source and legitimate differences, and re-syncs when the canonical changes.

Named-adjacent and deliberately separate (boss, same date): wiki staleness — pages drifting against a changing world while unedited — is a different problem, uncommissioned here.
