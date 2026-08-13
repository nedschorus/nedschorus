<!-- provenance: judgment of the calibration protocol's second-document run — the settled sanity-checker prompt (post-calibration acceptance) reviewing docs/cross-project/fast-handoff-design.md, a live document with no pre-existing ground truth; the ground truth IS the user's rulings, made 2026-08-12 in the findings walk recorded at md-review-records/2026-08-12-fast-handoff-sanity-check/dispositions.md -->

# Second-document judgment: the sanity-checker on fast-handoff-design.md

The first calibration document (git-gatekeeper spec at 0890848) scored the prompt against rulings that already existed. This second document ran the other direction: the settled prompt reviewed a live design first, and the user then ruled on its seven findings with no prior positions. His rulings are the judgment.

## Outcome per finding

| Finding | User ruling | Match |
|---|---|---|
| F1 — two auto-trigger mechanisms, delete the relay | Accepted in full: relay deleted, hook is transcript-only. The walk verified what the reviewer could not read (the hook): the fallback's only trigger was a pre-first-turn session, below any threshold — the finding's cut was *more* right than its own argument knew. The reviewer's honest "I could not read the hook script" was exactly the right epistemic line. | Accepted |
| F2 — the liveness gate suppresses self-healing, delete it | Accepted: gate deleted. The flagged ruling collision resolved the way the reviewer suspected — hook-silence was an implementation choice riding the 2026-08-06 detectability ruling, not the ruling itself. The gate was also dormant (settings never passed `--agent`), which the reviewer could not see. | Accepted |
| F3 — queue-status line has no reader when detached | Accepted as the reviewer's preferred option: routed into the ignition prompt; console print kept. The #32 collision resolved by reading the ruling: the boss is the ruled reader, the successor's reporting is the surviving channel. | Accepted |
| F4 — per-upgrade canary duty: mechanize or delete | Accepted in the finding's stated alternative: the duty deleted, not mechanized. User rationale: upgrade breakage is a risk he does not care about; containment exists regardless. | Accepted (alternative) |
| F5 — Tests/Components predate the word-floor ruling | Accepted as a class (see below). | Accepted (subsumed) |
| F6 — three disagreeing status homes | Accepted as a class (see below). | Accepted (subsumed) |
| F7 — Known holes holds closed holes | Accepted as a class (see below). | Accepted (subsumed) |

**The class ruling (F1-document-half, F5, F6, F7):** while weighing F1 the user ruled on the document's purpose itself — no utility in prose documenting what is better understood by reading the code. The four documentation findings were resolved wholesale by gutting the design document to what code cannot carry (rulings, verified facts, live holes, a component pointer). This is a stronger action than any single finding proposed, in the direction all four pointed: the reviewer diagnosed drift instance by instance; the user cut the drift-generating tissue.

## Aggregate

Seven findings presented, seven led to accepted change, zero rejected — against a document that had already passed its build walk and a live trial. No finding was judged wrong or wasteful; the two flagged ruling collisions were both real and both resolved without re-litigating a ruling. The review also provoked a ruling larger than its findings (the document-gutting charter), which is the reviewer's "hunt: a better way" duty landing one level above where the prompt aimed it.

## What this unblocks

The calibration protocol's condition is met: the settled prompt has now been judged against ground truth on two documents (S1–S9 scorecards, and this walk's rulings). The grid-seat proposal — whether the sanity-checker cell joins the md-review grid — is a user-walked decision, now ready to be walked.
