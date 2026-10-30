---
name: emergency-stop
description: 'Use when the user types /emergency-stop, or tells an agent-seat in any words to stop every agent-seat''s work, as in "everyone stop" or "stop the fleet"; when he tells you to lift the emergency stop, or names an agent-seat to coordinate the repair or to lift it; and when you see an emergency, as this skill defines one, that you cannot stop by stopping your own work. Writes the emergency-stop file, which every agent-session is shown until the user lifts the stop.'
---

# Emergency stop

An emergency stop is one file in the log-store, the emergency-stop file, which a hook shows to every agent-session at each turn and each tool call until the user lifts the stop, together with the rules every agent-seat follows meanwhile. While it is in force, only the agent-seat coordinating the repair pushes or merges. The program `nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py` writes every line of the file, so never write it by hand; run each command below from the root of a checkout of this repository.

## Starting a stop

An emergency is work being lost or damaged, or about to be, in more than one agent-seat at once, or in one thing several agent-seats depend on, such as main, the log-store, GitHub access or a machine, which you cannot stop by stopping your own work. CPU load that stalls every agent-seat on ned-box is one; one agent-seat's failing test is not.

1. Decide whether a stop is wanted. When the user types /emergency-stop, or his words name more than the agent-seat he is talking to, such as "everyone", "all agents" or "the fleet", it is. When his words could mean only your own work, stop your own work and ask him one yes-or-no question, "Stop every agent-seat's work?"; on no, do what he says about your own work. When you start one on your own, the emergency must meet the definition above.
2. Run `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py start --words '<his words>'`, or, when you start it on your own, `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py start --evidence '<what you saw, with the time>'`.
3. If it printed a line opening FAILED, the stop is not recorded: send the user a push notification with the PushNotification tool saying the emergency stop could not be recorded and what the line said, stop your own work, and do not try another way to write the file. Do not go on to step 4.
4. If it printed "started", you are the coordinating agent-seat. If it printed "added to the emergency stop in force", another agent-seat already coordinates; your words or evidence are now in its file, and you follow the rules the hook shows you.
5. When you started the stop, send the user a push notification with the PushNotification tool, saying the emergency stop started, why, and that you coordinate the repair. Then run `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py push-notification sent`, or, when it could not be sent, `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py push-notification failed --error '<why>'` and tell the user in your reply.

## Coordinating the repair

1. Write the repair brief at the path the stop file names on its `repair brief:` line: what is being lost or damaged, what you will do to end it, and which agent-seats you need.
2. The stop file lists the scheduled jobs, which keep running, pushes included. Pause any whose run would harm the repair by commenting out its line in that machine's crontab, or with `launchctl unload` on the Mac, and list in the brief each one you paused.
3. Give other agent-seats work for the repair only, by SendMessage.
4. When the user names another agent-seat to coordinate, run `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py coordinate --agent-seat <name> --words '<his words>'`, send that agent-seat the repair brief's path by SendMessage, and from then on take work only from it or the user.

## Lifting a stop

Only the user lifts a stop, in any words, to any agent-seat.

- When he tells you to lift it, run `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py lift --words '<his words>'`. Then restart every scheduled job the repair brief lists as paused.
- When he hands the lift to a named agent-seat, run `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py hand-lift --agent-seat <name> --words '<his words>'`; this does not lift the stop. That agent-seat later runs `lift`, quoting his words that handed it over.
- If any of these commands prints a line opening FAILED, tell the user what it said; the stop is unchanged.
- `python3 nc-systems/skills/emergency-stop/emergency-stop-file-start-append-and-lift.py status` prints what the hooks see: NoStop, InForce, Lifted, Unreadable or FolderUnreachable.
