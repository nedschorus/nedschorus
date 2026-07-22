---
status: specification
design-as-of: 2026-07-22
---

# fast-handoff — the session handoff system (specification)

**Implementation status:** `scripts/handoff.py` is DESIGNED, NOT YET BUILT — the build order below starts it in the quarry. Ceremony behavior described in present tense is the contract for that build, not running behavior; the manual rehearsals to date follow the ceremony by hand (markers boss-ruled 2026-07-21, package-review item 9).

Continuity between sessions in this repo. Actors: the boss (human), the session agent (ending its session), a fresh drafting subagent, the successor session. The skill and script are named `handoff` (`handoff.py`); the skill carries the working alias `fast-handoff` only while it is prototyped inside the quarry — the predecessor repo at `~/Projects/nedlern`, read-only reference (see README).

## The artifacts

Each handoff is a numbered triple in `handoff/`, counter ascending, zero-padded width 4 (numeric ordering — `read` parses numbers, never sorts lexically; gaps in the series are legal):

- `handoff/<NNNN>.md` — the handoff. Fixed frame: a `written by session <id> at <UTC>` stamp at top; a fixed provenance block below it — ceremony mode (`auto`/`vet`), correction count, correction classes — whose presence and shape `write` validates (boss-ruled 2026-07-21, package-review item 7; this block is the permanent home of nedschorus#6's interim correction-summary tripwire); a `read by session <id> at <UTC>` stamp appended when consumed; the If-already-read TEMPLATE at bottom (script-injected, placeholder intact in the file; `read` substitutes the actual reader id only when it prints the warning). `read` on the normal path prints the BODY only — the frame is machinery, never shown as content.
- `handoff/<NNNN>-transcript.md` — the denoised dialog tail of the writing session: extracted from the last `line-count` JSONL lines (default 1000), both voices kept, noise dropped. The file IS the extracted window; reading it and "tail-only input" refer to the same content. The only other transcript surface is dead-session recovery (below); raw JSONLs are never read directly otherwise.
- `handoff/<NNNN>-tasks.json` — the surviving tasks exported at the ceremony, committed with the pair. `read` imports it PYTHON-DIRECT (boss-ruled 2026-07-21, package-review item 7): it writes the task files straight into the harness's session-keyed store directory (`~/.claude/tasks/<session-id>/`) and prints `imported N tasks`; the pickup line has the successor confirm N against its live task list. Accepted residual (boss-ruled 2026-07-21): the import couples to the harness's internal task-file format, which can change without notice — not a concern while the printed-count verification bounds any drift to a visible mismatch at the very next pickup; reopening trigger: a count mismatch.
- `scripts/handoff.py` — subcommands `write`, `read`, `transcript` (contracts below).
- Two CLAUDE.md lines, verbatim: the pickup line — *"At session start run `python3 scripts/handoff.py read`; follow the handoff only on a fresh successful read; on anything else stop and tell the boss."* — and the archive pointer — *"`handoff/<NNNN>-transcript.md` holds each past session's extracted dialog; read it when the handoff is not enough."*

## What a handoff body contains

The drafting subagent's distillation of the session dialog, plus only what (a) the extracted transcript misses AND (b) no durable store holds. Content routes by audience: successor → the handoff; everyone → durable stores (tasks in the task list, memories in the memory store, permanent knowledge in the wiki, tracked work in issues, behavior in skills and code — the handoff points at store content, never restates it; a pointer to MUTABLE content carries a version pin — a commit SHA with the path, an issue-comment id, the exported tasks file — so the successor resolves what the writer meant, not whatever the artifact says by read time (boss-ruled 2026-07-21, package-review item 7); the boss → an issue labeled `boss-review` (full-context body, walkable; no work ever waits on one). The highest-value body content: correction notes — "you will likely misread X as Y; actually Z."

## Writing a handoff (session end, boss present)

1. Run `handoff.py transcript` (no arguments = the current session, from the environment). It computes `NNNN = max+1` and writes `handoff/<NNNN>-transcript.md` — this file both carries the dialog and RESERVES the number; `write` later derives `NNNN` from it, never recomputes. Reservation is locked and explicit (boss-ruled 2026-07-21, package-review item 7): `transcript` holds an exclusive lock while computing and creating the reservation, so concurrent ceremonies cannot take the same number, and a reservation whose `write` never completed is a named INCOMPLETE state that `read` refuses on (see the state table) — an interrupted ceremony is visible, never silently newest.
2. Spawn a fresh subagent whose only inputs are that transcript file and the drafting instructions in the skill. It writes the draft to a scratch path and returns the path.
3. **The correction pass** (the session agent): fix the draft's misunderstandings (they predict the successor's), add facts the transcript misses that no store holds, prune anything a durable store already holds, route suggestion-class material to `boss-review` issues. Never added: accomplishment summaries, discovery reprises.
4. **The scrub**, in the mode the boss names — `handoff auto` (default: the agent scrubs on its own judgment) or `handoff vet` (the boss walks both the corrections and the scrub before finalizing); the mode words are the boss's spoken command, not a script invocation. Tasks: close the dead, rewrite the stale, carry the live. Memories: prune the stale. The agent states the open `boss-review` count, one line.
5. `handoff.py write <draft-path>`: validates, injects the If-already-read template, stamps, writes `handoff/<NNNN>.md` (the number from step 1's reservation; refuses on collision), exports surviving tasks to `handoff/<NNNN>-tasks.json`, commits all three files (pathspec-scoped, carrying the throat's provenance trailer schema) — and NEVER pushes. Ceremony commits ride to origin with the next `throat.py land` push (boss-ruled 2026-07-21, package-review S2: the throat's push monopoly has zero exceptions); the successor reads from the same canonical checkout, so nothing functional waits on the push.

A refused `write` changes no numbered handoff; the reserved transcript stays in place and the retry reuses it (no re-extraction).

**Privacy scan (boss-ruled 2026-07-21, package-review finding S1):** `write` runs a privacy-scan stage over the transcript before commit, ruled to the lightest form — initially minimal, even a no-op placeholder. The boss judges the risk low for this project: credentials are keychain-held and never appear in chat, and the residual — non-credential private conversation content landing in a public repository — is explicitly accepted. The stage exists as a named slot so teeth can be added later without redesigning the ceremony; strengthening it is a ladder rung admitted on evidence.

## Reading a handoff (session start)

`read` behaves per this table — the prose in the pickup line defers to it:

| Latest handoff's state | `read` behavior |
|---|---|
| WRITTEN (written-by stamp, no read-by), written by a DIFFERENT session | Validates everything first, imports `<NNNN>-tasks.json`, appends + commits the read stamp, prints the body LAST — validate → import → stamp → print (order boss-ruled 2026-07-21, package-review item 7: the successor sees the body only after the handoff is fully consumed, so a failed import or stamp can never strand a half-read handoff behind a working successor). The normal case — a fresh successful read. |
| Written by the CURRENT session (no read-by) | Prints only `you wrote this handoff — resume`. A session never consumes its own handoff. |
| READ by the current session | Prints only `already read by this session — resume`. Covers compaction re-entry, and `claude --continue` re-entry: `--continue` keeps the prior session id (boss-measured 2026-07-21), so a continued session lands in the same-session rows by construction — no separate resume row is needed, and the launcher keeps `--continue` from day one. |
| ALREADY-READ by a different session | Prints the staleness warning + the If-already-read text with `<reader-id>` filled from the read stamp; stamps nothing; exits nonzero. The boss decides. Note: a mid-session context CLEAR mints a new session id, so a cleared-and-relaunched terminal lands here by design — the boss's "continue" is the expected exit, not an error. |
| No handoff series | Refuses: "no handoff series — ask the boss." |
| Head file with no written-by stamp, or any malformed/unparseable stamp | Refuses as corrupt state; never prints it as a handoff. |
| Newest number is a reservation without its handoff (an INCOMPLETE ceremony — transcript written, `write` never completed) | Refuses, naming the orphaned reservation. The boss decides: complete the ceremony (`write` reuses the reservation) or remove it. |

The If-already-read template (stored with the placeholder; `read` fills it when printing): *"This handoff was already consumed by session `<reader-id>` — your picture is likely behind reality. Tell the boss. To recover what that session did: `python3 scripts/handoff.py transcript <reader-id>` and read the output. Do not start work before the boss says continue."*

## `scripts/handoff.py` contracts

| Subcommand | Does | Refuses (structured, named, never silent) |
|---|---|---|
| `write <draft-path>` | Frame validation of the draft (body non-empty; provenance block present and well-formed — mode, correction count, correction classes; after injection: stamp block well-formed, template present; reserved number uncollided — structure, not meaning), privacy scan (minimal per S1), inject, stamp, atomic write, task export, pathspec-scoped LOCAL commit of the triple with provenance trailers — no push. | Missing/unreadable draft path; validation failure (names the defect, writes no numbered handoff); missing/empty session-id environment (distinct exit code, never stamps empty); number collision; commit failure (surfaced verbatim). |
| `read` | Per the state table, in the ruled order — validate → import → stamp → print-last; task import only on the normal case. | Per the state table (including the newest-reservation-incomplete state); missing/empty session-id environment; stamp-write failure surfaced. |
| `transcript [session-id] [line-count]` | Defaults: current session, 1000. Extracts the two-voice dialog from the LAST `line-count` lines of the session's JSONL; drops tool dumps, thinking fragments, scheduled-prompt turns, subagent turns. Parser tolerance (boss-ruled 2026-07-21, package-review item 7): a live file's partial last record is tolerated (skipped, not fatal); a malformed line is skipped and counted, with the count named in the output, never a silent or fatal result; per-line size is bounded so one oversized record cannot defeat the window. Locates the JSONL by searching all project directories under `~/.claude/projects/` for `<session-id>.jsonl` (session ids are unique; the writing session's repo path may differ from the current one). Ceremony use writes the reserving file; recovery use (a dead session's dialog) prints to stdout. | No JSONL found for the id (names the paths searched); empty or unparseable JSONL (names which). |

All ceremony commits are local-only by the S2 ruling (read stamps always were — a boot-time push failure must not block boot); staleness detection therefore holds within one clone, and ceremony commits reach origin with the next `throat.py land` push. The lag is bounded by commit-as-you-go landing cadence and covered by the machine's backup; accepted.

## Assumptions

- MEASURED: JSONL extraction of a closed session yields readable dialog; the session id is in the environment; a context clear mints a new session id; `claude --continue` keeps the prior session id (boss-measured 2026-07-21 — a continued session is the same session to the read table); a fresh subagent's context is CLAUDE.md + prompt, no parent conversation.
- INFERRED, verified at dogfood: CLAUDE.md reloads at session start and after clears; the session id is stable across compaction (a false ALREADY-READ after routine compaction would cry wolf).
- UNMEASURED, gated: draft quality from transcript-only input (gate: T6a); `transcript` against the session's own still-open JSONL (gate: probed in build step 1).

## Tests

T1 `write` refuses each defect class; no numbered handoff changes on refusal · T2 stamps exactly once; same-session re-read prints only the resume line · T3 foreign read stamp → warning with filled reader id + nonzero + no stamp; strip-the-gate: neuter the comparison → T3 red · T4 empty series, stampless head, malformed stamp → three distinct refusals · T5 `transcript`: two voices, zero noise lines, closed AND live session, tail-window verified (content from the END of a long session), cross-directory id search, empty/unparseable refusal, plus the four adversarial parser fixtures (item 7): partial tail (live file ends mid-record), malformed line (skipped + counted, named in output), oversized line (bounded, cannot defeat the window), subagent-output classification (subagent turns dropped as noise, verified deliberate) · T6 own-handoff guard: the writing session's `read` prints the resume line, never consumes · T8 missing session-id env → loud refusals · T9 git failures surfaced; series unchanged after refused write; reserved transcript reused on retry · T10 numbering: reservation at step 1, `write` derives, collision refused, numeric (not lexical) max · T6a dogfood ceremony (steps 1–5) in the quarry via its sanctioned push path; correction count recorded; compaction-stability verified · T6b pickup-line test at first nedschorus boot (not testable in the quarry — its own startup machinery already loads context) · T7 one-time trial of a SECOND d-review-style pass on the T6a handoff — an optional extra vetting phase, NOT the core draft-then-correct ceremony; if it catches nothing material it is out permanently.

## Build order

1. `handoff.py` in the quarry — `transcript` first, then `write`/`read`; T1–T6, T8–T10 green.
2. The skill file (ceremony steps + drafting instructions), then a d-review clarity pass.
3. Cross-runtime review (Codex side) of the near-final spec.
4. Dogfood T6a + T7 on the current role's next real handoff.
5. Enter nedschorus at populate (the boot-up plan's repository-population step), through the entry checkpoint; T6b at first boot declares it live.

## Known holes

- Draft quality is unmeasured until T6a; the design bets on it.
- Corrections and the scrub are done by the ending agent at low context; the boss's presence is the backstop; reopens as a mechanism candidate if dogfood shows scrubs skipped.
- Very-long-session material can predate the extracted window and every store; bounded by commit-as-you-go and the boss at the walk.
- Staleness detection is single-clone (read stamps unpushed); revisit at companion admission.
- A counter past 9999 breaks the width-4 padding; accepted (numeric parsing tolerates wider numbers; the pad is cosmetic).
- Transcripts commit to a public repository behind only the minimal (possibly no-op) privacy scan; accepted by boss ruling 2026-07-21 (package-review S1). The residual class is non-credential private conversation content.
- The old system's handoff machinery is untouched; the current role keeps its old skill until T6a.
