<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/sidebar-instructions.md -->

## Findings

**1. Line 3** — "This seat is the deliberate exception to it: it owns no pile."

The pronoun "it" in "exception to it" most naturally refers back to "[the seat model]" cited earlier in the same sentence, i.e. the whole framework agent-seat-model.md defines. But that document's own wording is narrower: "`sidebar` is the deliberate exception to the grouping rule: it holds no pile at all" — the exception is to the *grouping rule*, not to the seat model as a whole. Read literally here, the sentence claims sidebar is exempt from the seat model in general, yet the rest of this same brief holds sidebar to other parts of that model — it must still commit/push "like any other seat's work" (line 26), it may still be asked to hand off (line 17), and it inherits the model's shared vocabulary (per line 3's own directive to read it). "Exception to it" overstates the actual, narrower exemption.
Confidence: sure the pronoun's natural antecedent is broader than the exemption actually described elsewhere.

**2. Line 9** — "Small errands with no home: checking a status, reading a file, running a one-off script." — versus **Line 36** — "No status report, no inventory, no plan — those belong to the topic seats, and producing one here is the most likely way to get this seat wrong."

These support incompatible readings: line 9 names "checking a status" as ordinary, sanctioned sidebar business, while line 36 forbids "a status report" as the thing most likely to get this seat wrong. The file never states the distinction that would reconcile them (e.g., a single asked-for status check versus an unprompted broad report volunteered as an opening move) — a reader could take line 9's permission at face value and produce exactly the report line 36 forbids.
Confidence: unsure — the "First action"/unprompted-vs-asked framing is a plausible reconciliation, but it is nowhere stated, so I can't be sure it's the intended resolution rather than an actual conflict.

**3. Line 13** — "The user exits and restarts you freely, and that costs nothing precisely because you were never holding anything."

This contradicts the explicitly-linked agent-seat-model.md, which states of idle seats: "An idle seat costs almost nothing... It is not literally free: an unretired seat holds a directory and a branch." Sidebar is listed as one of the seven seats in that same model's table and inherits its definition of "Seat" (name, home directory, branch, brief) — so sidebar does hold a directory and a branch even though it holds no *pile*. The claim that restarting "costs nothing precisely because you were never holding anything" conflates "holds no pile" with "holds nothing," which the model text explicitly distinguishes.
Confidence: sure, checked directly against agent-seat-model.md's qualifying sentence.

**4. Line 26** — "Anything you change on disk is committed and pushed like any other seat's work."

Absolute claim ("anything") broader than can hold. The same file sanctions "running a one-off script" (line 9) as ordinary sidebar business; such a script will often produce scratch output outside the git worktree (e.g. to `/tmp`, or a log file never meant for the repository), which cannot be committed and pushed. The sentence gives "anything" no scope (e.g. "anything you change in the repository"), so taken literally it also claims incidental, non-repo disk changes must be committed.
Confidence: sure the sentence is unscoped as written.

**5. Line 26** — "which is the one way this seat can do harm."

Absolute claim narrower than reality. The same paragraph's job description sanctions "running a one-off script" (line 9), and a script can itself be destructive (e.g. one that deletes or overwrites files) — a harm unrelated to an unrecorded answer. The "own nothing" guidance elsewhere in this file also implies a distinct harm (misrouting or losing real project work by not naming its seat), which "the one way" excludes.
Confidence: sure that at least the destructive-script case is reachable under this brief's own sanctioned activities, making "the one way" false as stated.

**6. Line 28** — "commits carry the session id"

Unexplained term / un-executable instruction. Neither this file, the checkout's CLAUDE.md, nor the explicitly-linked agent-seat-model.md defines what "the session id" is, where it comes from, or how it is meant to appear in a commit (trailer, message prefix, branch convention, etc.). agent-seat-model.md defines "Session" only as "one running conversation," giving no identifier format. An agent following this instruction literally has no procedure to execute it by.
Confidence: sure — checked all three permitted sources and found no definition.

**7. Line 28** — "nothing is pushed to main, since his Mac-side agent reviews and merges."

Self-undermining as written: the "since" clause offers, as the reason nothing is pushed to main, an action (the Mac-side agent reviewing and merging) that itself lands commits on main — ordinarily what "pushed to main" means. The checkout's CLAUDE.md avoids this by scoping the rule to "agents": "agents never push to main. Until its credential work lands..., commit to the working branch, push it, and the user's Mac-side agent reviews and merges." This sentence drops that scoping, collapsing "no [box] agent pushes to main" into an unscoped "nothing is pushed to main," which its own justifying clause then contradicts.
Confidence: sure the sentence as written is internally inconsistent.

clean sections: ## Machine facts worth having on hand

