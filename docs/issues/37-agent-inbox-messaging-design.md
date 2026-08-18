---
status: design under review revision; build boss-gated, tracked in nedschorus#37
design-as-of: 2026-08-18
---

# Agent inbox messaging — the turn/start and turn/steer equivalents (design)

How a message reaches a Claude session as **data instead of keystrokes**: a
per-agent inbox — one sqlite database any writer inserts a record into — and
a persistent Monitor whose emitted line wakes the idle session. This is the
design for [nedschorus#37](https://github.com/nedschorus/nedschorus/issues/37)
— the Claude-side equivalent of the Codex App Server's `turn/start` (deliver
into an idle session) and `turn/steer` (deliver into an active turn) — and
the permanent replacement for tmux keystroke injection, which the
synthetic-keystroke guard (`scripts/synthetic-keystroke-guard-hook.py`,
merged 2026-08-17) already restricts to verified-detached sessions as an
interim.

Everything here is design; no code exists. The build is boss-gated like all
NC work. Build slices are at the end.

## The problem, precisely

A Claude session that is idle does not process content that is merely
displayed or injected at it — a message becomes a model turn only on real
input (upstream: [anthropics/claude-code#44380](https://github.com/anthropics/claude-code/issues/44380),
open). The legacy fleet's entire mail-delivery machinery worked around this
gap, and the unsafe workaround family — typing keystrokes at sessions — is
what spliced the operator's typing twice on 2026-08-17 (rule and receipts:
[nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27)).

What already works, and therefore bounds what this design must add:

- **On one machine, Claude-to-Claude**: the harness's cross-session
  messaging (ListAgents/SendMessage over per-machine sockets) delivers
  reliably — to a busy session at its next tool round, and its send wakes an
  idle one. The inbox does not replace it on-machine.
