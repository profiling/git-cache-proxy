"""Report CLI flag changes between two `git-cache-proxy --help` outputs.

Usage: cli_diff.py OLD_HELP_FILE NEW_HELP_FILE
Prints Markdown: flags added, removed, and flags whose default changed.
"""
import re
import sys

OPTION = re.compile(r"^ {2,8}(?:-\w, )?(--[a-z0-9][a-z0-9-]*)")
DEFAULT = re.compile(r"\[default: ([^\]]*)\]")


def parse(path):
    flags, current = {}, None
    for line in open(path, encoding="utf-8").read().splitlines():
        m = OPTION.match(line)
        if m:
            current = m.group(1)
            flags[current] = None
        if current:
            d = DEFAULT.search(line)
            if d:
                flags[current] = d.group(1)
    return flags


def main(old_path, new_path):
    old, new = parse(old_path), parse(new_path)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(f for f in set(old) & set(new) if old[f] != new[f])
    if not (added or removed or changed):
        print("No CLI argument changes.")
        return
    for title, items in (("Added", added), ("Removed", removed)):
        if items:
            print(f"**{title}**")
            for f in items:
                default = (new if title == "Added" else old)[f]
                print(f"- `{f}`" + (f" (default `{default}`)" if default is not None else ""))
            print()
    if changed:
        print("**Default changed**")
        for f in changed:
            print(f"- `{f}`: `{old[f]}` -> `{new[f]}`")


main(sys.argv[1], sys.argv[2])
