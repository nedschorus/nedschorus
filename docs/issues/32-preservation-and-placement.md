Issue: https://github.com/nedschorus/nedschorus/issues/32

# What NC Preserves, Where It Goes, How That Is Codified, and How It Is Kept From Drifting

The preservation-and-placement design pair. Substance walked and ruled by the
boss 2026-07-27/28 (the standing-items walk's preservation thread); this
document carries the walked content, the issue carries the state. Destination
form, boss-set: this graduates into a wiki page with subpages when matured.

## Part 1 — the inventory: four classes, each with its recovery story

### Class 1: git-preserved (free — preservation is a side effect of normal work)

Files on main; check-ins (commits, whose provenance trailers are the single
import record); pair documents; wiki pages; queued MDs; handoffs and their
task exports. Git keeps the versions of tracked files, so deleting
committed content here is recoverable rather than lost — a struck file remains one command away in
history. This class is the reference standard: the further a class sits from
"preserved as a side effect of normal work," the more deliberate machinery it
needs.

### Class 2: vendor-preserved (the vendor's job — the fleet builds nothing)

GitHub-held state (issues with their comments and labels, repository
settings, Actions secrets) and the boss's desktop-app conversations (stored
with his provider account). Boss-ruled: we do not take on responsibility for
backing up other people's or other companies' data; export or snapshot
machinery for platform-held state is make-work. One free decision rides this
class: when the legacy system is decommissioned, ARCHIVE its repository
rather than delete it — archiving costs nothing and keeps every issue and URL
readable.

### Class 3: machine-local (the only class where preservation takes real decisions)

