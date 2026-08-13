# Credential and hook bindings for pair #3 (git-gatekeeper) — ruled 2026-08-09

Queued for the design rewalk. Destination:
[nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3), folded into
the canonical spec `docs/cross-project/git-gatekeeper-design.md` at the walk.
Source: the user's credential discussion with choirmaster, 2026-08-09 (session
1caf1c51). These bindings amend the spec's enforcement periphery — the
credential, the account layout, and the cooperative tier around the gate. The
core contract (request/reply, digest, trailers, concurrency, states, error
catalog) is untouched.

Provenance note: items C1–C6 were ruled by the user in conversation; C7 is a
builder-side consequence; C8 is open. The design rewalk is where each ruling
gets confirmed against the whole; until the spec is updated at that walk, this
document governs these points.

## C1 — The dedicated-identity rung is admitted early, as an account

The spec names two triggers for its mechanical-closure rung: the audit ever
firing, or the boss admitting it early. The user admitted it early
(2026-08-09). Form chosen: a **dedicated GitHub account**, not the GitHub App
or CI job the spec sketched — an App/CI relocates the gate into CI, which the
spec scoped out; a plain account keeps the gate a local program. The account
is one of the user's existing accounts, added to `nedschorus/nedschorus` as a
**collaborator with write, not admin, and never an org owner**. Blast radius
of a stolen or misused token: push commits to this one repository, nothing
else — it cannot change protection, administer the org, or touch other
repositories.

## C2 — The Unix-user boundary is the enforcement, not GitHub

GitHub restricts *accounts*; it cannot see which agent or process used a
token. On one box, every process of one Unix user reads the same credential
files (verified on this box: `~/.config/gh/hosts.yml`, mode 600, owner
`nedlern` — every agent, subagent, and shell here is `nedlern` and reads the
same token). Therefore: the main-capable credential is owned by a **dedicated
Unix user** (working name `nedschorus-gatekeeper`), unreadable by agent
sessions; agents invoke the gatekeeper through a **sudoers rule scoped to
exactly that program**. This is what makes "agents never push to main"
mechanical rather than instructed. Harness hooks and CLAUDE.md are context,
never enforcement — the project has already ruled this class
(instruction-file guard: a soft block by design; spec: "a python script does
not read it").

## C3 — Account layout amendment

Amends the boss-ruled 2026-07-21 layout. Branch protection's push restriction
on `main` moves from `NedLern` to the gatekeeper account **alone**. `NedLern`
and `NedLerner` remain the two org owners — owner power stays with the user,
never with anything an agent runs as. Requires an org owner to apply (agents
cannot: verified, `ubuntu-claude` cannot even read protection settings).

## C4 — Agent tokens are scoped, and issues are scoped rather than gated

The agent credential on this box today is a **classic** token with `repo` +
`workflow` scopes: full control of every repository the account reaches, plus
the ability to land GitHub Actions workflow files — the capability-by-landing
class [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31)
singles out. Replace with a **fine-grained token scoped to
`nedschorus/nedschorus`**: contents read/write (branch pushes stay open — the
[nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45)
"push-less" ruling covers main only; verified by dry run that branch pushes
already work), issues write, nothing else; `workflow` dropped (the repository
has no workflows; nothing breaks).

Issue work is **scoped, not gated**: agents legitimately read, create,
comment, and edit as ordinary work; there is no invariant like "one writer to
main" to protect, so a mediating program would re-implement the issues API
and buy nothing. Discipline lives at the skill/hook rung (`ghi-write`,
[nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13), and the
gh-rewrite hook of C6). What would move issues up a rung, recorded: wanting
per-write provenance, or approval-before-close. Neither is true today.

## C5 — Break-glass: an unlockable credential, never a standing ungated agent

The failure the user named: something goes wrong and an agent is needed to
fix it. Split by failure class:

1. **Gate defects** — the gate's own history is the recovery path: any
   historical version of the program is directly runnable
   (`git show <good-sha>:scripts/git-gatekeeper.py > /tmp/gk.py`). Standing
   invariant, adopted: **the gatekeeper stays one standard-library-only
   file** precisely so this always works.
2. **A landing the gate wrongly refuses** — the credential is *unlockable*,
   not held: a sudoers entry that requires the user's password. An agent
   prepares the exact command and asks; the user approves in the moment.
   Ten-second recovery, no standing main access in any agent environment.
3. **Credential expiry or protection misconfiguration** — org-owner
   territory; the user's alone by C3. No agent bypass would help, because no
   agent may hold owner power.

Rejected: a permanently ungated agent — it would be the party running
half-finished gate code against production while holding the credential that
lets mistakes through, and gate *development* needs no access at all
(slices 1–3 were built and 146-case-tested entirely against throwaway bare
repositories, credential-free).

## C6 — The cooperative tier: rewrite hooks, the check-in skill, teaching refusals

Verified: PreToolUse hooks in the current harness can return `updatedInput` —
seamless substitution of a tool call. The tier, and the split:

- **`gh` calls rewrite seamlessly** (the user's gh-ned pattern): semantics
  map one-to-one, agents keep their trained behavior, zero token cost.
- **`git push` toward the nedschorus remote gets deny-with-exact-invocation,
  not a rewrite**: a push carries none of the declaration (`--files`,
  `--base`, `--message` map to nothing in `git push`'s arguments), and
  auto-deriving the whole declaration would gut the intentionality the spec's
  `unchanged-path` refusal exists to force. The one moment of friction lands
  exactly where the design wants a deliberate act.
- **The check-in skill front-loads the declaration** so the first call is
  well-formed: `--files` relayed from the agent's own staging (the `git add`
  of this design), `--base` computed as `git merge-base HEAD origin/main`
  (the branch point GitHub used to compute for free), message passed through
  verbatim (commit message ≈ PR description; the trained act).
- **Refusals teach** as the final tier; every error names the exact fix.

Division of labor, stated once: the agent contributes only what it already
does by training — choose the files, write the what-and-why; the machinery
derives or auto-fills everything else (base, session origin, digest, issue
trailer form). Hooks are convenience and coverage, **never the boundary**
(C2 is the boundary). A `conflict` refusal is deliberately loud: resolving
one takes judgment about intent, the one thing the machinery must never fake.

## C7 — Privileged invocations refuse the test seams

`--repo` and `--remote` exist so the test suite can hand the program
throwaway repositories (B3a) with no test-only code path. The moment the
program runs under the credential-holding user, those same arguments are a
privilege surface: an agent could aim the credentialed program at an
arbitrary remote. Binding: **when running as the gatekeeper user, `--remote`
and `--repo` overrides are refused** (named refusal; the remote is pinned to
the canonical repository). Tests run unprivileged and keep the seams.

## C8 — OPEN: cross-machine callers

The gatekeeper reads declared content from the caller's worktree, which
works only when caller and gatekeeper share a filesystem. Mac-side agents
(CLI, Mac app) cannot be read from the Ubuntu box. Candidate shapes, none
chosen: the caller pushes its branch first and the gatekeeper reads content
from the branch ref (a real contract change — the request names a ref
instead of relying on worktree bytes); or Mac agents do not check in
directly and route work through the Ubuntu side; or a second gatekeeper
installation on the Mac (two credentialed hosts — weakens C2's single-place
property). Decide when a Mac-side agent first needs direct check-in; the
spec's "invocable service" line anticipated the shape but did not design it.
