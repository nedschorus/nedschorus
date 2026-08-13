<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh attack=cut doc=gatekeeper isolation=instruction-pinned document set -->

# Cut report

Reviewed only the four supplied snapshots. No files were changed.

## 1. Remove agents’ branch-write capability when the gate becomes live

**WHAT** — At the C2/C3 switchover, reduce ordinary agent tokens to repository read plus issues write; remove `contents: write`. Retain branch pushing only as a time-bounded permission for the current manual lane, or deliberately restore it later if C8 selects the branch-ref design.

**WHY** — The governing contract says:

> “Ordinary changes use no branches and no pull requests.”  
> “Agents … never push themselves. One program, one credential, one door.”

([spec line 12](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:12), [line 16](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:16))

The build plan says slice 1 retires “the manual merge lane, on the happy path.” Yet C4 permanently grants agents “contents read/write (branch pushes are open).” ([plan line 37](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:37), [bindings line 53](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:53))

After activation, no named ordinary workflow consumes this capability. Public-repository reading needs no write permission, and issue work has its own `issues write` permission. C8’s branch-ref approach is only one of three “candidate shapes, none chosen,” so it is not yet a roadmap commitment. ([bindings line 135](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:135))

This collides directly with user-ruled C4. It should therefore be presented as a proposed narrowing at gate activation, not silently treated as a correction.

**LOST** — Agents lose the ability to push non-main branches after activation. The current interim lane must remain available until the gate is genuinely live. Selecting C8’s branch-ref option later would require deliberately restoring the permission. That is a one-time roadmap decision, not a recurring operator step.

**CONSEQUENCES** —

- The spec’s C4 sentence granting “contents read/write (branch pushes are open)” becomes false. ([spec line 139](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:139))
- C4’s replacement-token paragraph must say issues write rather than contents read/write plus issues write; its dry-run observation that branch pushes work ceases to describe intended steady state. ([bindings lines 55–64](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:55))
- C8’s caller-pushes-a-branch candidate must state that choosing it re-admits content-write permission. ([bindings line 140](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:140))
- No described test becomes false.

## 2. Delete the two standing audits rather than reconnecting their dead handoff trigger

**WHAT** — Remove slice 5’s trailer-absence audit and branch-protection audit after C2/C3 are installed. Do not recreate a “handoff scrub” solely to run them.

**WHY** — The specified trigger no longer exists:

> “a standing audit at each handoff scrub scans main…”

([spec line 144](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:144))

But the supplied handoff specification says “the scrub modes” were superseded and “full manual scrubs died.” Its recycle cycle names exactly one maintenance output: “one automated queue-status line”; it never invokes either gatekeeper audit. ([handoff line 8](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-fast-handoff-design-at-0890848.md:8), [line 39](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-fast-handoff-design-at-0890848.md:39))

Repairing that trigger would add gatekeeper work to a separately ruled recycle cycle. Deletion is preferable because the replacement enforcement already exists:

> “C2 is the boundary.”  
> “C3 removes that class by taking owner power out of agent hands entirely.”

([spec line 144](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:144))

The gate is dormant until that boundary is installed, so deleting these contract-only components loses no current protection. Once active, ordinary raw pushes are prevented rather than retrospectively detected. A bad landed commit remains contained to one repository and has the named revert remedy.

This cut collides with the accepted slice-5/B3c plan and the 2026-07-30 audit amendment. Those rulings require an explicit revisit.

**LOST** — Automatic detection of a stolen gatekeeper token being used outside the program, owner-caused protection drift, and audit infrastructure failures. This is a real priority-1 loss. The cut is justified only after C2/C3 and finding 1 are effective; before that point the audits still answer a real procedural gap.

**CONSEQUENCES** —

- Remove “the audits” from implementation status. ([spec line 8](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:8))
- Remove the revision note about “the branch-protection audit’s three named outcomes.” ([spec line 10](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:10))
- “loop counters and the audit” must lose the audit reference. ([spec line 59](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:59))
- The standing-audit mechanism, draft-issue behavior, three outcomes, and claimed coverage in the credential section all become stale. ([spec line 144](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:144))
- The historical table’s “procedural gap is audit-detected” needs to be marked historical rather than current. ([spec line 157](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:157))
- T12 must be deleted. ([spec line 171](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:171))
- Slice 5’s audit deliverables and B3c/T12 mapping become false. ([plan line 41](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:41))
- The plan’s “audits are detection” rationale and both-audits deferral become stale. ([plan line 69](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:69), [line 116](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:116))
- C1’s audit-firing trigger may remain only as historical provenance for admitting the dedicated identity. ([bindings line 19](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:19))

