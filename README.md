<h1 align="center">jdiff</h1>

<p align="center">
  <b>A readable diff for JSON files.</b>
</p>

<p align="center">
  <a href="https://github.com/Viltrumlik/jdiff/actions/workflows/ci.yml"><img src="https://github.com/Viltrumlik/jdiff/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

`diff` tells you line 412 changed. True, and useless: the formatter moved everything, or a key order changed, and the one edit you care about is buried in three hundred lines of noise.

```console
$ jdiff before.json after.json
- config
+ features       {"dark_mode": true}
~ server.port    8080 -> 9090

3 changes
```

Key order is never a difference. Paths are, so you can find the thing.

## Lists of objects

This is where a normal diff falls apart. Insert one item at the front and everything after it shifts:

```console
$ jdiff before.json after.json
~ users[0].id    2 -> 0
~ users[0].name  "Bobur" -> "Yangi"
~ users[1].id    1 -> 2
~ users[1].name  "Alisher" -> "Bobur"
+ users[2]       {"id": 1, "name": "Alisher M"}
```

Match the items by a key instead, and the real changes appear:

```console
$ jdiff before.json after.json --array-by id
+ users.id=0       {"id": 0, "name": "Yangi"}
~ users.id=1.name  "Alisher" -> "Alisher M"
```

One user added, one renamed. That is what actually happened.

If the key is missing from an item, or is not unique, it falls back to position rather than guessing.

## Options

| | |
|---|---|
| `--array-by KEY` | match list items by this key instead of position |
| `--ignore PATH` | skip a path and everything under it (repeatable) |
| `--keys-only` | structure changes only, no value changes |
| `--json` | machine-readable |

`-` reads one side from stdin.

Exit codes: `0` identical · `1` cannot read a file · `2` usage · `3` differences found.

```bash
jdiff a.json b.json --ignore meta --ignore build.timestamp
curl -s api/v1/schema | jdiff schema.json -
```

## One deliberate decision

JSON `true` and `1` are different values, and so are `1` and `1.0`. Python calls them equal, so the comparison checks the type as well. A config that quietly turned a boolean into a number is exactly the change you want to catch.

## Install

```bash
pipx install git+https://github.com/Viltrumlik/jdiff
```

Or take the file:

```bash
curl -O https://raw.githubusercontent.com/Viltrumlik/jdiff/main/jdiff.py
python3 jdiff.py a.json b.json
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

32 tests. CI runs on Ubuntu, macOS and Windows with Python 3.9 through 3.13.

## License

[MIT](LICENSE) © Alisher Muhammadaliyev ([@Viltrumlik](https://github.com/Viltrumlik))
