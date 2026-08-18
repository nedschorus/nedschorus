# Multi-machine, multi-agent comms — design inputs survey (draft)

Commissioned by the boss 2026-08-18, mid-way through the #37 inbox design's
md-review walk: locate the earlier complete-comms-system designs and start a
more complete comms design — multi-machine, multi-agent — that leverages the
harnesses' own messaging abilities (Claude's cross-session messaging, which
did not exist when the earlier designs were written; possibly the Codex App
Server's turn primitives). This survey is the found record plus the proposed
design shape; it decides nothing.

## The prior designs, found

1. **The comms bridge** — `docs/cross-project/comms-bridge-spec.md`
   (specification, boss-designed, adopted verbatim 2026-07-20, re-derived
   2026-07-21 against six ruled inputs on
   https://github.com/nedschorus/nedschorus/issues/5). Append-only log-pair
   channels: one channel = two files, write only your own, read only the
   other's; atomic appends via a shared ~30-line utility; entry ids
   channel-namespaced and restart-proof; reader checkpoint written AFTER
   ingestion (at-least-once, duplicates tolerated by construction);
   pull-only BY DESIGN — no wake mechanism, urgency is the boss's
   cut-and-paste relay; logs are gitignored chatter, durable content is
   PROMOTED out. Still the live spec for the founding bridge and the
   companion-era mini-comms channel.

2. **The legacy postal system** — nedlern's v3 substrate (read-only
   reference; wiring spec at
   `~/Projects/nedlern/docs/working/comms-harness-live-wiring-spec.md`,
   defect reviews and incident RCAs alongside it). A full delivery
   lifecycle over sqlite (`nedlern_postal.db`): messages,
   message_recipients state, delivery events, attention tiers,
   response-requirement ranks, a dispatcher, fire-once notices,
   reincarnation redelivery. The bridge spec's "Why not import postal"
   names it the single largest measured friction source in the legacy
   system — stranded rows, pull-only replies, delivered-but-unsurfaced
   messages, the unsolved idle-wake gap — and defers ALL of it until the
   new system has earned automation. Its incident corpus
   (`comms-v3-reference-canaries/v1-*.md`: triple delivery, t0 delivery
   loss, replay loops, idle-wake gaps) is the strongest available evidence
   about which comms failure modes actually occur.

3. **The comms backlog** — pair #10 § communications backlog, dispersed
   2026-07-25 (walk 17 cluster 1) into GHIs. The still-open ruled inputs:
   per communication type, decide whether a supported API or MCP carries
   it; preserve BOTH agent-level and task-level addressing where each is
   useful (both on https://github.com/nedschorus/nedschorus/issues/1 and
   the bridge spec § Open); boss-notification mechanism rides
   https://github.com/nedschorus/nedschorus/issues/26; console insertion +
   stuck/waiting detection is
   https://github.com/nedschorus/nedschorus/issues/27.

4. **The current generation** —
   https://github.com/nedschorus/nedschorus/issues/36 (mutual oversight;
   proven: Claude watches Codex transcripts via Monitor, Codex reads Claude
   transcripts live; Codex-side wake = App Server turn/start, thin build)
   and https://github.com/nedschorus/nedschorus/issues/37 + its pair
   `docs/issues/37-agent-inbox-messaging-design.md` (sqlite inbox +
   Monitor wake; design mid-md-review on branch
   agent-inbox-messaging-design, walk paused for this survey).

## What changed since those designs

- **The harness now ships same-machine messaging**: ListAgents +
  SendMessage over per-machine sockets. Delivery to busy sessions at the
  next tool round; a send wakes an idle session. This retires the bridge's
  pull-only compromise and the postal dispatcher's whole reason to exist —
  ON one machine, BETWEEN Claude sessions.
- **Monitor wake is proven** (5/5, ~3 s, canary on #27) — the idle-wake gap
  that postal never solved has a working answer any file/db change can
  trigger.
- **Cross-machine session messaging tested absent** (2026-08-17 LAN test,
  both directions; Remote Control ruled not pursued).
- **Codex side**: App Server turn/start (idle inject) and turn/steer
  (mid-turn) exist as supported primitives; Codex has no Monitor
  equivalent (#36's evidence).

## The proposed shape: a layered composition, not a new system

Each layer uses the most-native mechanism that exists there, and the
layers compose rather than duplicate:

| Layer | Carrier | Status |
|---|---|---|
| Claude↔Claude, same machine | harness SendMessage | ships today, in daily fleet use |
| Any writer → Claude, any machine | #37 sqlite inbox + Monitor wake | design mid-review |
| Any writer → Codex | App Server turn/start | thin build, evidence on #36 |
| Codex → Claude | writes the #37 inbox (a non-Claude writer) | falls out of #37 |
| Boss ↔ any agent | nedsmessenger over the inbox; `say` for urgent-attention | requirements on #27 |
| Boss-readable durable coordination | the bridge log-pairs, unchanged | live spec; chatter, not delivery |

What this composition retires, keeps, and owes:

- Retires: any postal import; the bridge as a DELIVERY mechanism (it
  remains the boss-readable coordination record); tmux keystroke injection
  (already guard-blocked, #27).
- Keeps: the bridge spec's ruled protocol wisdom — checkpoint-after-
  ingestion, at-least-once with tolerated duplicates, promotion-out of
  chatter — all of which #37's consume-after-acting protocol already
  inherits.
- Owes (the open ruled inputs from #1 that a full design must answer):
  API-vs-MCP per communication type; agent-level vs task-level addressing.
  #37 answers agent-level only; task-level addressing is unaddressed in
  the current generation.

## Proposed next steps (boss-gated, in order)

1. Finish the #37 md-review walk and land that design — it is the load-
   bearing new layer, and its review findings are already half-processed.
2. Write the layered composition as the comms design of record (a
   cross-project MD superseding nothing but positioning everything: the
   bridge spec stays, postal stays retired, #36/#37 become layers) — with
   the two open #1 inputs either answered or explicitly carried.
3. The Codex-side thin build (#36's watcher + turn/start injector) after
   #37's slices prove the pattern.