## 3. Remove the `--repo` and `--remote` test seams and therefore remove C7

**WHAT** — Delete both test-only CLI overrides and their privileged-invocation refusal. Tests can run the program with the throwaway caller repository as their working directory and configure that repository’s `origin` to the throwaway bare remote. Keep the privileged production destination pinned to the canonical repository.

**WHY** — The plan already supplies the replacement behavior: the remote “defaults to the invoking repository’s `origin`.” ([plan line 177](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:177))

The two flags exist only “so the test suite can hand the program throwaway repositories.” They then create a privilege surface which requires another rule:

> “when running as the gatekeeper user, `--remote` and `--repo` overrides are refused”

([bindings line 127](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:127))

That is self-created machinery. A subprocess working directory plus a fixture `origin` delivers the same test isolation without production options or a privileged guard.

The mechanism is also incomplete in the supplied contract: C7 promises a “named refusal,” while the fixed error catalog names no test-seam refusal. ([spec line 123](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:123))

C7 is identified as a builder-side consequence, not a user ruling, although D1 was accepted uncontested in the build-plan walk. ([bindings line 12](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:12), [plan line 242](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:242))

**LOST** — Tests can no longer nominate source and destination paths as arguments; their harness must set `cwd` and `origin`. Builder convenience pays this small priority-3 cost. Production loses an avoidable argument surface.

**CONSEQUENCES** —

- Delete the spec’s entire “Privileged invocations refuse the test seams” bullet. ([spec line 142](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:142))
- Delete C7’s heading and binding. ([bindings line 125](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md:125))
- D1’s statement that an explicit argument hands the program a fixture path must be replaced by fixture working-directory setup. ([plan line 175](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:175))
- Walk-order item 5’s “test fixture model” remains a decision point but no longer includes these flags. ([plan line 268](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:268))
- The described throwaway-repository tests remain valid; only their setup changes.
- B3a is referenced but not included in the supplied set, so its exact stale wording cannot be enumerated.

## 4. Remove the normative five-label state machine

**WHAT** — Delete `SCREENING → WORKING → PUSHING → CHECKED-IN/REFUSED` as a state taxonomy. Retain the actual mechanics and describe them through the existing procedure, observable `status` outcomes, and two durable worlds.

**WHY** — No named state field is recorded. The machine observes a workspace, a worker PID, and history. `status` returns `in-progress` or `abandoned`, not `WORKING` or `PUSHING`.

The document immediately provides a smaller complete model:

> “The whole pipeline has exactly two durable effects: the workspace directory, and the atomic push.”  
> “A crash or lost connection … leaves one of two worlds: the commit is on main, or it is not and a stale workspace remains.”

([spec line 119](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:119))

That model drives resubmission and crash recovery; the five labels drive nothing. The companion plan also calls it “the four-state model,” contradicting the five labels in the arrow. ([plan line 158](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:158))

The honest defense is that the labels make the lifecycle easier to narrate. The numbered procedure already does that without presenting transient phases as persisted states.

This cut collides with the statement that “states” belong to the boss-walked 2026-07-24 core. ([spec line 10](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:10))

**LOST** — A compact lifecycle vocabulary. Priority 2 pays that cost; no observable behavior or recovery guarantee is lost.

**CONSEQUENCES** —

- The “States” arrow and terminal labels must be removed, while its workspace, request-record, refusal-record, and sweeping rules remain as ordinary lifecycle rules. ([spec line 117](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:117))
- “`status` distinguishes WORKING from abandoned” becomes “distinguishes a live worker from a dead one.” ([spec line 119](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:119))
- T7’s “killed mid-WORKING” wording becomes “killed before push”; its behavior remains unchanged. ([spec line 171](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:171))
- The plan’s “four-state model” sentence becomes stale. ([plan line 158](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:158))

## 5. Remove explicit `--wait`

**WHAT** — Waiting should be represented only by omitting `--no-wait`. Delete the explicit `--wait` spelling.

