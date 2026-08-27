# Conformance corpus

Test containers for slipcase 1.0, described by `manifest.toml` and built by
`generate.py`.

```
python3 generate.py          # writes cases/ — 83 containers, then self-checks
python3 generate.py --list   # case ids and expected verdicts
```

Requires Python 3.11 or later. Nothing else is needed: the ZIP writer is in
`generate.py`, because the standard library cannot produce duplicate member
names, a local file header that disagrees with the central directory, a CP437
name with general purpose bit 11 clear, or an entry that is not a regular file.

After writing, the generator holds every `accept` and `out-of-scope` case to
§2.2 and §2.1 and fails if one does not conform. A case declared conformant that
is not conformant is the corpus lying about the specification, which is worse
than having no corpus.

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
`payload.file`, escaping a name before displaying it — and no sample file can
test those.

Some of §3 is reachable anyway, by handing an implementation a container and
reading the verdict it reports: that is what the `out-of-scope/` and
`undetermined/` cases do. Uniqueness is reachable the same way, because a
container carrying duplicate names separates a reader that enumerates the central
directory from one that asks its ZIP library for a name. `reject/duplicate-metadata-members-agreeing`
is the one that reaches it cleanly: the other two can be rejected for a reason
downstream of the duplicate.

Section 6 cannot be tested either, and for a different reason. The bound it
requires on the metadata member belongs to the implementation, so no expected
verdict can depend on it: a reader that answers `undetermined` for a container
larger than its own limit is obeying §6, and the same file would have to be
`accept` for a reader with a larger one. `accept/metadata-high-compression-ratio`
tests the part that does not vary — that a high ratio alone is not grounds to
refuse.

## Containers worth knowing about

`accept/encrypted-payload.slpc` and `undetermined/encrypted-metadata-member.slpc`
use ZipCrypto with the password `conformance`.

`accept/metadata-inline-table-multiline.slpc` uses an inline table spanning
several lines, which is legal in TOML 1.1.0 and not in 1.0.0. It is the only
case that fails if an implementation links a 1.0.0 parser, which §2.2 no longer
permits.

`accept/payload-name-bidi-override.slpc` carries U+202E in `payload.file`. It is
a conformant name and the case expects `accept`; whether the name is displayed
safely is the §3 requirement above, which no file can check. A terminal that
applies the override will render this case id and the name misleadingly, which
is the point of the rule.

`reject/archive-preceded-by-data.slpc` and `reject/two-archives-in-one-file.slpc`
are the two cases mainstream ZIP implementations disagree with. Info-ZIP,
Python's `zipfile` and the Rust `zip` crate all open both by adjusting the
recorded offsets against wherever the archive begins. §2.1 takes those offsets
from the start of the file, so both are non-conformant here and an
implementation built on a library that adjusts has to check the offsets itself.
