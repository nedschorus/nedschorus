# handoff-system glossary

Terms that belong to the handoff-system alone, for agents working on its files, which are under `nc-systems/handoff/` and `scripts/`. The parts these entries name, such as the threshold hook, its ceiling and the writer script, are described in `nc-systems/handoff/handoff-design.md` and in the handoff-system's nc-architecture-overview, `docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md`. Project-terms, such as session-handoff and reincarnate-seat, are in the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`.

- **handoff-deferral** — the threshold hook's postponing of a reincarnate-seat while a subagent or a recent background Bash task of the agent-session is still running, up to the ceiling.
- **spawned-subagent-roster** — the `spawned-subagent-N` fields the writer script writes into a session-handoff, one for each subagent still working, and the sentence the handoff-supervisor gives the successor naming them.
