---
issue: "[Harden the Ubuntu box and home network before any server role (not hardened today)](https://github.com/nedschorus/nedschorus/issues/40)"
---

# Harden the Ubuntu box and home network before any server role (not hardened today)

The Ubuntu box is well set up as a development machine, but neither it nor the home network is hardened for server use (boss, 2026-07-31). Before the box takes any server role — a CI runner, the gatekeeper's dedicated-identity service, anything externally reachable — run the hardening pass over both the box and the network. Procedures get designed when that trigger nears, not now. Until then: development machine only, nothing listens.

Trigger: the first planned server role for the box.

Session provenance: new-vp session b7c09142 (replaces the overtaken legacy audit nedlern#628).


## Network reliability record (2026-08-17)

SSH to the box dropped repeatedly before any hardening: three ~1-minute drops on 2026-08-15 and a connect timeout on 2026-08-16. Diagnosis (2026-08-17): the ethernet port was installer-configured `ipv4.method=link-local` — no DHCP — so all traffic rode the wifi mesh. Fix applied the same day: method set to auto; the box is wired at 10.0.1.106 with the wired route outranking wifi; the Mac's shared `~/.ssh/config` resolves `ned`/`ned-box` there, with `ned-wifi` keeping 10.0.1.39 as a named fallback; the eero DHCP reservation for 10.0.1.106 is in place. Distinct failure class, recorded separately: the 2026-08-14/17 session deaths were login-scope and service teardown, not network — see GHI [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62).
