# Walk: what a nit is, and where nits go under the review stopping rule

Subject: the word "nit" in code review — what it means, what it is not, and where a nit goes under the rule that a review round ends when it changes no code and no test.

4 items.

---

## Item 1 of 4: What a nit is

A nit is a review finding that is real, correct, and does not matter to whether the change works.

The word is short for nitpick. It names the smallest class on a reviewer's severity scale. This project already has that scale, written down in [the adversarial package review brief](file:///Users/el/agents/reboot-test/docs/issues/8-adversarial-package-review.md): BLOCKER (the design fails its purpose), MAJOR (a real failure mode ships), MINOR (friction or drift risk), and NIT. The first three each say what goes wrong. NIT is the class where nothing goes wrong.

Concrete examples of a nit, in code: a variable named `tmp` where `candidate_path` would read better; a comment that says "fetch the remote" above a line that plainly fetches the remote; two blank lines where the file elsewhere uses one; a function that could be two lines shorter. Each is a true observation. Fixing any of them changes what a reader sees. Fixing none of them changes what the program does.

The test: if the nit were left exactly as it is forever, would any caller, any test, or any user ever observe a difference? If no, it is a nit. If yes, it is not a nit — it is a MINOR or worse, and it has been mislabelled.

No decision here. This item exists so the rest of the walk has one definition to refer to.

---

## Item 2 of 4: What a nit is not — the two things it gets confused with

Two other kinds of finding get called nits and are not. They matter because under the stopping rule they go to different places.

The first is a **small defect**. A one-character typo in a git ref name, an off-by-one in an exit code, a message that names the wrong file. These are tiny to fix and easy to call nits because of their size. They are not nits, because a caller would observe the difference. Size is not the test; observability is. A one-character bug is a bug.

The second is a **prose finding on a design document** — a claim stated too strongly, a term used before it is defined, a sentence that supports two readings. These are also called nits, and they are also not, for the opposite reason: they can be large, and fixing them produces new text with defects of its own. This is the class behind the four-round, five-hour review of a one-file deletion recorded in `CLAUDE.md`, where two of the three blocking findings were errors the previous round's own fix had introduced.

So three things, three names: a **nit** changes nothing observable; a **small defect** changes something observable and is small; a **prose finding** changes wording in a document. The stopping rule treats each differently, which is the next item.

No decision here either.

---

## Item 3 of 4: Where each one goes under the stopping rule

The stopping rule, approved today: a review round ends the loop when it produces no finding that changes a line of code or a line of test.

**A small defect changes a line of code or a line of test.** It is fixed in the round it is found, whatever its size. The rule counts lines changed, not effort, so a one-character bug is a real finding and keeps the loop open exactly as a large one would. A defect whose fix is only a test change — a wrong fixture, a missing case — counts the same way. This is deliberate: the alternative is a reviewer deciding a bug is too small to report.

**A prose finding on a design document changes no code and no test.** `CLAUDE.md` already rules on it: a reviewer of a pull request reports nothing about `docs/` prose — silent, not merely non-blocking, because everything a reviewer writes gets read and "fixed" by another agent, and those fixes introduce defects of their own. The design catches up with the code in maintenance after the change lands, which is the shape the user ruled with the merge-lane seat today. So a prose finding does not enter the loop at all.

**A nit changes a line of code but nothing observable.** Here is the choice, and the recommendation:

A nit is fixed in the round it is found **only when that round has other, real findings being fixed anyway**. When a round would otherwise be clean — no defect, no test change — a nit does not by itself keep the loop open. The author fixes it or leaves it; either way the round is clean.

Why: a nit is by definition a change with no observable effect, so a round that produces only nits has produced nothing a test can distinguish from the round before. Counting nits as findings would mean the loop can never close, because there is always one more variable that could be better named.

Recommendation: adopt that. A nit never keeps a review loop open on its own.

Y to adopt, N to keep nits as loop-holding findings, or say what you would change.

---

## Item 4 of 4: The labelling rule that makes item 3 safe

Item 3 depends on reviewers labelling honestly, and there is one failure mode to name.

The failure: a reviewer who has a finding they are not sure about downgrades it to a nit, because a nit is cheap to file and nobody argues with it. Now a possible defect sits in the class that does not hold the loop open, and it slides through. This is the mislabelling item 1 warned about, done in the direction that hides risk.

The fix is a labelling rule: **a nit carries no failure scenario, by definition. A finding that has a failure scenario — any way a caller, test, or user could observe the difference — cannot be labelled a nit, however small the fix.** A reviewer who writes "nit:" and then describes something breaking has contradicted themselves, and the finding is re-labelled up, not down.

The other direction is harmless. A reviewer who labels a nit as MINOR has cost the author one sentence of disagreement and nothing else. So when in doubt, label up. The cost of an over-labelled nit is a sentence. The cost of an under-labelled defect is a green test suite and a wrong result — which is what pull request 223 shipped, 143 passing tests and a wrong answer.

Recommendation: add that sentence to the reviewer instructions. Their home is `pr-reviewer-instructions.md`, which [issue 210, the review-scope rule](https://github.com/nedschorus/nedschorus/issues/210) is building; the line goes in when that file is written. It is one sentence and it makes item 3's rule safe to apply.

Y to adopt, N, or say what you would change.
