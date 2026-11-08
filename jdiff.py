#!/usr/bin/env python3
"""jdiff - a readable diff for JSON files.

`diff` on JSON tells you line 412 changed. That is true and useless: the
formatter moved everything, or a key order changed, and the one edit you
care about is buried in three hundred lines of noise.

    $ jdiff before.json after.json
    ~ server.port          8080 -> 9090
    + features.dark_mode   true
    - config.legacy_mode

Exit codes: 0 identical, 1 cannot read a file, 2 usage, 3 differences found.

Zero dependencies. Python 3.9+.
"""

import argparse
import json
import sys

VERSION = "0.1.0"
EXIT_SAME, EXIT_ERROR, EXIT_USAGE, EXIT_DIFF = 0, 1, 2, 3

ADDED, REMOVED, CHANGED = "+", "-", "~"


class Change:
    def __init__(self, op, path, old=None, new=None):
        self.op, self.path, self.old, self.new = op, path, old, new

    def as_dict(self):
        d = {"op": self.op, "path": self.path}
        if self.op in (REMOVED, CHANGED):
            d["old"] = self.old
        if self.op in (ADDED, CHANGED):
            d["new"] = self.new
        return d


def brief(value, width=60):
    """Qiymatni bir qatorga sig'adigan qilib ko'rsatadi."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= width:
        return text
    if isinstance(value, dict):
        return "{%d keys}" % len(value)
    if isinstance(value, list):
        return "[%d items]" % len(value)
    return text[:width - 1] + "…"


def join(path, part):
    if isinstance(part, int):
        return "%s[%d]" % (path, part)
    return "%s.%s" % (path, part) if path else str(part)


def key_of(item, field):
    return item.get(field) if isinstance(item, dict) else None


def diff_lists(a, b, path, field, out, ignore):
    """Ro'yxatlarni taqqoslaydi.

    Sukut bo'yicha indeks bo'yicha. Bu obyektlar ro'yxatida yomon ishlaydi:
    boshiga bitta element qo'shilsa, hamma narsa surilib, diff butunlay
    shovqinga aylanadi. --array-by berilsa, elementlar kalit bo'yicha
    moslashtiriladi va natija o'qiladigan bo'ladi.
    """
    if field and all(isinstance(x, dict) for x in a + b):
        a_keys = [key_of(x, field) for x in a]
        b_keys = [key_of(x, field) for x in b]
        if None not in a_keys and None not in b_keys \
                and len(set(a_keys)) == len(a) and len(set(b_keys)) == len(b):
            a_map = dict(zip(a_keys, a))
            b_map = dict(zip(b_keys, b))
            for key in a_keys:
                here = join(path, "%s=%s" % (field, key))
                if key not in b_map:
                    record(out, ignore, Change(REMOVED, here, old=a_map[key]))
                else:
                    walk(a_map[key], b_map[key], here, field, out, ignore)
            for key in b_keys:
                if key not in a_map:
                    record(out, ignore,
                           Change(ADDED, join(path, "%s=%s" % (field, key)),
                                  new=b_map[key]))
            return

    for i in range(max(len(a), len(b))):
        here = join(path, i)
        if i >= len(a):
            record(out, ignore, Change(ADDED, here, new=b[i]))
        elif i >= len(b):
            record(out, ignore, Change(REMOVED, here, old=a[i]))
        else:
            walk(a[i], b[i], here, field, out, ignore)


def record(out, ignore, change):
    if any(change.path == p or change.path.startswith(p + ".")
           or change.path.startswith(p + "[") for p in ignore):
        return
    out.append(change)


def walk(a, b, path, field, out, ignore):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a:
            here = join(path, key)
            if key not in b:
                record(out, ignore, Change(REMOVED, here, old=a[key]))
            else:
                walk(a[key], b[key], here, field, out, ignore)
        for key in b:
            if key not in a:
                record(out, ignore, Change(ADDED, join(path, key), new=b[key]))
        return
    if isinstance(a, list) and isinstance(b, list):
        diff_lists(a, b, path, field, out, ignore)
        return
    # bool va int Python'da teng bo'lishi mumkin (True == 1), lekin JSON'da
    # bu boshqa narsa -- shuning uchun tur ham tekshiriladi
    if a != b or type(a) is not type(b):
        record(out, ignore, Change(CHANGED, path, old=a, new=b))


def diff(a, b, field=None, ignore=()):
    out = []
    walk(a, b, "", field, out, list(ignore))
    out.sort(key=lambda c: c.path)
    return out


def load(path):
    try:
        if path == "-":
            return json.load(sys.stdin)
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise ValueError("%s: invalid JSON: %s" % (path, e))
    except OSError as e:
        raise ValueError("%s: %s" % (path, e))


def render(changes, keys_only):
    width = min(40, max((len(c.path) for c in changes), default=0))
    for c in changes:
        path = c.path.ljust(width)
        if keys_only or c.op == REMOVED:
            print("%s %s" % (c.op, c.path))
        elif c.op == ADDED:
            print("%s %s  %s" % (c.op, path, brief(c.new)))
        else:
            print("%s %s  %s -> %s" % (c.op, path, brief(c.old), brief(c.new)))


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="jdiff",
        description="A readable diff for JSON files.",
        epilog="example: jdiff before.json after.json --array-by id")
    p.add_argument("left", metavar="BEFORE")
    p.add_argument("right", metavar="AFTER")
    p.add_argument("--array-by", metavar="KEY", dest="field",
                   help="match list items by this key instead of by position")
    p.add_argument("--ignore", action="append", default=[], metavar="PATH",
                   help="skip this path and everything under it (repeatable)")
    p.add_argument("--keys-only", action="store_true",
                   help="report structure changes, not value changes")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="version", version="jdiff " + VERSION)
    args = p.parse_args(argv)

    try:
        left, right = load(args.left), load(args.right)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return EXIT_ERROR

    changes = diff(left, right, args.field, args.ignore)
    if args.keys_only:
        changes = [c for c in changes if c.op != CHANGED]

    if args.json:
        print(json.dumps({"ok": not changes,
                          "changes": [c.as_dict() for c in changes]},
                         indent=2, sort_keys=True, ensure_ascii=False))
    elif not changes:
        print("identical")
    else:
        render(changes, args.keys_only)
        print("\n%d change%s" % (len(changes), "" if len(changes) == 1 else "s"))
    return EXIT_DIFF if changes else EXIT_SAME


if __name__ == "__main__":
    sys.exit(main())
