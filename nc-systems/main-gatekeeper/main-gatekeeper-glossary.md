# main-gatekeeper glossary

Terms that belong to the main-gatekeeper alone, for agents working on the files in this directory. Project-terms, such as main-gatekeeper itself, are in the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`.

- **check-in** — one request to the main-gatekeeper to put a change on main, made with `nc-systems/main-gatekeeper/main-gatekeeper.py check-in`; the main-gatekeeper either checks the work in or refuses it and says how to fix it. Until the main-gatekeeper is live, changes reach main by pull request instead.
- **main-gatekeeper-check-in-request-holder** — the process that does one check-in request's work and holds the request's lock until the work ends: the detached worker of a `check-in --no-wait`, or, for a waiting check-in, the `check-in` process itself.
- **main-gatekeeper-worker-spawner** — the `check-in --no-wait` process that starts the detached worker, which is the main-gatekeeper-check-in-request-holder, and answers `accepted`.
- **review-at-the-gate** — the review a change must have before the main-gatekeeper lets it reach main; at activation it is merge-lane-2's review of the pull request the main-gatekeeper opens, and a reviewer attached to the main-gatekeeper itself comes later.
