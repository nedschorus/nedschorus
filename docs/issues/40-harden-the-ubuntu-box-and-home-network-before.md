---
issue: "[Harden the Ubuntu box and home network before any server role (not hardened today)](https://github.com/nedschorus/nedschorus/issues/40)"
---

# Harden the Ubuntu box and home network before any server role (not hardened today)

The Ubuntu box is well set up as a development machine, but neither it nor the home network is hardened for server use (boss, 2026-07-31). Before the box takes any server role — a CI runner, the gatekeeper's dedicated-identity service, anything externally reachable — run the hardening pass over both the box and the network. Procedures get designed when that trigger nears, not now. Until then ned-box stays a development machine, except for the two services the user has since approved to listen on ned-box for the home network only; the section below headed "Services the user approved for the home network only (2026-10-14 to 2026-10-31)" names them.

Trigger: the first planned server role for the box. The user approved those two services without the hardening pass being run first; the same section below says how.

Session provenance: new-vp session b7c09142 (replaces the overtaken legacy audit nedlern#628).

## Services the user approved for the home network only (2026-10-14 to 2026-10-31)

When this GHI was written on 2026-07-31, its first paragraph ended "Until then: development machine only, nothing listens." Three later decisions of the user made that sentence untrue. None of the three names this GHI, and each is given here as what the user approved, in the words of its walk-minutes or walk-document.

- 2026-10-14, item 2 of 22 of the approval-walk on the open defects of GHI [A small HTTP service with SQLite on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972): the user answered "y" to this sentence of that design: "The service listens on port 8765 on every address; ned-box's `ufw` firewall admits the port from the LAN only, which is what keeps access on the LAN." The walk-minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-seat-service-design-open-defects-2026-10-14-minutes.md`; they give the date and no time.
- 2026-10-15, item 17 of the approval-walk whose walk-minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/open-decisions-unpushed-branches-memory-claude-md-root-cause-and-cold-read-2026-10-14-minutes.md`: the user answered "y" to a new `CLAUDE.md` bullet on when an agent may propose a guard, which holds the sentence "Hardening against deliberate attackers is not needed". The bullet is about the guards agents propose; it does not mention this GHI's hardening pass.
- 2026-10-31 07:39, item 16.3 of 25, "no password on the walk-page server", of the approval-walk whose walk-minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`: the user approved the recommendation "keep the design: no password, home network only" for the server of GHI [A read-only web server on ned-box renders Markdown files as web pages on the LAN, for approval-walk item pages and other pages agents publish to claude.ai that only show text](https://github.com/nedschorus/nedschorus/issues/2175), which ned-box's firewall lets only devices on the home network, `10.0.1.0/24`, reach. The item cited the two decisions above as "Earlier user-rulings".

These decisions approve the two designs. This GHI-MD does not record whether either service is installed or running.

Why the build of the first service was not stopped for the hardening pass: on 2026-11-05 ghi-guide-agent asked whether this GHI's rule stops the build of the service of GHI [A small HTTP service with SQLite on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972), and two agents of the agent-seat fleet-restart-at-login answered no, from the three decisions above: the second agent wrote that "GHI 40's 2026-07-31 rule no longer binds a LAN-only service." Their record is `nedlern@ned-box:/home/nedlern/nedschorus-logs/ghi-guide-agent-proposed-improvements-or-changes/972-a-small-service-on-ned-box-keeps-one-proposed-improvements-or-changes-ghi-guide-agent-2026-11-05.md`. That sentence is the agents' reading of the three decisions, not a user-ruling: the user approved these two services, and none of the three decisions says that every later service reachable only from the home network may skip the hardening pass.

The hardening pass is not cancelled: none of the three decisions mentions the hardening pass. It is still due before ned-box takes any server role other than these two services.

## Network reliability record (2026-08-17)

SSH to the box dropped repeatedly before any hardening: three ~1-minute drops on 2026-08-15 and a connect timeout on 2026-08-16. Diagnosis (2026-08-17): the ethernet port was installer-configured `ipv4.method=link-local` — no DHCP — so all traffic rode the wifi mesh. Fix applied the same day: method set to auto; the box is wired at 10.0.1.106 with the wired route outranking wifi; the Mac's shared `~/.ssh/config` resolves `ned`/`ned-box` there, with `ned-wifi` keeping 10.0.1.39 as a named fallback; the eero DHCP reservation for 10.0.1.106 is in place. Distinct failure class, recorded separately: the 2026-08-14/17 session deaths were login-scope and service teardown, not network — see GHI [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62).
