---
status: specification
---

# fast-handoff — the session handoff system (specification)

Continuity between sessions in this repo. Actors: the boss (human), the session agent (ending its session), a fresh drafting subagent, the successor session. The skill is named `fast-handoff` until it enters nedschorus, where it is named `handoff`.

## The artifacts

- `handoff/<NNNN>.md` — one numbered file per handoff, counter ascending, zero-padded. Fixed frame: a `written by session <id> at <UTC>` stamp at top; a `read by session <id> at <UTC>` stamp appended when consumed; a script-injected If-already-read section at bottom. Body: free-form.
- `handoff/<NNNN>-transcript.md` — the denoised two-voice dialog of the session that wrote handoff `<NNNN>`, committed beside it. Read its tail for more context than the handoff gives; this is the only transcript surface — never read raw session JSONLs (exception below).
- `scripts/handoff.py` — subcommands `write`, `read`, `transcript` (contracts below).
- One CLAUDE.md line for pickup, and one for the transcript archive.

## What a handoff body contains

The drafting subagent's distillation of the session dialog, plus only what (a) the transcript tail misses AND (b) no durable store holds. Content routes by audience: successor → the handoff; everyone → durable stores (tasks in the task list, memories in the memory store, permanent knowledge in the wiki, tracked work in issues, behavior in skills and code — never duplicated into the handoff); the boss → `boss-review-log.md` (suggested wiki/issue/skill updates, appended as dated checkbox lines; nothing ever blocks on a log entry). The highest-value body content: correction notes — "you will likely misread X as Y; actually Z."

## Writing a handoff (session end, boss present)

1. Run `handoff.py transcript` once, producing `handoff/<NNNN>-transcript.md`. This is the session's only JSONL extraction.
2. Spawn a fresh subagent whose only inputs are that file and the drafting instructions in the skill. It writes the draft.
3. The session agent corrects the draft's misunderstandings (they predict the successor's), adds facts the tail misses that no store holds, prunes anything a durable store already holds, and routes suggestion-class material to `boss-review-log.md`. Never added: accomplishment summaries, discovery reprises.
4. The scrub, in the mode the boss names — `handoff auto` (default: the agent scrubs on its own judgment) or `handoff vet` (the boss walks the scrub first). Tasks: close the dead, rewrite the stale, carry the live. Memories: prune the stale.
5. `handoff.py write`: validates, injects the If-already-read section, stamps, writes `handoff/<max+1>.md`, exports the surviving tasks to its own file, commits handoff + transcript (pathspec-scoped), pushes.

## Reading a handoff (session start)

The CLAUDE.md line: run `handoff.py read`; follow the handoff only on a fresh successful read; on anything else, stop and tell the boss (own-stamp re-entry: resume what you were doing). `read` prints the latest handoff, appends the read stamp, commits it, and imports the exported tasks into the current session's task store.

| State of the latest handoff | `read` behavior |
|---|---|
| WRITTEN (written-by stamp, no read-by) | Prints it, stamps, imports tasks. The normal case. |
| READ by the current session | Prints only `already read by this session — resume`. Nothing else. |
| ALREADY-READ by a different session | Prints a staleness warning + the file's If-already-read section, stamps nothing, exits nonzero. The boss decides. |
| No handoff series | Refuses: "no handoff series — ask the boss." |
| Head file with no written-by stamp | Refuses as corrupt state; never prints it as a handoff. |

The If-already-read section (script-injected, verbatim): *"This handoff was already consumed by session `<reader-id>` — your picture is likely behind reality. Tell the boss. To recover what that session did: `python3 scripts/handoff.py transcript <reader-id>` and read the output. Do not start work before the boss says continue."*

## `scripts/handoff.py` contracts

| Subcommand | Does | Refuses (structured, named, never silent) |
|---|---|---|
| `write` | Frame validation (stamp block well-formed, If-already-read injected, body non-empty, counter uncollided — frame only; the script checks structure, not meaning), stamp, atomic write as `handoff/<max+1>.md`, task export, pathspec-scoped commit of handoff + transcript, push. | Validation failure (names the defect, writes nothing); missing/empty session-id env (distinct exit code, never stamps empty); commit/push failure (surfaced verbatim, file already durable locally). |
| `read` | Behavior per the state table; task import into the current session's store. | Per the state table; missing/empty session-id env; stamp-write failure surfaced. |
| `transcript` | Extracts the two-voice dialog from a session JSONL (args: session id, line count, default 1000): keeps boss and agent text; drops tool dumps, thinking fragments, scheduled-prompt turns, subagent turns. Derives the transcript-directory slug from the current repo path at runtime. Runs at ceremony start, and on demand only against a session that died without its ceremony (the ALREADY-READ recovery — the one case whose dialog is not already committed). | Missing JSONL (names the exact path tried); empty or unparseable JSONL (names which). |

Read stamps commit locally and do not push (a boot-time push failure must not block boot). Staleness detection therefore holds within one clone.

## Assumptions

- MEASURED: JSONL extraction of a closed session yields readable dialog; the session id is in the environment; a context clear mints a new session id (which is why ALREADY-READ on a cleared session is correct, not a false alarm); a fresh subagent's context is CLAUDE.md + prompt, no parent conversation.
- INFERRED, verified at dogfood: CLAUDE.md reloads at session start and after clears (the pickup line's reliability); the session id is stable across compaction (a false ALREADY-READ after routine compaction would cry wolf).
- UNMEASURED, gated: draft quality from tail-only input (gate: T6a); `transcript` against the session's own still-open JSONL (gate: probed in build step 1).

## Tests

T1 `write` refuses each frame defect, series byte-identical after refusal · T2 `read` stamps exactly once; same-session re-read prints only the resume line · T3 foreign stamp → warning + section + nonzero, no stamp; strip-the-gate: neuter the comparison, T3 goes red · T4 empty series and stampless head → distinct refusals · T5 `transcript` two voices, zero noise lines, closed AND live session, empty/unparseable refusal · T8 missing session-id env → loud refusal both subcommands · T9 git failures surfaced; series head unchanged after refused write · T10 counter: `write` creates max+1, `read` targets max · T6a dogfood ceremony half in the quarry (sanctioned push path; correction count recorded; session-id-across-compaction verified) · T6b kernel-line pickup at first nedschorus boot · T7 one-time second-pass trial on the T6a handoff (if it catches nothing material, two-phase is out permanently).

## Build order

1. `handoff.py` prototype in the quarry — `transcript` first, then `write`/`read`; T1–T5, T8–T10 green.
2. The skill file (ceremony steps + drafting instructions), then a d-review clarity pass.
3. Cross-runtime review of the near-final spec (Codex side).
4. Dogfood T6a + T7 on the current role's next real handoff.
5. Enter nedschorus at populate through the entry checkpoint; T6b at first boot declares it live.

## Known holes

- Draft quality is unmeasured until T6a; the design bets on it.
- Corrections and the scrub are done by the ending agent at low context; the boss's presence is the backstop; reopens as a mechanism candidate if dogfood shows scrubs skipped.
- Very-long-session material can predate the tail and every store; bounded by commit-as-you-go and the boss at the walk.
- Staleness detection is single-clone (read stamps unpushed); revisit at companion admission.
- The old system's handoff machinery is untouched; the current role keeps its old skill until T6a.
