---
status: working plan
---

# nedschorus Boot-Up Plan

The preparation the boss + new-vp (the old system's VP agent) do to bring choirmaster into existence. The boss works one step at a time; this is the order of steps with what each produces. The first task choirmaster will run is deliberately the LAST step. This is the founding pair's workflow document — the specifications it points at are written for zero-context readers; this file is written for us.

## Standing decisions (all boss-ruled, 2026-07-20/21; provenance in git history and the founding transcripts)

- Fresh repo `~/Projects/nedschorus` (live: https://github.com/nedschorus/nedschorus — owned by the `nedschorus` organization since 2026-07-21; the old `nedlern/nedschorus` URL redirects). The old project is the QUARRY: read-only reference; every import crosses the entry checkpoint (`entry-manifest.md`: quarry SHA + purpose + date, same commit — enforced as a day-one throat check).
- Primary agent: **choirmaster** (Claude runtime), running with bypass permissions (`.claude/settings.json` → `permissions.defaultMode: bypassPermissions`).
- **The single-writer throat** is the permanent check-in architecture — one identity (choirmaster's credential) pushes to main; all checks live at the throat from day one. Specification: [fast-pr-to-prod-design.md](fast-pr-to-prod-design.md) ([nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3)).
- **Throat rulings 2026-07-21 (all in the specification):** the account layout, org form, applied LIVE — the repo lives in the `nedschorus` organization; both boss accounts are org owners (`NedLern` — also the machine/agent credential and the only permitted pusher — and `NedLerner`, settings and emergency power, no push); branch protection on `main` with enforce-admins, force-push and deletion blocked; the boss never commits directly. Check-table additions adopted from the prior-art cross-check: exact-tree validation, trailer-schema provenance record, declared-vs-actual paths, replay protection, and the executable quarry-import command (one-transaction copy + digests + manifest-line write; one component per landing).
- **The publishing program** ([nedschorus#4](https://github.com/nedschorus/nedschorus/issues/4)): strategy admitted and walked in full; `nedschorus.com` is **registered** (the boss, 2026-07-21); every further external action — account, site, first post — waits on a per-action go; the first build step is deliberately unpicked while the boss deliberates.
- **The prior-art cross-check is complete** — two adversarial passes over the nine founding patterns; every borrowing's disposition is recorded on closed [nedschorus#5](https://github.com/nedschorus/nedschorus/issues/5), and the full reports are git-history-recoverable from there (the doc was temporary reference, disposed at close). Net: throat/ladder/python-first are established practice (validating, not novel); the handoff governance bundle and quarry-with-manifest survived as unmatched compositions; handoff-quality instrumentation deferred low-priority with raise-triggers ([nedschorus#6](https://github.com/nedschorus/nedschorus/issues/6)).
- **The handoff system** — naked-writer drafts, corrected by the session agent; numbered files + committed transcripts; auto/vet scrub modes. Specification: [fast-handoff-design.md](fast-handoff-design.md) ([nedschorus#2](https://github.com/nedschorus/nedschorus/issues/2)). Skill named `fast-handoff` until entry, then `handoff`.
- **The Codex companion arrives early** — right after choirmaster's boot test passes, in advisory mode: it drafts freely in its own clone, never pushes, no git identity ever; its work lands via promotion (attribution by provenance stamp). Two channels compose for the pair: **MCP as the call channel, one-off OR threaded** — each CLI exposes itself as an MCP server (Codex-direction measured 2026-07-21; Claude-direction via `claude mcp serve`, unprobed); a fresh call spawns a new instance (right for consults, reviews, ask-both-heads-the-same-thing), and a THREAD sustains a real multi-turn discussion with context intact (Codex: `codex-reply` with a thread id; Claude: `claude -p --resume <session-id>` — whether resume keeps or forks the session id is unprobed). Threading reaches the conversation, not the live terminal: it neither displays in nor wakes a peer's interactive window. **Mini-comms (a second two-log-file bridge)** therefore keeps only what it is uniquely good at: asynchronous, boss-readable coordination that survives either side's death. The parallel-proposal workbench UI is a recorded future candidate.
- 100% manual edit-production pipeline; automation earned rung by rung (manual → script-you-run → automation). Python liberally, and light: python over prompts, python over bash; smallness kept by re-derivation, the single door, and earned complexity — not by the language.
- Kernel lines settled so far: the handoff pickup line; the transcript-archive pointer; commit-as-you-go with session id in every commit message; the zero-context-reader writing rule for durable artifacts (delivered inside every writing skill too).
- The boss's review queue is **issues labeled `boss-review`** — same format as all issues, full-context walkable bodies, non-blocking by rule, no title/filename markers (the label is the single authority). The scrub step of each handoff states the open count.
- Boot-pack validation is boot-testing the delta with genuinely fresh subagents, not review alone. A fresh subagent's context floor (CLAUDE.md + prompt) is the measured boot state of every future reader.

## Project organization

Three committed homes plus the shared place — no `docs/working/` ever exists:

1. **`docs/wiki/`** — permanent truth (Obsidian vault; `.obsidian/` gitignored, matching the quarry's practice — config is per-vault, so the old wiki cannot be affected).
2. **`docs/issues/<n>-<slug>.md`** — working material, one document per substantial issue; header carries the issue link only (the issue's open/closed state is the sole status authority); at issue close the same commit disposes the document (delete, or promote to the wiki with `design-as-of:` frontmatter and the production-is-SSOT line). The choice between them (boss-ruled 2026-07-21): promote only distilled standing knowledge; an evidence archive or reference file DELETES, with the extracted decisions memorialized in their governing documents and a `git show <sha>:<path>` recovery pointer on the closing issue.
3. **`handoff/`** — the numbered handoff series with transcripts.
4. **`docs/cross-project/`** — artifacts shared with the old system, including the founding documents (migrated here from the quarry, frozen there at 78ed90f0).

**The MD-GHI pair:** a request for a durable MD IS a request for a doc + issue pair (the boss's trigger word: "memorialize"). `md-write` searches existing pairs first, then disposes NEW / REVISE (default on subject match) / REPLACE (supersede, old issue closed same commit) / REMOVE; ambiguity goes to the `boss-review` queue, never blocks. Session provenance: MDs via commit messages; issues via a footer line.

**Subsystem structure:** co-locate when free; subsystem subdirectories inside pinned roots at the second file; the subsystem token verbatim in every name (one grep returns the whole subsystem); a hygiene script (a throat check) verifies tokens, subdirectory moves, and test markers — placement itself stays the writer's judgment; a never-seen token routes to `boss-review`.

## The steps

**1. Assemble the starting skills — FIVE:** d-review and walk-me-through (quarry trims through the checkpoint); the handoff skill; `ghi-write` (issue-only artifacts) and `md-write` (the pair), each small, embedding the zero-context-reader rule with the composed-in three-test check (subject identifiable; why stated; actionable without the conversation). The companion later gets `ghi-write`/`md-write` as Codex-side skills. Each skill build DRAINS any staged lessons that name it from the old system's memory store (skills are the trigger-bearing surface; memories only stage lessons whose home doesn't exist yet) — walk-me-through drains the three 2026-07-21 walk lessons: purpose-before-mechanism ordering for decision items; capture-the-decision-never-the-meeting; and the boss's positive length rule, in place of any not-shorter phrasing — "The target is complete and clear. Length is not the measure: never cut needed substance to be shorter, never pad to look thorough; use what completeness needs within the cap, and split when the cap is too small."

**2. Revise CLAUDE.md for them.** The kernel, per sentence: training covers it → cut; training silent → state plainly; training conflicts → NOT/DO override. No rationale, no history, present-tense truth. The seed draft is input, not the base. Line-by-line boss admission. Product: the kernel.

**3. Revise the wiki for them.** The boss + new-vp walk the quarry's pages together, eliminate roughly half; survivors cleaned for the zero-context reader, imported through the checkpoint into the Obsidian shell.

**4. Build the minimal comms bridge, tested before boot.** The two-log-file bridge between choirmaster and the old system per [comms-bridge-spec.md](comms-bridge-spec.md) (spec awaits its re-derivation pass). Test: a genuinely fresh subagent, handed only the draft kernel, uses the bridge unprompted. Unruled rider: Monitor-armed idle-wake on each side.

**5. Write their one-time startup instruction.** (Possibly dissolved: the kernel pickup line + founding handoff may BE the startup instruction — ruling pending.)

**6. Set up worktree/git and populate.** The git substrate (identity, `useConfigOnly`, base config), `.claude/settings.json` (bypass permissions), the launcher scripts (manifest row 9: fresh start / `claude --continue`, focus-restore cribbed from `iterm2-open-window.sh`), the Obsidian shell with step 3's survivors, skills, kernel — and the founding handoff written LAST via `handoff.py write`, so choirmaster's first boot is an ordinary handoff read.

**7. Pick ONE task; boot; run it; learn.** Ruled direction: the git foundation — the fast-pr-to-prod build slice (config + throat script with built-in checks + protection lock + workflow rules). Boot-test the delta first (find a named thing in the quarry without writing there; use the bridge; produce a handoff); every failure patches the pack. Then task 2 (standing candidate: the code-review skill), and companion admission right after the boot test passes.

## The documents

| Document | Status |
|---|---|
| [README.md](../../README.md) | The charter: what/why, seven principles, the agent model, layout. |
| This plan | The founding pair's workflow document. |
| [fast-handoff-design.md](fast-handoff-design.md) | Specification, d-review in progress. |
| [fast-pr-to-prod-design.md](fast-pr-to-prod-design.md) | Specification, d-review in progress. |
| [comms-bridge-spec.md](comms-bridge-spec.md) | Specification, re-derived 2026-07-21 (both channels, six ruled inputs honored); awaiting the boss's read and the package review. |
| [boot-pack-manifest.md](boot-pack-manifest.md) | Artifact list; rows superseded by the specs are historical. |
| [seed-claude-md-draft.md](seed-claude-md-draft.md) | Pre-calibration input to step 2, not the base. |
| [handoff-lite-skill-draft.md](handoff-lite-skill-draft.md) | Superseded by fast-handoff-design.md; kept as record. |
| git-clean-slate-plan.md (quarry: `~/Projects/nedlern/docs/working/proposed/`) | Read-only reference for step 7's slice. |

## Open — awaiting the boss

1. Entry-checkpoint-as-throat-check: the full statement awaits his approve (no import can land unmanifested; the manifest cannot lag the system). The checkpoint's mechanical shape is already ruled (2026-07-21): imports run through the executable import command, which writes the manifest line itself.
2. Commit this founding conversation's denoised transcripts (this session + predecessor) to `docs/cross-project/` — the founding decisions currently live only in unbacked `~/.claude` JSONLs.
3. Step 5's dissolution into the kernel + founding handoff.
4. The bridge spec's re-derivation is DONE (2026-07-21, all six ruled inputs honored; the spec now covers both channels — founding bridge and companion-era mini-comms with the shared-directory fix). Awaiting the boss's read; its two open questions (ceremony-time log snapshots; the Monitor idle-wake rider) moved into the spec's own Open section. The package review (nedschorus#8) is no longer gated on it.
5. Which artifact classes are gated (review-before-promotion) from day one.
6. The global `~/.claude/CLAUDE.md` edit before first boot (it currently points every session at the OLD system's kernel — measured).
7. Wiki-walk scheduling (step 3) and first boot-test timing.
