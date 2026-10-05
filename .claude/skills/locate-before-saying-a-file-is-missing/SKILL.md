---
name: locate-before-saying-a-file-is-missing
description: Use before telling anyone that a file, record, transcript, approval or other stored artifact does not exist, is gone, or cannot be found. Runs the locator that searches both machines, the log-store, and backups, including transcripts in backups.
---

# Locate before saying a file is missing

Files agents call missing are usually somewhere they did not look: another checkout, the other machine, the log-store, a transcript, git history or a backup.

1. Run `python3 scripts/locate-file-copies-across-machines.py <name>`, with the file's name or a distinctive part of it, from a checkout of this repository.
2. Read all of its output. Copies of the file are listed under a "Same name" heading, newest first, each with its machine and path; files whose names only contain yours are listed as candidates, "not counted as found". When it finds no copy, it searches the backups and prints one line per place: FOUND, NOT FOUND or UNAVAILABLE. NOT FOUND covers only that place; UNAVAILABLE and "Could NOT search" mean the place was not searched.
3. Check that a hit holds the file's content, not just its name: a transcript matches whenever the name was only typed in it.
4. If a hit holds the file, say where it is.
5. If no hit holds the file, say where you looked, naming each place searched and each place not searched, and any hit you ruled out and why, not that the file does not exist.
6. If the locator itself fails, say so and quote what it printed; a failed search is not a search that found nothing.
