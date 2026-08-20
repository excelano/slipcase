# Conformance corpus

Test containers for slipcase 1.0, described by `manifest.toml` and built by
`generate.py`.

```
python3 generate.py          # writes cases/ — 76 containers
python3 generate.py --list   # case ids and expected verdicts
```

Requires Python 3.11 or later. Nothing else is needed: the ZIP writer is in
`generate.py`, because the standard library cannot produce duplicate member
names, a local file header that disagrees with the central directory, a CP437
name with general purpose bit 11 clear, or an entry that is not a regular file.

`cases/` is generated and is not committed. Every container is deterministic —
fixed timestamps, no randomness — so regenerating an unchanged case reproduces
it byte for byte.

## This corpus is not normative

Where a case and `SPEC.md` disagree, the specification wins and the case is a
bug. The corpus exists to make implementations agree about what §2 already
says, not to say anything of its own.

## Verdicts

| Verdict | Meaning |
|---|---|
| `accept` | Conformant. An implementation MUST NOT reject it. |
| `reject` | Non-conformant. An implementation MUST reject it. |
| `undetermined` | §2.2: the metadata member cannot be read, so conformance cannot be established. Report neither verdict. |
| `out-of-scope` | §2.4: declares a `slipcase_version` other than the one under test. Not a failure. |

## What this cannot test

Section 2 states properties of a container, so each case is a file plus an
expected verdict. Section 3 states requirements on programs — preserving unknown
keys, writing only the payload on extract, refusing to sanitize a bad
`payload.file` — and no sample file can test those. They need a harness that
runs an implementation and inspects what it did. None exists yet.

## Two containers worth knowing about

`accept/encrypted-payload.slpc` and `undetermined/encrypted-metadata-member.slpc`
use ZipCrypto with the password `conformance`.

`accept/metadata-inline-table-multiline.slpc` uses an inline table spanning
several lines, which is legal in TOML 1.1.0 and not in 1.0.0. It is the only
case that fails if an implementation links a 1.0.0 parser, which §2.2 no longer
permits.
