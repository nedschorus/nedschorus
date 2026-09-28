---
issue: "[Seat mailboxes across machines and runtimes](https://github.com/nedschorus/nedschorus/issues/749)"
status: draft (2026-09-22) — no code written, nothing built. Revised 2026-09-22T19:50Z after the user put every seat on one account: the original justification (two accounts, per-account discovery) is dead and is replaced by a measured one (liveness — an offline seat receives nothing, whatever the account). See "Why the fleet needs it"; two additions in §9 and §10.6. Filed as its own issue on 2026-09-28, with §10.7 added; measurements below are as of 2026-09-22.
home: this issue. It was to reopen GHI [Claude turn/start and turn/steer equivalents](https://github.com/nedschorus/nedschorus/issues/37), the earlier request, closed with no GHI-MD; since PR 708 such an issue cannot be edited by hand, so the user approved filing the design as a new issue instead (merge-lane-2's meta-walk, item 10, "Y" at 2026-09-28T15:18:11Z).
next action: the user walks this design with merge-lane-2, one open question of §10 at a time; nothing is built before that walk.
---

# Seat mailboxes across machines and runtimes

One agent-seat sends a message to another, on either machine, in either runtime, and the recipient acts on it without the user relaying anything. That is the whole job. This document extends `docs/cross-project/comms-bridge-spec.md`, the user's append-only log-pair design adopted verbatim 2026-07-20; everything below that is not marked NEW is that spec, applied to ten seats instead of two.

## Why the fleet needs it

**The account argument this document was first built on is dead, and the requirement survives it. Read this section as rewritten 2026-09-22T19:50Z, superseding the earlier one.**

The original argument was that the two machines were signed into two claude.ai accounts, discovery is per account, and so built-in cross-session messaging could not reach between them: every send from 2026-09-22T00:40Z reported "queued" and none arrived, stalling the pull-request queue for a day. **That condition is gone.** The user put every seat on `ned@lerner1.com` on 2026-09-22, and the Mac seats now appear in ned-box's `ListAgents` as ordinary peers.

**The mailbox is still needed, for a reason the account problem was hiding.** Built-in messaging requires both ends to be alive **at the same moment**. Measured from this seat immediately after the account change, sending to the merge-lane seat on the Mac, the tool's own answer was:

> a Claude session on another machine, over Remote Control; not confirmed read ... it is offline right now — delivery is queued until that machine reconnects

Every Mac seat read `offline` in the same listing. So the message did not arrive, one account or two. The obstacle moved from *addressing* to *liveness*, and liveness is the permanent one: seats hand off, are restarted by the supervisor, crash, and sit down for hours, which is the fleet working as designed rather than a fault. A file mailbox delivers across time — a seat down for a day reads its mail in order when it next starts — and that is a property no live-session channel has.

**And `offline` does not mean the seat is idle, which is the sharpest version of this argument.** Measured within the same ten minutes, 2026-09-22: `reboot-test` read `offline` in ned-box's listing at 19:52Z, and at 19:55Z it pushed a hand merge to PR [Build the GHI write tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596) — a commit, on a branch, resolving five conflict sites, which is minutes of work by a seat that the messaging layer reported as unreachable. `offline` describes Remote Control connectivity, not whether an agent is working. So the failure is not "the message waits until someone is around"; it is **a seat can be actively doing the work you want to talk to it about, and be unreachable while doing it.** Nothing about one account fixes that, and no amount of both-ends-alive discipline detects it, because both ends *were* alive.

Also measured, and worth keeping because it is the one positive result: when a Mac seat's Remote Control session *is* connected, a direct send from ned-box now works — at 20:0xZ a send to `merge-lane [42b1fb]`, then `idle`, returned no "queued until that machine reconnects" clause, unlike the send twenty minutes earlier. So built-in messaging is a genuine fast path when both ends happen to be up, and the mailbox is what carries the rest. The design should not replace the fast path; it should not depend on it either.

**This is also the specific mistake to guard against, because the project has already made it once.** GHI [Claude turn/start and turn/steer equivalents](https://github.com/nedschorus/nedschorus/issues/37) recorded this break on 2026-08-17, designed a file inbox, and was **closed on 2026-09-18 because the harness's messaging had started working**. It then broke again four days later. Harness messaging working is not evidence the mailbox is unnecessary; it is evidence that both machines happen to be up and on one account right now. The requirement is a channel that asks neither which account a seat is on nor whether it is currently running.

The cost of not having it, measured today: ten entries sat in `walk-ledgers/outgoing-messages-to-mac-seats-from-merge-lane-2.md`, six of them carrying fix-round requests their authors could not act on, because the only route to a Mac seat was a human-forwarded file that the forwarder was offline to read.

## Two terms, proposed to the user

- **seat-mailbox** — one agent-seat's directory of incoming message files. Every seat has exactly one.
- **mailbox-root** — the one directory on ned-box holding every seat-mailbox.

Everything else reuses existing project-terms. Checked for collisions: no file in the tree matches `*mailbox*`.

## 1. The transport

**mailbox-root is `/home/nedlern/nedschorus-agent-mailboxes/` on ned-box.** Inside it, one directory per agent-seat, and inside that, one file per correspondent:

```
/home/nedlern/nedschorus-agent-mailboxes/
  merge-lane-2/from-merge-lane.md        <- only merge-lane ever writes this
  merge-lane-2/from-reboot-test.md
  merge-lane/from-merge-lane-2.md        <- only merge-lane-2 ever writes this
```

A pair of seats owns exactly two files — the comms-bridge log-pair unchanged, now found by the recipient's name rather than a channel's — and files are created lazily, only for pairs that talk. One writer per file is not tidiness: the Mac reaches these files over an SMB share (`read only = no` in `/etc/samba/smb.conf`, share `[nedhome]`, `path = /home/nedlern`; check with `ssh nedlern@ned-box 'sed -n "25,33p" /etc/samba/smb.conf'`), and the atomic-append guarantee a local filesystem gives does not carry over SMB. With one writer per file there is nothing to interleave.

**Every seat-mailbox lives on ned-box, including the Mac seats'.** A Mac seat writes and reads its mail over `/Volumes/nedhome/nedschorus-agent-mailboxes/...`; a ned-box seat uses the local path. It is chosen because the reverse direction does not exist: ned-box has no `~/.ssh/config` and an empty `known_hosts`, and `scripts/resupervise-seat.py`'s docstring records that "the box cannot even resolve its own ssh alias". The mount is the only transport measured working both ways — merge-lane (Mac) appended into merge-lane-2's ned-box files twice on 2026-09-22, and that is how PR [dangling-path-citation-check: a test file is one whose stem ends -test, whatever the extension](https://github.com/nedschorus/nedschorus/pull/631) reached merge-lane-2 and was merged.

**Why not the alternatives.** A broker (murmur's NATS, hcom's MQTT, claude-peers-mcp's HTTP+SQLite) is a service to install, supervise and diagnose on two machines, for a hop the mount already makes. An SSH spool (druide67/claude-whisper) needs the one direction that is not configured. A per-session MCP server is a second lifecycle per seat.

## 2. The message

Unchanged from the comms-bridge spec. An entry is:

```
## merge-lane-2:merge-lane-0007 2026-09-22T18:31:04Z merge-lane
reply-to: merge-lane:merge-lane-2-0012
base-sha: nc@5f0fd4c5

Plain markdown body.
```

The entry-id is channel-namespaced as the spec requires — here the channel is the recipient's seat-mailbox, so it reads `<recipient>:<author>-NNNN`. The counter is recovered at startup from the tail of the writer's own file, so it is restart-proof with no second copy of the number anywhere; a missing or empty file means the next number is `0001`, and a file carries no header, only entries. `reply-to:` and `base-sha:` are optional and keep their meanings, the repository qualifier included. There is no protocol beyond that: no envelope, no JSON, no schema version. A person reads a seat-mailbox with `cat`.

Appends go through one shared utility, `scripts/mailbox-append-entry.py` (NEW, the spec's "shared append utility" with a recipient argument): it composes the whole entry in memory, bounds its size, writes it in one call, and detects a short write. A reader never sees half an entry.

## 3. Receipts, and how a reader knows what it has handled

The user measured on 2026-09-22 that appending to a file in another machine's checkout works and an in-place edit of one is refused by the permission layer. So nothing here is ever edited, including the reader's position.

**The receipts are the checkpoint.** A seat `R` reads an entry in `mailbox-root/R/from-S.md`, acts on it, then appends one ordinary entry to `mailbox-root/S/from-R.md` — S's mailbox, R's own file in it, the file R alone writes — carrying one `received: <entry-id>` line per entry handled. One entry may acknowledge several, which is what a seat catching up writes. R never writes anything under `mailbox-root/R/`; every file there belongs to the seat its name gives.

Those lines are both the acknowledgement the sender reads and the reader's own durable position: on any later turn, or after a session-handoff, R finds where it left off from the tail of `mailbox-root/S/from-R.md`. One fact, one place, append-only, visible to both sides — no checkpoint file exists to be edited, and no two records of it can drift apart.

The receipt is written **after** the entry is acted on, per the spec's ruling, so a crash between acting and acknowledging re-delivers — duplicates the spec already rules tolerable. A session that dies mid-message wrote no receipt, so its successor re-reads that message, and this survives reincarnation without a handoff mentioning mail.

**What a send reports.** `mailbox-append-entry.py` exits 0 and prints the entry-id when the bytes are on disk, or exits 1 with the reason (mount not mounted, directory missing, short write). There is no third state. The failure the fleet just lived through was a send that said "queued" and meant nothing; here the only evidence of delivery is a line the recipient wrote, and its absence means assume undelivered.

## 4. Waking a Claude seat

**Measured.** The installed Claude Code carries a hook field `asyncRewake`, documented as "If `true`, runs in the background and wakes Claude on exit code 2" (https://code.claude.com/docs/en/hooks). Verified in the binary, not only the docs: `grep -c asyncRewake /home/nedlern/.local/share/claude/versions/2.1.278` returns 9. The hook's stderr becomes the system-reminder the woken model is shown, so the message arrives with the wake.

**The design (NEW).** One more Stop hook, `scripts/mailbox-wait-and-wake-hook.py`. The committed `.claude/settings.json` holds one `Stop` group whose `hooks` list carries `handoff-context-threshold-hook.py` and `checkout-freshness-catch-up.py`; the new hook is a third entry in that list, with `asyncRewake` on the command entry beside `type` and `command`, where the binary's schema puts it, next to `async`:

```json
{
  "type": "command",
  "command": "python3 \"$CLAUDE_PROJECT_DIR\"/scripts/mailbox-wait-and-wake-hook.py",
  "asyncRewake": true
}
```

When the turn ends the hook records the size of every file in the seat's own seat-mailbox, goes to the background, and re-reads those sizes every ten seconds. On growth it exits 2 with every byte added since it armed, and the idle session wakes holding them. It reads no receipts and parses no headers: every file under `mailbox-root/<seat>/` is addressed to that seat by construction, and growth since arming is the whole test. Four rules make that safe:

- **Enrolment is the directory.** The hook exits 0 at once unless `mailbox-root/<seat>/` exists, `<seat>` being the working directory's basename — already how /handoff names a seat, so nothing new decides it. Subagents, cells and task worktrees have no such directory and stay silent; creating one is how a seat joins.
- **One advisory lock per seat, per machine**: `flock` on `/tmp/mailbox-wait-and-wake-<seat>.lock`, held through the waiter's open descriptor. A hook that cannot take it exits 0, so a Stop during an existing wait arms no second waiter. Nothing cleans it up — the kernel drops the lock when that descriptor closes, `kill -9` included, so a crashed waiter cannot leave a lock that silences a seat.
- **At most one wake per armed wait.** After exiting 2 the waiter is gone, and the turn it caused ends in a Stop that arms a fresh one, baselined on the file as it now stands. An entry the woken turn failed to act on is never woken for twice; it is read at the next ordinary turn, so a message that crashes a turn cannot drive a wake loop.
- **No deadline: it ends with its session.** GHI [Console text-insertion + stuck/waiting-state detection](https://github.com/nedschorus/nedschorus/issues/27) recorded that killing a Claude process group does not reap a persistent watcher child, so the waiter must notice on its own; its stdin JSON carries the session id and transcript path, and which it watches is the one mechanism the build must settle (§9). That deadline problem also makes the Monitor tool the wrong instrument here: 5 minutes by default, 30 at most, re-armed by the agent (https://code.claude.com/docs/en/tools-reference#monitor-tool). **This answers "Open" item 2 of the comms-bridge spec, the unruled Monitor-armed idle-wake rider, by choosing a different instrument.**

Borrowed from [druide67/claude-whisper](https://github.com/druide67/claude-whisper) (`internal/cmd/wakewait.go`) and [alexfrmn/murmur](https://github.com/alexfrmn/murmur), whose Stop-hook wake and startup drain this copies; claude-whisper's one-hour waiter life is the part deliberately not copied.

No cross-session tool call exists anywhere in the path, so the permission-mode problem the Mac seat measured — a message between sessions in different modes held for approval — has nothing to hold.

## 5. Waking a Codex seat

**Measured, from the vendor documentation** (https://learn.chatgpt.com/docs/app-server, https://learn.chatgpt.com/docs/developer-commands?surface=cli). `turn/start` adds user input to a thread and begins generation; `turn/steer` appends to an active turn and fails when there is none. An app server listens on a Unix socket (`codex app-server --listen unix://PATH`), and a TUI attaches with `codex --remote` or `codex resume --remote`.

**Not established, and I could not establish it.** Attaching an external process to an already-running plain `codex` is not described in those pages; remote mode applies to a server started with `--listen`. So a Codex seat must be launched for this, the one launcher change this design asks for.

**The design (NEW).** A Codex seat is launched as an app server on a per-seat Unix socket with its TUI attached over `--remote`, its launcher writing the socket path and thread id beside the socket on that seat's own machine — never into `mailbox-root`, which only a seat's correspondents write. One small waker, `scripts/codex-mailbox-turn-start-waker.py`, runs on the same machine, watches the seat-mailbox for growth as the Claude waiter does, and calls `turn/start` on that thread with the added bytes. Codex then reads, acts, and appends its own `received:` receipt like any other seat. If the socket is gone or `turn/start` is refused, the waker stops and prints why on that seat's terminal; it does not retry, and a relaunch writes a fresh thread id over the stale one. Borrowed from [murmur's wake-native documentation](https://github.com/alexfrmn/murmur/blob/main/docs/wake-native.md), which limits the same arrangement to managed `--remote` sessions — the same limit, honestly held.

No Codex seat exists today: Codex runs here only as non-interactive cells (`nc-systems/cold-read/cold-read-codex-cell.py`, `scripts/code-review-codex-cell.py`), so this half is specified now and built when the first one is created. Sending **to** a Claude seat **from** Codex needs none of it: Codex appends to a file.

## 6. When a machine or a seat is down

- **Mount down.** Send fails on the Mac side, exit 1, naming the mount; a Mac seat's waiter reports the same and exits rather than looping. ned-box seats are unaffected.
- **Recipient down.** The append still succeeds — a mailbox is a file, not a process — and the message waits. When the seat next starts it reads from its last receipt forward, so a seat down for a day gets everything in order, which the "queued" messages never did.
- **Recipient alive but never answered.** No receipt appears. The sender notices on its own next turn, not on a timer: this lane retired the pre-merge timer on 2026-08-28 and does not reinstate clocks. If it matters immediately, the sender tells the user, the always-available fallback the comms-bridge spec already names.
- **Seat renamed or retired.** Its directory stays until someone removes it, so a message to a seat that no longer runs is at least visible to anyone who looks.

## 7. Who writes what

| Party | What it does |
|---|---|
| Any agent-seat sending | runs `mailbox-append-entry.py <recipient> <body file>`; reads the entry-id it prints |
| Any agent-seat receiving | on wake or at session start, reads past its last `received:` line in every `from-*.md` of its own seat-mailbox — not only the bytes the wake carried — acts, then writes its receipts as §3 says, one file per sender |
| Every Claude seat | nothing to install: the Stop hook is in the committed `.claude/settings.json` and reaches both machines through git. It does nothing until the seat has a directory under mailbox-root, so enrolling is one `mkdir` and withdrawing one `rmdir` |
| A Codex seat | launched as app server + `--remote` TUI, socket and thread id recorded on its own machine, one waker started |
| `scripts/launch-claude-mac`, `scripts/launch-claude-ubuntu` | unchanged |
| The user | nothing, beyond the mount being up |

## 8. Deliberately not in it

Each was a candidate and each is left out on purpose: no message broker, queue server or relay (NATS, MQTT, HTTP+SQLite, Redis); no per-session MCP server; no Claude Channels, ruled out by the user 2026-09-22 ("Claude channel was problematic"); **no terminal injection of any kind** — no tmux `paste-buffer`, no PTY writes, no AppleScript typing, which is what [aannoo/hcom](https://github.com/aannoo/hcom) and [FrankenBit/tmux-tell](https://github.com/FrankenBit/tmux-tell) use and what `scripts/synthetic-keystroke-guard-hook.py` already blocks at any surface an operator may be typing on; no `turn/steer`, because turn-boundary delivery is enough at this scale; no Monitor watch, for the deadline reason above; no delivery lifecycle, retries, priorities, broadcast or groups; no encryption or authentication, this being one LAN, one user and cooperative seats; no rotation or TTL beyond the spec's; and no daemon — the only long-lived process is a hook child that dies with its session.

## 9. What I could not verify

- That an SMB append from the Mac is atomic. Not relied on: one writer per file.
- That `asyncRewake` exit 2 wakes a session idle for hours rather than minutes. The field is real; the duration is untested.
- That a hook's background child survives a seat kill the way a Monitor child does. Assumed from GHI 27's measurement of the Monitor case.
- **How a waiter learns its session has ended.** `session_id` and `transcript_path` are both in the hook's stdin payload and in the binary, but which is a reliable liveness signal is untested, and `$PPID` is not one: a hook runs under a shell the harness spawns. Until it is settled, a waiter can outlive its seat.
- That `turn/start` into an attached `--remote` TUI visibly drives that TUI. No Codex seat exists to try it on.
- That ned-box genuinely cannot ssh to the Mac: it has a key named for the purpose, no config and no known hosts. The design needs none either way.
- **Whether §3's write-permission measurement still holds.** It was taken while the two machines were on two accounts: a Mac seat appending to a file in merge-lane-2's ned-box checkout succeeded twice, and an in-place edit of one was refused by the Claude Code permission layer as a shared-resource change. The refusal was attributed to the permission *mode*, not the account, so it should survive the 2026-09-22 account unification — but nobody has re-measured it since, and this design leans on it (§3 puts receipts in append-only entries for exactly this reason). Re-measure before building. If in-place edits now succeed, §3 still stands on its other leg — one fact in one place, no checkpoint that can drift — but the argument for it gets weaker and should be re-argued rather than quietly kept.

## 10. Open questions for the user

1. **mailbox-root's location.** Recommendation: a new top-level `/home/nedlern/nedschorus-agent-mailboxes/` on ned-box, not inside the log-store, whose kinds are add-only records shipped by a program with its own README authority. Live mail is neither, and putting it there means teaching that program a sixth kind.
2. **The two proposed terms, seat-mailbox and mailbox-root.** Recommendation: adopt both and add them to the glossary; no existing term names either thing.
3. **A missing receipt is the only failure signal, read on the sender's next turn rather than on a timer.** Recommendation: accept. A timer rebuilds the pre-merge wait this lane retired on 2026-08-28.
4. **The Codex half: specify now, build at the first Codex seat?** Recommendation: yes. It is the only part that changes a launcher, and there is nothing to launch yet.
5. **Which seats are enrolled first?** The hook lands in the committed settings for the whole fleet at once — there is no second settings file — but sleeps in any seat with no directory under mailbox-root, so the rollout is a list of directories, not of configurations. Recommendation: create two, merge-lane and merge-lane-2, the pair broken today; run the lane on them for a day; then the rest.
6. **Should an announcement about a pull request have to name the seat that wrote it?** (NEW, 2026-09-22, from a routing error this seat made today.) §2 deliberately has no envelope and no schema, and the entry-id already names the message's own author. But the message's author is not the same as the *work's* author, and today merge-lane-2 sent PR 637's follow-ups to the wrong seat: it read the changed file `scripts/ghi-info-ask.py` and the branch name `ghi-info-state-key-names-the-session-it-holds` as naming the authoring seat, when both name the program. MD-skills wrote it. The only place that fact appeared anywhere was the sweep stamp inside the pull request body — `MD-skills at 4ce13e727062` — which carries it as a side effect of the runner naming its checkout, not as a record. ghi-info caught the error and said so; nothing else would have. **Recommendation: not a mailbox field.** Keeping §2 free of schema is worth more than one line, and a wrong `authored-by:` would be believed more readily than a filename is. It belongs instead in whatever governs what a pull-request announcement must contain — raised here because the mailbox is what such announcements will travel through, and because the cost of getting it wrong is a fix-round request sitting with a seat that cannot act on it.
7. **Terminal wrappers: ruled out entirely, or judged one by one?** (NEW, 2026-09-28.) §8 rules out "terminal injection of any kind". The user said on 2026-09-22 that "Terminal wrappers can be OK or bad, depending on exactly what they do", which is narrower. merge-lane-2 undertook to check one, [aannoo/hcom](https://github.com/aannoo/hcom), against that, and has not. **Recommendation: check hcom before this question is walked,** and bring what it writes to a session's terminal, and when, so the answer rests on what it does rather than on its category.