Session transcripts (the logs — also the re-creation substrate: much else is
recoverable from them, which lowers what needs preserving elsewhere);
memories (cross-session by design); tasks (in the harness store — not
preserved today, planned to be); production databases (messaging, alerts);
global instruction files (global CLAUDE.md — now deliberately empty — global
skills, settings, keybindings, the harness's own state file `~/.claude.json`);
per-worktree identity and local settings (`.mcp.json` — who each agent is —
and `settings.local.json` with its accumulated permission grants); deployed
runtime state (installed scheduled jobs and daemons). The machine-level
answer is per-machine (updated 2026-07-28, boss-supplied facts + verification):
on the Mac, Time Machine; on the NC Ubuntu box, Timeshift to an external
3.7 TB drive — VERIFIED WORKING as of 2026-07-28 after repair (it had one
snapshot from setup day, every schedule off, and home excluded; now hourly +
daily schedules run by cron and /home including the Claude state is captured,
confirmed by artifact in snapshot 2026-07-28_13-03-17). Two lessons from the
repair ride here: Timeshift's exclude array is a GENERATED artifact — edits
to it are overwritten from the per-user model each run; the include-pattern
form is the stable control (anti-drift discipline 2, met in the wild); and
live DATABASE files need their own online-dump job before a file-copier can
preserve them reliably — a copier reading a live database mid-write can
capture a torn copy (no databases on the box yet; the pattern applies when
the first one lands). The legacy record separately shows how thin
machine-backup discipline runs (a designed fleet backup was ratified, merged,
and never wired). The design direction is that
this class SHRINKS by placement (part 2) rather than growing a backup system.
The settings/permissions members are mostly regenerable-by-use (re-login,
re-grant) — loss is friction, not lost work.

### Class 4: deliberately unpreserved (recorded, so absence reads as intent)

Dropped by design: scratchpads, intermediate outputs, rendered reports
(regenerable from source data), the gatekeeper's transient workspaces (a
refused check-in deliberately leaves nothing), working files that never enter
a queue or home. Regenerable by design: credentials (boss-ruled — recovery is
minting a new one rather than restoring a copy; forced regeneration is rotation, a
safety gain; the real dependency is the boss's account access, which only he
holds), external tools and platforms (reinstallable; compatibility is not the
code writer's job — record an environment detail only where a specific
attestation's validity turns on it), deployed state where installation stays
scripted, permission grants (regenerate by use).

**The economics principle (boss-ruled, governs the whole inventory):** losing
a small fraction of work — five percent — is better than hoarding low-quality
material. Every kept artifact taxes file listing, search, and context
windows; memories beyond working-set size stop functioning as memories.
Aggressive dropping is maintenance, not negligence.

## Part 2 — what goes where

One rule: **state whose value outlives a session belongs in the repository,
moved there at a natural boundary; machine-local holds live working state;
the global scope stays empty.** Per member: tasks — already placed by the
approved handoff design (export to files, check in at each handoff); memories
— machine-local decision-queue store, drained by the boss (resolved below,
2026-07-31); transcripts — full logs stay local (size), boundary
extracts are the bridge specification's open question, not re-decided here;
databases — live data stays live, the accepted Time-Machine residue;
instruction files — in-repo (NC's CLAUDE.md is a step-2 repository
file; the global file stays empty — the 2026-07-27 cross-project
contamination incident is this rule's founding specimen, recorded on
[nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29)); agent
identity — recreatable from the briefing, itself a repository file.

Within-repository placement (which directory, which queue, which name) is
already governed by the artifact-lifecycle rule (founding plan § Project
organization) and the naming rules; this part cites them and adds nothing —
one concept, one home.

## Part 3 — codification: the duties land in builds already planned

- **The git-gatekeeper** ([nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3))
  owns the git-preserved class's entrance; its commit trailers are the
  provenance record. This design adds requirements, not features.
- **The handoff build** ([nedschorus#2](https://github.com/nedschorus/nedschorus/issues/2))
  owns the boundaries: task export, the scrub (its standing duties are
  enumerated on that issue), and — if the open questions resolve that way —
  log extracts and memory placement at the same boundary.
- **The writing skills** (`ghi-write` / `md-write`,
  [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13)) own
  within-repository placement at writing time — the established pattern:
  enforcement lives in skills at the moment of writing; the gatekeeper stays
  lean.
- **The wiki page this pair graduates into** owns the recorded inventory
  itself, including class 4, so absence keeps reading as intent.

## Part 4 — maintenance: keeping the parts from drifting apart

Four things change independently — the inventory, the placement rules, the
codifying builds, and reality on disk — and the legacy record shows every
pairwise drift, each caught by accident, none by machinery. The design:

**Three disciplines (prevention):**
1. One home per fact, pointers everywhere else — copy-drift disappears
   when a fact exists once; record-versus-reality drift remains, which is
   the sweep's territory.
2. Any list that mirrors what a mechanism enforces is generated from the
   mechanism or checked against it (extraction-walk rule; the legacy
   approval-required-list drift is its specimen).
3. When drift is found, name which side is wrong — the record lags the
   mechanism or the mechanism lags the decision — and fix that side. The
   legacy's worst drifts survived because both sides stayed standing, each
   plausibly authoritative.

**Detection is the guarantee (boss-directed design):** autonomy is
deliberate — agents create tasks, memories, GHIs, MDs, and files we do not
fully control — so contracts alone are not reliable. Each class in this
inventory lives in an enumerable store with timestamps, so a **watermarked sweep** answers
"what is new since last time" completely and cheaply per store: git for repo
files, one API call for issues, directory listings for tasks, memories, and
stray state.

**The sweep is a scheduled PROGRAM, not an agent session** (boss-ruled): the
detection half is purely mechanical — zero token cost, deterministic,
testable, and cron-schedulable with no idle-wake dependency. It classifies
each find against the placement rules; its safe action is **archiving** —
moving or marking processed things out of the processing queue (reversible,
so automation-safe under the undoable-is-safe calculus). Version 1 deletes
nothing itself: **archives expire on a 30-day TTL**, and that expiry is the
deletion path — time passing on something already reviewed-or-archived, with
a 30-day recovery window. Only
the unclassifiable residue goes to an agent (or the boss) for judgment:
tokens go to judgment rather than enumeration. Sensors are programs;
judgment is agents.

**The handoff scrub remains** the persistent agents' own moment (its duties
enumerated on [nedschorus#2](https://github.com/nedschorus/nedschorus/issues/2));
the ownership discipline — a temporary worker returns its deliverable to its
dispatcher and leaves nothing behind, with the dispatcher's own records
making orphaned dispatches visible — reduces the sweep's load but is not the
guarantee. No dedicated drift-detection machinery beyond the sweep until
incidents earn it, per the enforcement ladder.

## Open questions (state carried on the issue)

1. **Memory placement — RESOLVED (boss-walked 2026-07-31, fleet-side walk
   item 6):** the memory store is **machine-local working state, not
   repository content** — a decision queue under the artifact-lifecycle
   rule, one store per project shared across all worktrees (per-worktree
   stores would fragment one fact into drifting copies).
   - **Working tier:** agents write memories freely to the local store;
     nothing is committed at write time. Real-time visibility comes from
     instrumentation, not git: every memory read and write is echoed to the
     console, remind-tier
     ([nedschorus#39](https://github.com/nedschorus/nedschorus/issues/39));
     the boss intervenes by prompting the acting agent.
   - **Content rule — memories are memories, not soft skills.** Two admitted
     classes: (a) durable human-context facts (the boss's name, role,
     preferences, plans); (b) staged lessons whose structural home does not
     exist yet, drained into that skill, hook, or doctrine line at its build
     (the founding plan's step-1 drain). Instruction-shaped content whose
     home already exists never persists as a memory — a surprising ruling
     ("always X," "never Y") goes to its doctrine line, hook, skill, or
     code, not into the store.
   - **Preservation is the drain, not the write.** The boss walks the store
     at his cadence; per entry: reject-delete (expected majority), redirect
     to its structural home (lands via a normal check-in), keep as memory,
     or leave queued. Kept survivors are committed in **one batched check-in
     per drain** — main receives one curated commit per drain, never
     per-write churn, and nothing reaches the public repository before the
     boss's review. The handoff scrub reports the store's depth and
     oldest-entry age alongside the other queues, so the queue rots
     visibly, never silently.
   - **Accepted residual (boss-ruled 2026-07-31):** undrained entries are
     unbacked between drains — machine loss loses them; cheap by the
     drain's own economics (most entries are headed for deletion or
     relocation anyway); the outside-git backup question stays at
     [nedschorus#7](https://github.com/nedschorus/nedschorus/issues/7).
     Reopening trigger: an undrained memory loss that costs real work.
   - Feeds the memory-pointing research on
     [nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29).
2. **Log extracts at boundaries:** already open in the bridge specification;
   owned there, tracked here only as a placement consumer.
3. **Shared-store writes by temporary workers:** ban them (workers return
   content; only persistent agents write shared stores) or allow them and
   sweep entries whose originating session is dead. The first is simpler;
   the second matches how scheduled routine runs would need to work anyway.

## Relations

- Backup of state outside git (the class-3 leaf): https://github.com/nedschorus/nedschorus/issues/7
- The handoff build and scrub duties: https://github.com/nedschorus/nedschorus/issues/2
- The git-gatekeeper: https://github.com/nedschorus/nedschorus/issues/3
- The writing skills: https://github.com/nedschorus/nedschorus/issues/13
- Queue drain procedure: https://github.com/nedschorus/nedschorus/issues/24
- The dynamic agent-team model (workers, dispatchers, sensors-vs-judgment): https://github.com/nedschorus/nedschorus/issues/26
- Runtime-behavior research (instruction surfaces; the contamination specimen): https://github.com/nedschorus/nedschorus/issues/29

—
Session: 3b576242-213e-43a2-bd16-80a1a36f67e7 (new-vp)
