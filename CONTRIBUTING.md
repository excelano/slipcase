# Contributing

slipcase is a specification. Most of what it needs is not code.

## Contributions are dedicated to the public domain

Everything in this repository is dedicated to the public domain under
[CC0 1.0](LICENSE). By contributing you dedicate your contribution on the same
terms, waiving copyright and related rights in it to the extent possible under
law. Nothing can be accepted on any other basis: a specification that anyone may
implement, quote, fork, or embed cannot carry a part that they may not.

## What is most useful

A question the specification cannot answer. The format is small and its rules are
short, which makes it easy to read past a case that neither `SPEC.md` nor
`DESIGN.md` decides. Two conforming implementations disagreeing about the same
container is the clearest form of this, and the most valuable thing to report.

Open an issue. A case that the specification leaves open is a specification bug,
not a matter of opinion about what an implementation should do.

## Security

Do not open a public issue for a security defect. Use **Report a vulnerability**
under the Security tab, which reaches the maintainers privately.

For a specification the plausible defects are in the rules rather than in code: a
name that the `payload.file` exclusions fail to exclude, or an ambiguity that lets
two conforming readers resolve the same container differently.

## A rule and its reasoning travel together

`SPEC.md` states what a conformant container is. `DESIGN.md` records why each rule
is the way it is. A change to one needs the matching change to the other in the
same commit, or the reasoning behind a rule ends up written down nowhere.

## The conformance corpus is not normative

Where a case in `conformance/` and `SPEC.md` disagree, the specification wins and
the case is a bug. See `conformance/README.md`.

## The version key

While `SPEC.md` is marked draft, changes land without moving `slipcase_version`.
Once it is final, any change to what counts as a conformant container moves that
number, and editorial changes — corrections, clarifications, added examples — do
not. §2.4 is the rule; it governs this repository as much as it governs a reader.