**WHY** — The request syntax says `--wait` is already the default:

> `[--wait | --no-wait] (default: --wait)`

([spec line 43](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:43))

Explicit `--wait` and no mode flag have identical behavior, digest, records, and reply. Because the default exists, the flag does not force a caller decision. It is a dead distinction.

**LOST** — Scripts cannot spell the default explicitly. Priority 2 pays a small readability preference; behavior and autonomy are unchanged.

**CONSEQUENCES** —

- The request syntax becomes `[--no-wait]`.
- “mode choice” in Submit should refer only to opting into non-waiting operation. ([spec line 70](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:70))
- Slice 1’s “`--wait` only” becomes “synchronous/default mode only.” ([plan line 81](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:81))
- `unbuilt-option`’s next action changes from “resubmit with `--wait`” to “resubmit without `--no-wait`.” ([plan line 189](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:189))
- No described test specifically depends on accepting `--wait`.

## 6. Remove `empty-change` from the error catalog

**WHAT** — Use `unchanged-path`, listing all unchanged declared paths, when every declared path is unchanged. Delete `empty-change`.

**WHY** — `--files` must be non-empty. Each path is then either unknown, unchanged, added, modified, or deleted:

> “`unchanged-path` (declared but identical to base …), `empty-change` (nothing differs at all).”

([spec line 48](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:48))

“Nothing differs” has no unique condition: it is exactly the case where every non-empty declared path satisfies the already-defined `unchanged-path` condition. The three-part refusal can name all affected paths and preserve more specific facts. A second label merely creates validation-precedence and test obligations.

This touches the boss-walked core error catalog and therefore requires explicit ruling acknowledgement.

**LOST** — A whole-request shorthand for “all paths unchanged.” Priority 2 pays that label; no fact, next action, or refusal protection is lost.

**CONSEQUENCES** —

- Remove `empty-change` from field validation. ([spec line 48](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:48))
- Remove it from the fixed catalog. ([spec line 125](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:125))
- Remove it from slice 1’s form-error inventory. ([plan line 86](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:86))
- T1 remains, but loses the separate `empty-change` case in both the spec and build plan. ([spec line 171](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md:171), [plan line 121](/home/nedlern/agents/choirmaster/md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md:121))

## Leanness certification

I examined the request/reply contract, candidate construction, provenance fields, digest, import path, concurrency, async lifecycle, enforcement layout, cooperative hooks, break-glass, audit tier, tests, and the handoff interaction.

These parts already survive the replacement test:

- **Candidate-from-declaration construction:** the simplest replacement is a clean-worktree or staging check. Neither guarantees that only declared bytes enter while preserving unrelated local work, so construction is lean.
- **Digest plus git-history deduplication:** caller-generated IDs or a journal add state and recovery machinery. The content digest is the smallest retry-safe key.
- **GitHub’s atomic push as concurrency arbiter:** a lock or queue adds a coordinator. Atomic rejection plus bounded rebuild is smaller and more autonomous.
- **Conflict refusal:** automatic conflict resolution is simpler only superficially; it would guess author intent. The refusal is the minimal safe boundary.
- **Dedicated Unix-user credential boundary:** hooks and CLAUDE.md are the simplest apparent alternatives, but the documents establish that they are cooperative and process-readable credentials are not isolated. The Unix boundary is the minimum mechanical enforcement.
- **Required issue declaration:** omission would remove the forcing function demonstrated by the project’s recorded ruling; `none | number` is minimal.
- **Import provenance in the commit trailer:** the simplest alternative, the entry-manifest row, duplicates the record and creates a shared-file concurrency conflict.
- **No queue, lock, caller IDs, separate audit log, or impact analysis yet:** the spec has already cut these at the correct growth points.
- **Async lifecycle:** blocking execution is simpler today, but the supplied roadmap explicitly ties non-waiting operation and cancellation to future slow checks. I therefore did not report its deletion.
- **Undeclared-worktree advisory:** construction already contains accidental inclusion, but the advisory has a real human consumer and catches omitted intended files. I did not classify it as dead output.
- **`imports` query:** raw `git log` could derive the same data, but removing the command would replace a stable one-command view with remembered operator parsing. That would move cost to operation, so it is not a valid cut.