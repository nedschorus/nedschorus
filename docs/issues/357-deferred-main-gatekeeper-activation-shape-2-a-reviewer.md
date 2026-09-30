---
issue: "[Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own](https://github.com/nedschorus/nedschorus/issues/357)"
---

# Deferred: main-gatekeeper activation shape 2 — a reviewer attached to the gate and an approving identity of its own

**Deferred component of the main-gatekeeper, deferred by the user's ruling of 2026-09-14 ("shape 1"). This issue is the tracker for that deferral; nothing is being designed or built under it yet.** Filed 2026-09-14 on the user's word at the merge-lane seat, as a new issue rather than an edit to GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3), because GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3)'s body is already over the ghi-write cap (1135 words at filing) and shape 2 has its own lifecycle: its own design, its own next action and its own closure, separate from activation.

## What shape 2 is

Two additions to the gate as shape 1 activates it:

1. **A reviewer the gate invokes itself**, so the review verdict returns in the gate's reply to the caller rather than on the pull request the gate opens.
2. **An approving identity of the gate's own**, so the gate's pull request needs no seat to approve it.

Under shape 2 as presented, the merge lane retires. Under shape 1, which is ruled, it does not.

## The ruling that defers it

On 2026-09-14 the merge-lane seat put the activation question to the user as two shapes. Shape 1: at activation the merge lane keeps reviewing and approving the pull requests the gate opens; the gate is the program that opens them, with attribution computed, checks run and staleness reported. Shape 2: the gate acquires its own reviewer and a second approving identity before activation, and the merge lane retires. The user's whole reply was "shape 1". Review-at-the-gate (ruled 2026-08-17) is therefore met by review at the pull request the gate opens. Shape 2 is deferred, not rejected: the user said he will want it soon. The ruling is recorded in `docs/issues/3-main-gatekeeper-build-slice-plan.md` § Activation shape ruled 2026-09-14, and on GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3)'s body.

## What it attaches to

The path shape 1 activates: slices 7 through 10 of the slice plan (the gate opens a pull request instead of pushing to main; the per-file staleness report; the check battery; the C2 move onto the dedicated Unix user). Nothing in those slices is undone by shape 2; it attaches on top. It builds on slice 7 at the earliest, because until the gate opens pull requests there is nothing for the gate's own identity to approve. Whether it waits for slices 8 to 10 is for its design.

## Where the existing thinking lives, so it is not redone

All paths are on main as of filing.

- `docs/issues/3-main-gatekeeper-build-slice-plan.md` § Shape 2 — the deferral record and the source of this list.
- `docs/issues/3-slice-6-review-evidence-not-built.md` § What replaces it — the review-at-the-gate paragraph, including the user's 2026-08-17 sketch: a script invoking a heavy Claude and Codex review.
- `docs/issues/3-credential-work-measured-state-and-rulings.md` § The guardian direction — structure over instructions, author ≠ approver by account, interactive not headless, the error standard.
- The slice plan § Open item 3, the tier split: mechanically decidable checks are code and belong to the gate; correctness review belongs to the judgment layer.
- `nc-systems/main-gatekeeper/main-gatekeeper-design.md` § Constructive guarantees, the advisory, and the growth point — the gate as the place where checks attach as they come to exist.
- `docs/design-to-main/design-to-main-state-machine-design.md` § 3.4 and the gate-rejection entry of `docs/design-to-main/design-to-main-glossary.md` — what a review finding returned through the gate looks like to a caller. That design assumes the gate returns a verdict; under shape 1 that verdict is the merge lane's review of the gate's pull request, and shape 2 is what makes the assumption literally true.
- GHI [Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience](https://github.com/nedschorus/nedschorus/issues/105) — the deferred machine merge-decision review, which names the gate as its eventual consumer, "the gate that can review, or refuse, what passes through it". A candidate for shape 2's reviewer.
- GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31) — the three mechanical checks a review gate owes (signer ≠ author, the exact version named, statements not quotations) and the author/checker structural lever; its Part 1 attaches at the gate "when a class is gated".

## Design questions shape 2 must answer, not answered here