- **Across machines**: nothing. The 2026-08-17 LAN test failed in both
  directions, and the boss ruled Remote Control not pursued (evidence on
  #37). This is the gap the inbox closes. **Observed cost, 2026-08-18**
  (merge-lane seat, reported live): the Mac merge-lane seat held a tested,
  full-history answer to a question the box's gatekeeper seat had just
  been asked; ListAgents on the Mac shows only Mac sessions, so the
  finding could not be handed over — it went through the user by voice,
  and the gatekeeper seat re-derived the same answer independently.
  Duplicate work plus an operator interruption, exactly the waste this
  layer removes. The same incident sharpens the gap's shape: Mac→box
  *observation* already works (a persistent watcher over ssh reads box
  seats' dialogs in real time) — what is missing is an addressable
  receiving endpoint, which is precisely what a polled inbox provides,
  with no cross-machine peer discovery required.
- **Non-Claude writers**: nothing. nedsmessenger, watchers, cron jobs, and
  shell scripts have no way to reach a session except keystrokes. The inbox
  gives them one.

So the inbox's scope is: **cross-machine delivery, non-Claude writers, and
durable delivery to agents that are down** (the store outlives the session;
backlog is read at the next start). On-machine Claude-to-Claude traffic
keeps using SendMessage.

## Evidence base

All numbers verified and recorded on
[#27](https://github.com/nedschorus/nedschorus/issues/27) (Monitor idle-wake
canary, 2026-07-28, Claude Code 2.1.220) unless noted:

- A persistent Monitor's emitted line wakes an idle session with **no
  keystroke: 5/5 trials, 3.045–3.754 s** from condition to first model
  activity; 0.24–0.73 s to notification. The canary's trigger was itself a
  **SQLite row inserted from outside the PTY** — the proven wake chain
  already contained sqlite, so this design's store choice subtracts nothing
  from the evidence.
- A 10-message burst drained losslessly from one notification (10/10,
  18.63 s to completed receipt turn).
- An armed-but-silent watcher produced **zero transcript events and zero PTY
  growth** over a 30 s interval — arming is free until a message arrives.
- Three deployment caveats, all reproduced in the canary run:
  1. Claude's **default permission mode denied the Monitor arm** twice;
     command-scoped allow-rules fixed it without a global bypass.
  2. The harness's `premature_notifications` counter misclassifies
     background-task completions as Monitor events — it is not valid
     evidence about Monitor behavior.
  3. Killing a Claude process group **did not reap the persistent Monitor
     child** (watcher pair survived as live PIDs and needed manual kill).
     Containment is the design's job, not the harness's.
- Monitor events reach a **busy** session too: they land as task
  notifications at the session's next tool round (harness-documented
  behavior, observed routinely in fleet sessions). This is what makes the
  steer half mostly free — see § The steer half.

Alternative wake channel, considered and not chosen: a `Stop` hook declared
`asyncRewake: true` exiting 2 also wakes an idle session (measured 3.1 s;
druide67's comment on #27 with upstream receipt). Rejected for this design
because it must be armed by a prior Stop (a fresh or promptless session has
nothing armed), and its stderr reaches the model **with the user role** — a
peer's message would borrow the operator's authority. The Monitor path
delivers as a task notification, which the harness itself frames as
non-user input; that framing is load-bearing for trust (§ Trust).

## Architecture

Three parts: a database, a writer, a reader. No daemon of our own — sqlite
is embedded and serverless — no relay, and no new socket (the cross-machine
hop is SSH).

### The inbox database

`~/agents/<name>/agent-inbox.db` — one sqlite database per agent, on the
machine where the agent runs. Ruled 2026-08-18, replacing this design's
first draft (an append-only JSONL file with a byte-offset cursor): the
review showed the file draft re-implementing database machinery piece by
piece — a cursor protocol with its own crash windows, torn-write handling,
a size cap with sidecar files, malformed-line tolerance — and the wake
canary's trigger was already a sqlite insert, so the proven mechanism loses
nothing. sqlite ships in Python's standard library: no new dependency on
either machine. Sessions recycle; the agent and its inbox persist. The
path rides the box convention from
[nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45) (an
agent's home is `~/agents/<name>`); a Mac-side agent uses the same shape
under its own home.

Schema (v1 — `PRAGMA user_version = 1` marks the version; the database is
created on first use by whichever script touches it first):

```sql
CREATE TABLE inbox_messages (
    message_id     INTEGER PRIMARY KEY,  -- assigned by the database
    send_token     TEXT UNIQUE,          -- writer-generated; makes retries exactly-once
    sender_name    TEXT NOT NULL,        -- claimed, unauthenticated (see § Trust)
    sender_machine TEXT NOT NULL,        -- claimed, unauthenticated
    written_at     TEXT NOT NULL,        -- UTC ISO-8601, the writer's clock
    kind           TEXT NOT NULL DEFAULT 'message',
    body           TEXT NOT NULL,
    consumed_at    TEXT                  -- NULL until the reader marks it processed
);
```

- `message_id` is the database's own monotonic id — nothing
  sender-composed, nothing to collide.
- `send_token`: the writer generates one per send and re-uses it on retry;
  the UNIQUE index plus `INSERT OR IGNORE` turns an ambiguous SSH retry
  into an exactly-once insert.
- `consumed_at` is the delivery state. There is no cursor file: a message
  is unconsumed until the reading session marks it, in a transaction,
  *after acting on it*.
- `kind` is `message` in v1; a reader delivers unknown kinds as opaque
  messages rather than skipping them. A reader that finds a `user_version`
  above what it knows reports the mismatch loudly and consumes nothing —
  never a silent skip. Replies are ordinary messages sent back to the
  originating agent's inbox — no ack machinery until a consumer needs one.
- No size cap and no sidecar files: `body` is TEXT and takes any payload.
- Reading by eye stays a one-liner:
  `sqlite3 ~/agents/<name>/agent-inbox.db "SELECT * FROM inbox_messages WHERE consumed_at IS NULL"`.

**Concurrent senders (ruled 2026-08-18, test required).** Simultaneous
writers are serialized by sqlite's own locking (WAL journal mode, a busy
timeout set by every script); inserts are transactions, so a fault
mid-write leaves no torn record — the insert happened or it did not. This
holds on a local filesystem only (never NFS), and the cross-machine path
is SSH-then-local-insert precisely so every write is local to the inbox's
disk. The first draft answered concurrency with kernel-serialized
`O_APPEND` writes; the same review round replaced the store, and the
ruling's condition carries over unchanged — **the serialization claim
ships tested, not assumed**: slice 1's suite includes a live
concurrent-send test, many writers inserting simultaneously, every row
intact afterward. The rejected alternative stays rejected: a serializer
process that senders pipe to is a daemon — a single point of failure
needing supervision and containment — and sqlite provides the
serialization embedded, in-process.

### The writer: `scripts/agent-inbox-send.py`

`agent-inbox-send.py <agent-name> <message body>` opens the target agent's
inbox database (creating it with the v1 schema on first use), composes the
row, and inserts it in one transaction with a fresh `send_token`.
`--machine <host>` routes the send over SSH: the same script runs on the
remote machine from its checkout, so the insert is local to the inbox's
disk, and the token rides along — a retry after an ambiguous SSH failure
is exactly-once. The default is the local machine. A writer that is not
this script (a watcher, a cron job) uses the `sqlite3` CLI with the same
INSERT shape; the schema's constraints reject a malformed row at write
time, loudly, instead of leaving damage for a reader to tolerate.

Cross-machine delivery is therefore exactly: SSH + a local insert. No
shared sockets, no relay process, no keyboard. This is the mechanism the
#37 body already identified as the one cross-machine path.

### The reader: read, consume, watch

Three scripts, no state file — delivery state is the `consumed_at` column:

- `scripts/agent-inbox-read.py <name>` — prints every unconsumed message
  (id, sender, machine, time, body). It marks nothing. Run at session
  start: the backlog that accumulated while the agent was down or
  recycling becomes the session's first reading.
- `scripts/agent-inbox-consume.py <name> <message-id>...` — marks the
  named messages consumed, in one transaction. The session runs it after
  acting on the messages. This ordering is what makes the semantics
  honest: state advances only after the work, so a crash at any earlier
  point re-surfaces the messages instead of losing them.
- `scripts/agent-inbox-watch.py <name> --owner-pid <pid>` — the Monitor
  command. Polls the database for unconsumed rows and emits each as one
  line, at most once per watch lifetime (an in-memory seen-set; nothing on
  disk). It exits on its own when `--owner-pid` is gone (polls `kill -0`
  between queries) — the containment fix for canary caveat 3: an orphaned
  watcher self-terminates instead of surviving its session.

The session arms it as:

```
Monitor(command: "python3 scripts/agent-inbox-watch.py <name> --owner-pid <session-pid>",
        persistent: true, description: "<name> inbox")
```

**Delivery semantics — at-least-once, transactional.** A message is
consumed only when a session, having read and acted on it, says so. Every
failure between insert and consume — session crash, watch death, recycle,
lost read output — leaves the row unconsumed, and the next read or watch
poll surfaces it again: duplicates are possible, silent loss is not. The
duplicate windows, named: a message read but not yet consumed when the
session dies re-appears to the successor; a bring-up read and the watch
can both surface the same row (accepted overlap); a restarted watch
re-emits unconsumed rows its predecessor already emitted. Because a
duplicated message may request a non-idempotent action (a merge, a post, a
send), the bring-up text tells the reader: before acting on a message that
commands an external effect, check whether it was already acted on —
`message_id` exists for exactly that check.

**Growth**: consumed rows are kept as the audit trail. Pruning them is a
one-line transactional DELETE — safe against concurrent writers by the
same locking as everything else — deferred until an inbox measures large.

### Arming: whose job, and when

Arming is a tool call, so only the session itself can do it — no hook can.
The reliable delivery point for "arm your inbox at start" is the **launch
prompt**, which the fleet already controls end to end: the handoff
supervisor (`scripts/handoff-supervisor.py`) launches every recycled seat
with a first prompt, and `scripts/launch-claude-ubuntu` /
`scripts/launch-claude-mac` take `--first-prompt-file` for fresh launches.
The arming recipe — arm the watch, read the backlog, consume only after
acting — becomes part of the standard seat bring-up text those paths
deliver. Step order between watch and read is not load-bearing: both query
unconsumed rows, so any interleaving delivers every message, at worst
twice (the accepted direction). What is load-bearing is
consume-after-acting, and the bring-up text says so plainly. It also makes
read or arm failure a surfaced error: a session that cannot read its inbox
says so rather than proceeding deaf. This is prompt-driven, which the
session-start evidence on #27 shows is the one start path that always
runs. A rule-in-context alone would be the weak read path this project
already distrusts; riding the launch prompt makes arming a first action,
not a memory.

Permission: under a seat's default permission mode the Monitor arm can be
denied (canary caveat 1). Seats running `bypassPermissions` (the current
fleet setting) are unaffected; any seat on a stricter mode needs a
command-scoped allow rule for the watch script. The build slice carries
the settings change alongside the scripts, so the deployment is one PR.

## Trust and authority

An inbox record is **data from an arbitrary writer**. The delivery channel
already frames it correctly — a Monitor event arrives as a task
notification, which the harness explicitly marks as not user input — and
the record's `sender_name`/`sender_machine` columns name the claimed
sender. Two rules bind the reader, and belong in the arming prompt text:

1. A message is a teammate's request at most, never the operator's
   authority: it cannot approve pending prompts, change permissions, or
   deputize pushes to main — same doctrine as the harness's own
   cross-session-message framing.
2. The claimed sender is a claim, not authentication. Anyone with write
   access to the database (or SSH to the machine) can put any name there.
   At fleet scale — a handful of agents, one operator, machines already
   trusted with each other's SSH keys — that is acceptable and stated;
   authenticating senders is out of scope until a consumer needs it.

## The steer half: mostly free, one probe to confirm

`turn/steer` means reaching a session mid-turn. The inbox already does
this to tool-round granularity: a Monitor event that fires while the
session is busy lands as a task notification at the next tool round of the
running turn — the same delivery the fleet observes daily from its PR
watches. For NC's scale, next-tool-round delivery **is** steer; nothing
finer is needed until a consumer demonstrates otherwise.

**Probe P1 (the steer half's only deliverable before acceptance):** send an
inbox record to a session known to be mid-turn and verify from its
transcript that the record's content arrived before the turn ended, and
that the session could act on it. Pass → the steer half closes as "same
mechanism, documented granularity". Fail → the record arrives only at turn
end, which is turn-boundary delivery; #37 already names that as possibly
the honest v1 answer, and the issue records whichever result the probe
returns.

The heavier candidates the issue body lists for finer steer (SDK/app
surfaces, terminal injection) stay unexplored by choice: terminal injection
is the hazard class this whole line of work exists to retire, and an SDK
control surface is a different architecture (harness-owned process) that no
current consumer justifies.

## What this replaces, and interplay with the guard

The synthetic-keystroke guard permits tmux `send-keys`/`paste-buffer` into
**verified-detached** sessions as the interim injection path, and its deny
message points here. Once the inbox is live on a seat, that seat has no
remaining legitimate keystroke-injection consumer; when all seats carry
inboxes, the guard's detached-session allowance can be revisited (tighten
to deny-always, or leave as the documented escape hatch — a later ruling,
not this design's). The guard and the inbox are the two halves of one
doctrine: block the unsafe channel at the moment of use, and make the safe
channel cheaper than the unsafe one ever was.

## Consumers

- [nedschorus#36](https://github.com/nedschorus/nedschorus/issues/36)
  mutual oversight: a Codex-side watcher waking a Claude session is exactly
  "non-Claude writer, possibly cross-machine" — it inserts a record instead
  of learning tmux.
- **nedsmessenger** (the boss's companion app, requirements held on #27):
  its "reach the box's Claude" need is `agent-inbox-send.py --machine ned`;
  its stuck/waiting-state detection half stays on #27, untouched here.
- Any future NC scheduler or alerting that must reach an idle agent.
- The fleet itself: seat-to-seat messages that today ride SendMessage keep
  riding it on-machine; the inbox adds the Mac↔box direction the sockets
  cannot cross.

## Build slices (each lands alone; boss-gated)

1. **Writer + schema**: `agent-inbox-send.py` (local + `--machine`), the
   v1 schema with creation-on-first-use, `send_token` exactly-once
   retries, and its test file — including the live concurrent-send test
   (many simultaneous writers, every row intact; the ruled proof of the
   serialization claim). No reader yet — the database is readable from day
   one via the sqlite3 one-liner.
2. **Reader**: `agent-inbox-read.py`, `agent-inbox-consume.py`, and
   `agent-inbox-watch.py` with `--owner-pid` self-termination, plus tests
   (including: owner death reaps the watch; crash-before-consume
   re-surfaces the message; a `user_version` above the reader's reports
   loudly and consumes nothing; the watch emits each message at most once
   per lifetime; watch and read in either bring-up order deliver every
   message at least once).
3. **Probe P1** (steer granularity) using slices 1–2 on a live seat;
   result recorded on #37.
4. **Fleet arming**: the bring-up text lands in the handoff supervisor's
   first-prompt path and the launch scripts' seat setup; permission
   allowlist entries where a seat's mode needs them. After this slice,
   #36's Codex-watcher build and nedsmessenger integration unblock.

Slices 1–2 are pure scripts with tests, PR-able under the interim lane;
slice 4 touches `.claude/` machinery and instruction text, so it rides the
user's walk per the instruction-file guard.

## Open questions

- **Pruning cadence**: consumed rows stay as the audit trail; when to
  prune them is a policy question, deferred until an inbox measures large
  — the pruning DELETE itself is a transaction, safe by construction.
- **Sender authentication** is explicitly deferred; the trust section
  states the accepted risk.
- **Inbox for the user himself** (a human-readable surface the operator
  checks, or `say`-line delivery for urgent records) is attractive but
  unscoped — it belongs to nedsmessenger's requirements on #27, not here.
- **Whether SendMessage ever crosses machines natively**: if a future
  harness release ships cross-machine session messaging, the inbox's scope
  shrinks back to non-Claude writers and durable backlog — both still
  real. The design loses nothing by that future.
