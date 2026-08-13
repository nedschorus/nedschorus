<!-- provenance: runtime=claude model=claude-fable-5 effort=xhigh attack=fresh-eyes doc=gatekeeper isolation=empty-scratch-directory -->

## 1. Your solution sketch

**Core stance.** The only identity that can push to `main` is a single non-agent identity; everything agents do goes through one deterministic script that serializes landings, checks the exact post-merge content, and writes its receipt into the merge commit itself. No daemons, no queues, no prompted intermediary. Model judgment appears nowhere in the landing path; human judgment appears only post-land (review-and-revert), never as a gate.

**Components.**

1. **Agent workspace layout.** Each agent session works in its own git worktree on its own branch; no writable checkout of `main` exists anywhere an agent writes, and agents hold zero GitHub credentials. "Commit to wrong branch" and "push to main" become mechanically impossible, not trained-against. A setup script (re)creates this layout so it survives recycled sessions.

2. **The `land` script** — the entire gatekeeper, a deterministic script run on demand. It executes as a dedicated Unix user (`lander`), the only holder of the GitHub push token, reachable by agents through a locked-down sudoers entry that permits exactly this one command. Steps, all inside a `flock` (which auto-releases on process death) and with `timeout` on checks:
   - Fetch the candidate SHA directly from the requesting agent's repo path (agents never need push credentials, even for branches).
   - Fetch `origin/main`; in a fresh temp worktree, merge the candidate onto the current tip. Textual conflict → refusal telling the agent to merge main and resubmit.
   - Run the in-repo check suite against the *merged* tree — this is the "exactly the content that lands" guarantee; never check the branch tip.
   - On green: finalize the merge commit with machine-readable trailers (`Request-Id`, `Change-Id`, `Requested-By`, `Source-SHA`, `Checks:` names+results, `Reason:` the requester's stated why) and push to `main`.
   - If the push is rejected non-fast-forward (the boss intervened directly), refetch–remerge–recheck and retry a bounded number of times, then refuse with that reason.
   - Emit a receipt as structured JSON on stdout either way: verdict, reason code, failing-check output (truncated), and a concrete next action an agent can execute.

3. **`land status <sha|change-id>`** — read-only recovery query. "Did my request land?" reduces to `git merge-base --is-ancestor` plus a trailer search of `main`'s log. A reconnecting or restarted agent answers its own question without a human and without any state outside git.

4. **Check suite, versioned in-repo,** tiered by change class: full build/test for code, fast validators for documents and records (seconds, not minutes — a slow gate on trivial changes breeds bypass pressure). Guard-the-guard rule: any diff touching the check definitions or the land tooling itself is refused pending explicit boss ack.

5. **GitHub branch protection / ruleset as backstop.** Only the lander's machine account may push `main`; the boss's account is on the bypass list. Even a leaked token or a confused local git cannot bypass policy, and the boss can always intervene from the Mac.

6. **Durable record = git history itself.** Success receipts are the merge-commit trailers — atomic with the landing (a push either happens or doesn't; the receipt cannot be separated from it), findable later with `git log --grep`, no side files. Refusals are returned synchronously and appended best-effort to a `refs/land/refusals` ref with the refused candidate kept under a TTL'd ref (so forensics survive GC); because checks are deterministic, any lost refusal is reproducible by resubmitting.

7. **Janitor-in-line.** The first step of every `land` run heals the last one: remove stale temp worktrees, prune expired refused-candidate refs, sanity-check disk and token, refusing with "infrastructure sick: X" if broken — so infra failures teach too. No cron, no daemon; the next landing cleans up the previous crash.

**Failure map.** Crash mid-landing: flock dies with the process, orphaned temp state is cleaned next run, and push atomicity means `main` is never half-updated. Lost reply: rerun `land` (idempotent — an already-landed SHA returns "already landed" success) or run `land status`. Duplicate submission after amend/rebase: the `Change-Id` trailer catches the same logical change under a new SHA and warns instead of double-landing. Concurrent submissions: the lock serializes; the loser re-merges against the new tip. Broken work: refused with failing output and next steps. Hung check: killed by timeout, refusal says so. GitHub down: refusal "remote unreachable, retry later" — the agent's branch is safe locally, nothing corrupts. Boss pushes directly: absorbed by the retry loop. Bad change that passed checks anyway: boss reviews landed history at leisure and reverts — a contained, cheap failure, deliberately preferred over pre-land human gating.

## 2. The hard parts

1. **The credential boundary on a shared box.** If agents run as the same Unix user as the lander, the isolation is fiction — any agent can read the token. Prototype first: create the `lander` user and sudoers entry, then, acting as an agent, try to read the token and push directly. Failure mode is silent (nothing breaks until an agent bypasses); detection is the GitHub-side push restriction rejecting it, which is why the backstop is not optional.
2. **Crash-anywhere recovery.** The autonomy claim is only as good as this. Test mechanically: `kill -9` the land script at every step boundary, then assert the next `land` heals and `land status` tells the truth. Especially the window between merge-commit creation and push.
3. **Contention plus boss races.** Script two agents landing while the boss pushes directly; verify the retry loop converges and that nothing ever lands checked against a stale tip. The "exactly the content that lands" goal lives or dies here.
4. **Check duration versus serialization.** I could not verify check runtime or landing rate. If checks take 10 minutes and several agents land hourly, the lock queue becomes the system. Experiment: measure the real suite and real landing cadence; if the product is bad, batching (test several candidates merged together, bisect on failure) is the known escalation — decide the trigger threshold now.
5. **Retry identity under real agent behavior.** Agents amend and rebase, changing SHAs; SHA-only idempotency then double-lands after a lost reply. Experiment: simulate lost-reply-then-amend-resubmit and confirm the Change-Id dedup catches it.
6. **GitHub plan capabilities.** Whether this repo's plan supports restricting pushes on a branch to one identity with a bypass list is a fact I couldn't verify. Experiment: configure it and test-push from a non-lander account.
7. **Refusal findability from the Mac.** Custom refs and notes don't fetch by default; verify the boss can actually see refusal records without asking anyone.

At 2am nothing pages, by design — there is no daemon to die. Failures surface as the next agent's refusal, which is the intended notice channel; the classes that escape it are slow rot (disk fill from temp state, branch litter, token expiry), which is what the in-line janitor and doctor check exist to convert into legible refusals.

## 3. Late discoveries

Class-typical traps in landing/merge-queue systems, whether or not my sketch covers them:

- **Checking the branch tip instead of the merged result.** Teams discover semantic conflicts (two individually green branches that break combined) only after post-merge breakage. Any design that checks pre-merge content has a drift window.
- **The gate can edit the gate.** A candidate diff that weakens the checks or the land tooling sails through the checks it just weakened. Cheap at design time (refuse or escalate diffs touching the guard); expensive after the first bad landing.
- **SHA identity breaks under amend/rebase.** Lost reply → agent amends → resubmits "the same" change with a new SHA → lands twice. Gerrit invented Change-Id for exactly this; retrofitting identity after duplicates exist is painful.
- **Side records that don't travel.** Git notes and custom refs are durable but invisible — they don't clone or fetch by default. The record "exists" and nobody can find it, violating findability late and silently.
- **GC eats the evidence.** Refused candidates are unreferenced objects; months later, "what did that refusal actually contain?" is unanswerable unless refused refs are kept deliberately.
- **Flaky checks corrode everything.** Refusals become noise, agents learn to retry-spam, and refusal-as-teaching dies. A flakiness budget and quarantine path are cheap early, culture-war expensive late.
- **The lock is host-local.** The day a second box or a cloud agent joins, flock serialization silently vanishes with no error. If serialization lives on one host, that fact must be loudly asserted, not assumed.
- **Client-side prevention doesn't propagate.** Hooks aren't cloned; worktree layouts drift. Any local guard not reinstalled mechanically by setup is absent on the next fresh checkout, silently.
- **Secrets on main are forever.** Once pushed to GitHub, history rewrite is agony. A pre-land secret scan is nearly free at design time.
- **The boss's bypass becomes the leak.** If the boss routinely pushes unchecked work directly, agents build on unvetted content and the gate's guarantees erode — the bypass must stay exceptional, or the boss should use the gate too.
- **Receipt schema becomes API.** Agents parse the refusal JSON and the trailers; unversioned, any format change breaks the fleet's recovery logic at the worst time.
- **Volume skew.** "Records" and doc changes usually dominate landings; if the gate prices every landing at full code-check cost, agents batch, delay, or route around it.
- **Shared-checkout corruption.** Concurrent sessions in one worktree collide on `index.lock` and mixed staging long before they collide on main; per-agent worktrees need enforcement, not convention.
- **Timestamps and clocks.** Receipts need one clock (the lander's); requester-supplied times end up in the durable record and lie.

## 4. Assumptions

1. All agents run on the one Ubuntu box, and no second agent host is imminent — host-local locking and fetch-from-path depend on this.
2. Unix user separation is available: a `lander` user can exist, agents don't run as root or as that user, and agents can invoke sudo for one whitelisted command.
3. Agents need no GitHub credentials of their own — branch backup to the remote, if wanted, can go through the lander.
4. The repo's GitHub plan supports restricting `main` pushes to one identity with a boss bypass.
5. A deterministic check suite exists or will be written; runtime is minutes, not hours; flakiness is manageable.
6. Landing rate is tens per day, not hundreds per hour — plain serialization suffices, no batching.
7. Post-land boss review with revert-as-remedy is acceptable; no change class requires pre-land human approval (except changes to the gate itself, which I chose to escalate).
8. Merge commits on `main` are acceptable — my recovery story (ancestor test on the original SHA) leans on them; a strict-linear-history requirement would force a different identity scheme.
9. The repo is moderate size with no submodules or LFS; a temp worktree per landing is cheap.
10. GitHub reachability is an acceptable landing dependency; pausing landings during an outage (agents keep working on branches) is fine, i.e., the authoritative remote is GitHub rather than a bare repo on the box.
11. The "why" in the durable record is the requester's stated intent, recorded but not verified.
12. The boss interacts only via GitHub from the Mac and never needs to hold the box-local lock.
13. There is a single target branch (`main`) — no release branches, cherry-picks, or backports.
14. Agents are trusted-but-fallible, not adversarial: the design defends against mistakes and crashes mechanically, but a deliberately malicious agent with shell access on the same box is out of scope beyond the credential separation described.