- **Which identity approves.** An account of the gate's own, and how GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31) Part 1's first check (signer ≠ author) holds when the same program opens the pull request and approves it. The user ruled 2026-08-17 that main's push allow-list keeps his own account beside any pusher; that constraint carries.
- **What the reviewer is.** GHI [Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience](https://github.com/nedschorus/nedschorus/issues/105)'s component, the merge lane's reviewer brief as composed today by `scripts/compose-pull-request-reviewer-brief.py`, the 2026-08-17 sketch, or something else.
- **Where the verdict lives.** In the gate's reply, on the pull request, or both; and what the design-to-main state machine's § 3.4 needs from it.
- **What remains of the merge lane.** Shape 2 as presented retires it; whether a human-facing reviewer of last resort stays is a ruling, not a default.

**Ruled 2026-09-15 (reboot-test seat, walk `ghi-md-pair-updates-reach-every-agent`, minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-md-pair-updates-reach-every-agent-minutes.md`), for shape 2 to carry:** the GHI write tool (GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)) opens pull requests touching only `docs/issues/`, and the gate's approving identity merges them without a person; a pull request from anyone but that tool which touches `docs/issues/` is refused at the gate. The user's original ruling, "the GHI subsystem pushes to main directly", is refused by branch protection and became this.

**Widened 2026-09-19/20 (reboot-test seat, walk `ghi-info-design-write-path-becomes-link-only`, minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-info-design-write-path-becomes-link-only-minutes.md`; design revision merged as PR [ghi-info design: the write path becomes link-only](https://github.com/nedschorus/nedschorus/pull/554)):** the rule above names `docs/issues/` as a fixed directory, and that cannot hold. The user ruled on 2026-09-18 that a design and its design-contract move into the component's directory when code starts, and on 2026-09-20 that a test-design joins them. Confined to `docs/issues/`, the write tool could neither perform that move nor edit a design afterwards.

**So the gate's rule follows the pairing, not a directory:** the write tool opens pull requests touching only files paired with a GitHub issue — under `docs/issues/` before that issue's code starts, and under the component's own directory after — and the gate's approving identity merges them without a person. A pull request from anyone but that tool which touches a paired file is refused at the gate. The user approved the tool's side of this as item 3 of that walk; this is the gate's matching half.

**Reversed 2026-09-20, and this issue is off the write tool's critical path.** The rule above said the gate's approving identity merges the write tool's pull requests without a person. That identity is this issue's deferred work, so it made the unbuilt gate a prerequisite of the GHI write tool. Put to the user 2026-09-20 as the one thing blocking that build; his answer was "like every other change seems fine. why is that even a question". **Ruled: the write tool's pull requests are merged by merge-lane exactly as every other pull request is, and this issue's approving identity is not among its prerequisites.** Measured the same day: merge-lane merged 49 pull requests in the preceding 24 hours against about 2.3 issues created per day, and a GHI-MD is prose under `docs/`, which the review-scope rule makes silent, so the lane reads nothing and merges. What survives here for whenever shape 2 is taken up: the gate still refuses a pull request from anyone but the write tool that touches a paired file.

One consequence for whoever builds the gate check: "is this path paired with an issue" is no longer answerable by prefix match alone, because a paired file can sit anywhere its component does. The write tool records the pairing, so the check reads that record rather than the path.

## Revisit trigger

After slice 7 lands and the merge lane has reviewed enough gate-opened pull requests to show what a gate-attached reviewer would do differently, or when the user says he wants it. Whoever reopens this writes the design first, in the designs queue the ghi-write skill names (`docs/designs/queue/`; no file in it on main at filing), and lands it as this issue's pair document before any build.

## Search receipt for filing new rather than amending

`gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "<terms>"` on 2026-09-14 for "shape 2", "reviewer attached to the gate", "review at the gate" and "gatekeeper reviewer" returned no issue covering a gate-attached reviewer; GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3), GHI [Deferred: pr-merge-decision-codex — machine merge-decision review; revisit after code-review-codex-cell accrues lane experience](https://github.com/nedschorus/nedschorus/issues/105) and GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31) are the nearest, and each names the gate as a consumer or attachment point rather than owning this. ghi-info was asked first and answered a sync notice instead of the question, so the `gh` ladder rung was used.

Closes when shape 2 is designed and built, or when the user rules the gate will not carry a reviewer of its own. Parent: GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3).
