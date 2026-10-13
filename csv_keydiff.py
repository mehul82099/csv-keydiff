#!/usr/bin/env python3
"""Compare CSV snapshots by explicit keys. Python 3.10+, standard library only."""
import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

__version__ = "0.1.0"


class InputError(ValueError):
    """An input is invalid or cannot be compared without guessing."""


@dataclass
class Table:
    headers: list[str]
    rows: dict[tuple[str, ...], dict[str, str]]


def validate_columns(columns: list[str], label: str) -> None:
    if not columns or any(not c.strip() for c in columns):
        raise InputError(f"{label}: columns must have nonblank names")
    if len(set(columns)) != len(columns):
        raise InputError(f"{label}: duplicate column names")


def load_table(stream: TextIO, keys: list[str], *, label: str = "input",
               delimiter: str = ",", max_rows: int = 100000) -> Table:
    """Read exact text values; reject blank/duplicate keys and ragged records."""
    validate_columns(keys, "key")
    if max_rows < 1:
        raise InputError("max_rows must be positive")
    if len(delimiter) != 1 or delimiter in '\r\n"':
        raise InputError("delimiter must be one character other than a newline or quote")
    reader = csv.reader(stream, delimiter=delimiter, strict=True)
    rows = {}
    seen_at = {}
    try:
        headers = next(reader, None)
        if headers is None:
            raise InputError(f"{label}: missing header row")
        validate_columns(headers, label)
        missing = [k for k in keys if k not in headers]
        if missing:
            raise InputError(f"{label}: missing key columns {missing!r}")
        for record, values in enumerate(reader, 2):
            if record - 1 > max_rows:
                raise InputError(f"{label}: exceeds {max_rows} data records")
            if len(values) != len(headers):
                raise InputError(f"{label}: record {record} has {len(values)} cells; "
                                 f"expected {len(headers)}")
            row = dict(zip(headers, values))
            key = tuple(row[k] for k in keys)
            if any(not value.strip() for value in key):
                raise InputError(f"{label}: blank key at record {record}")
            if key in rows:
                # Do not echo possibly sensitive key values into stderr.
                raise InputError(f"{label}: duplicate key at records "
                                 f"{seen_at[key]} and {record}; choose a more specific key")
            rows[key] = row
            seen_at[key] = record
    except csv.Error as exc:
        raise InputError(f"{label}: CSV parse error near physical line "
                         f"{reader.line_num}: {exc}") from exc
    return Table(headers, rows)


def compare(before: Table, after: Table, keys: list[str],
            ignore: list[str] | None = None) -> dict:
    """Return deterministic JSON-ready differences; input tables are not modified."""
    validate_columns(keys, "key")
    ignored = ignore or []
    for column in ignored:
        if column in keys:
            raise InputError(f"cannot ignore key column {column!r}")
        if column not in before.headers or column not in after.headers:
            raise InputError(f"ignored column {column!r} must exist in both files")
    for key in keys:
        if key not in before.headers or key not in after.headers:
            raise InputError(f"key column {key!r} must exist in both files")
    common = sorted((set(before.headers) & set(after.headers)) - set(ignored))
    added_columns = sorted(set(after.headers) - set(before.headers))
    removed_columns = sorted(set(before.headers) - set(after.headers))
    added, removed, changed = [], [], []
    unchanged = 0
    for key in sorted(set(before.rows) | set(after.rows)):
        identity = dict(zip(keys, key))
        if key not in before.rows:
            added.append({"key": identity, "row": after.rows[key]})
        elif key not in after.rows:
            removed.append({"key": identity, "row": before.rows[key]})
        else:
            old, new = before.rows[key], after.rows[key]
            cells = {c: {"before": old[c], "after": new[c]}
                     for c in common if old[c] != new[c]}
            if cells:
                changed.append({"key": identity, "cells": cells})
            else:
                unchanged += 1
    differs = bool(added or removed or changed or added_columns or removed_columns)
    return {
        "format_version": 1, "keys": keys, "ignored_columns": sorted(set(ignored)),
        "summary": {"before_rows": len(before.rows), "after_rows": len(after.rows),
                    "added": len(added), "removed": len(removed),
                    "changed": len(changed), "unchanged": unchanged,
                    "has_differences": differs},
        "columns": {"added": added_columns, "removed": removed_columns},
        "added": added, "removed": removed, "changed": changed,
    }


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--key", action="append", required=True,
                        help="exact header name; repeat for a composite key")
    parser.add_argument("--ignore", action="append", default=[],
                        help="shared non-key column to ignore; repeat as needed")
    parser.add_argument("--delimiter", default=",", help=r"one character, or \t for tab")
    parser.add_argument("--encoding", default="utf-8-sig", help="default: utf-8-sig (BOM safe)")
    parser.add_argument("--max-rows", type=positive_int, default=100000,
                        help="per-file limit; default 100000 (in-memory comparison)")
    parser.add_argument("--output", type=Path, help="new JSON file; never overwrites an existing file")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    delimiter = '\t' if args.delimiter == r'\t' else args.delimiter
    try:
        with args.before.open(encoding=args.encoding, newline="") as stream:
            before = load_table(stream, args.key, label="before", delimiter=delimiter,
                                max_rows=args.max_rows)
        with args.after.open(encoding=args.encoding, newline="") as stream:
            after = load_table(stream, args.key, label="after", delimiter=delimiter,
                               max_rows=args.max_rows)
        report = compare(before, after, args.key, args.ignore)
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        if args.output:
            # Exclusive creation protects input files, symlinks, and previous reports.
            with args.output.open("x", encoding="utf-8", newline="") as stream:
                stream.write(text)
        else:
            sys.stdout.write(text)
        return 1 if report["summary"]["has_differences"] else 0
    except (InputError, OSError, UnicodeError, LookupError) as exc:
        print(f"csv-keydiff: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
