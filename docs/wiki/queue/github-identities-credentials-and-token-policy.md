# GitHub identities, credentials, and this organization's token policy

Reference page for the NedsChorus fleet. It answers three questions an agent or
a human hits repeatedly: **which GitHub account am I acting as, what credential
holds that identity, and why did GitHub just refuse me?**

It is reference material, not rules. The rules about who may review, approve and
merge live in `CLAUDE.md` at the repository root, and in the machine-local
`CLAUDE.local.md` beside it in whichever checkout an agent is working in. This
page exists so those files do not fill up with credential trivia.

Everything below was measured on 2026-08-24 unless stated otherwise.

## The identities

These GitHub accounts touch this project: the human owner, a merge identity, a
review identity, and the machine accounts each host runs as.

| account | what it is | org standing |
|---|---|---|
| `nedlern` | the human owner's own account. Mac seats authenticate as this by default, because it is what `gh` is logged in as on the Mac. | owner |
| `ned-review-merge` | the merge-lane seat's identity: it reviews other seats' pull requests, approves them, and merges. Formerly the org's second owner, renamed and demoted to member on 2026-08-19. | member |
| `mac-claude` | the independent reviewer identity. It reviews and approves work the merge-lane seat itself authored — work `ned-review-merge` may not approve, because GitHub refuses an approving review from a pull request's author. | member since 2026-08-24 |
| `mac-codex` | Mac-side Codex worker. No credential yet. | invited 2026-08-24, pending |
| `ubuntu-claude` | the Ubuntu box's live credential; box seats act as this. | invited 2026-08-24, pending |
| `ubuntu-codex` | Ubuntu-side Codex worker. No credential yet. | invited 2026-08-24, pending |

**Why the identities are separate at all.** GitHub refuses an approving review
from a pull request's author, and `main` has required reviews enabled with no
bypass for anyone. So a single identity that both opens and merges pull requests
can never satisfy the rule on its own work. Each account above exists to be
*somebody else* at the moment an approval is needed.

**A naming trap, recorded because it has caused real confusion.** "nedlern" is
both a GitHub account *and* the Unix user every box agent runs as, while the
box's GitHub account is `ubuntu-claude` and the Mac's Unix user is `el`. A bare
"nedlern" is ambiguous until the namespace is named.

## The credentials

| account | where the credential lives | kind | expires |
|---|---|---|---|
| `nedlern` | this Mac, `gh`'s own store (keychain) | classic | 2027-08-24 |
| `ned-review-merge` | `~/.config/nedschorus/ned-review-merge.token` | fine-grained | 2027-08-20 |
| `mac-claude` | `~/.config/nedschorus/mac-claude.token` | fine-grained | 2027-08-25 |
| `ubuntu-claude` | the Ubuntu box, `gh`'s own store | classic | 2027-08-24 |

Token files are mode 600.

**Git operations borrow `gh`'s credential.** On both machines `git` is
configured with `credential.https://github.com.helper = !gh auth git-credential`,
so a broken or refused `gh` token breaks `git push` as well. The two are not
independent.

## This organization's token policy, and the four ways it bites

**No token may have a lifetime over 366 days.** This applies to classic and
fine-grained tokens alike. The refusal does not happen at creation — GitHub
issues a non-expiring token happily — it happens at *use*, as an HTTP 403 on
every organization-scoped call:

> The 'nedschorus' organization forbids access via a personal access token
> (classic) if the token's lifetime is greater than 366 days.

So **"No expiration" is never a valid choice here**, on any token type. This
took down `nedlern`'s access to the whole organization on 2026-08-24,
immediately after a routine renewal chose it, and it was simultaneously why the
Ubuntu box could not push.

**A fine-grained token can only name an organization the account is a member
of.** An outside collaborator is not offered the organization at all: the
resource-owner field silently defaults to the personal account, and the
resulting token authenticates correctly while reaching no repositories. This is
why the four machine accounts were invited to the organization — membership is
a prerequisite for holding a narrow, repository-scoped token, not a grant of
extra power. Organization base permission is deliberately set to **none** and
member repository creation is **off**, so membership by itself confers nothing;
each account's repository access comes from its explicit collaborator grant.

**A fine-grained token pointed at the organization needs an owner's approval.**
Until it is approved the token authenticates, reads public data normally, and
fails every write with `Resource not accessible by personal access token`. The
approval lives at **Organization → Settings → Personal access tokens → Pending
requests**, as a sidebar sub-item rather than a tab. The requirement can be
switched off in the adjacent **Settings** sub-item.

**A classic token's expiration cannot be edited in place.** The token page
offers only *Update* (name and scopes) and *Regenerate*. The expiration selector
lives inside the Regenerate flow, and regenerating issues a new value that must
then be installed.

## What is deliberately withheld

`ned-review-merge` cannot change branch protection, act on the organization,
touch workflows, or reach any other repository. `mac-claude` holds only pull
requests read-and-write plus contents read-only, on this repository alone.

The `nedlern` classic token is the exception and the standing exposure: it
carries `admin:org`, `admin:enterprise`, `audit_log`, `admin:repo_hook` and
more, and every agent on the Mac reaches all of it by running plain `gh` with no
token to export. Narrowing it is an open question for the owner, not a decision
this page makes.
