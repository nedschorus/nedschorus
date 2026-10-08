# main-gatekeeper glossary

Terms that belong to the main-gatekeeper alone, for agents working on the files in this directory. Project-terms, such as main-gatekeeper itself, are in the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`.

- **main-gatekeeper-check-in-request-holder** — the process that does one check-in request's work and holds the request's lock until the work ends: the detached worker of a `check-in --no-wait`, or, for a waiting check-in, the `check-in` process itself.
- **main-gatekeeper-worker-spawner** — the `check-in --no-wait` process that starts the detached worker, which is the main-gatekeeper-check-in-request-holder, and answers `accepted`.
