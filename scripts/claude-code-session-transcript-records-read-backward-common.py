#!/usr/bin/env python3
"""Read a Claude Code session transcript from its end, so a hook that needs only the last turn
reads only the last turn, not the whole file, which grows to tens of megabytes.

records_newest_first(path) yields each line's JSON object, last line first. A line that is not
JSON, such as the partial line Claude Code is still writing, or JSON that is not an object, is
skipped. The text after the file's last newline is decoded with undecodable bytes replaced,
because a partial line can end partway through a multi-byte character. Any other line holding
bytes that are not UTF-8 raises UnicodeDecodeError when it is reached, and an unreadable file
raises OSError; lines before the stopping point are never read, so a bad byte there raises
nothing.

records_from_newest_boundary_to_end(path, *is_boundary) returns, oldest first, the records from the newest one each
predicate matches to the end of the file, so the newest record every predicate matches is in
the list. When some predicate matches no record, it returns every record. A caller that scans
the returned list for the newest record a predicate matches therefore finds the record it
would find in the whole file.
"""

import json

BLOCK_SIZE = 1 << 16


def _lines_newest_first(path):
    with open(path, "rb") as transcript:
        transcript.seek(0, 2)
        position = transcript.tell()
        rest = b""
        while position > 0:
            size = min(BLOCK_SIZE, position)
            position -= size
            transcript.seek(position)
            pieces = (transcript.read(size) + rest).split(b"\n")
            # The first piece may be the end of a line that starts in an earlier block.
            rest = pieces[0]
            for piece in reversed(pieces[1:]):
                yield piece
        yield rest


def records_newest_first(path):
    # _lines_newest_first yields the text after the last newline first.
    errors = "replace"
    for line in _lines_newest_first(path):
        text = line.decode("utf-8", errors)
        errors = "strict"
        try:
            record = json.loads(text)
        except ValueError:
            continue
        if isinstance(record, dict):
            yield record


def records_from_newest_boundary_to_end(path, *is_boundary):
    records = []
    unmatched = list(is_boundary)
    for record in records_newest_first(path):
        records.append(record)
        unmatched = [predicate for predicate in unmatched if not predicate(record)]
        if not unmatched:
            break
    records.reverse()
    return records
