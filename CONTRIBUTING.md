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

`SPEC.md` is final as of 2026-08-29, so it is the second half of this rule that
is now in force: any change to what counts as a conformant container moves
`slipcase_version`, and editorial changes — corrections, clarifications, added
examples — do not. §2.4 is the rule; it governs this repository as much as it
governs a reader. While the document was a draft, changes landed without moving
the number, which is why nothing below 1.0 exists to compare against.

A tag marks each revision of the specification, and `v1.0` is the text as
declared final on 2026-08-29. It exists because the media type registration
cites an address that has to outlive several years of commits, and a `blob/main`
link follows the branch. So the tag names a revision rather than a version: an
editorial change stays 1.0 under §2.4 and gets a tag of its own rather than
moving this one, and a change that moves `slipcase_version` gets both.

`conformance/` is what makes the distinction checkable rather than arguable. A
change that alters no case's verdict is editorial; one that alters any case's
verdict is not. Generate the corpus before and after and compare, which is what
`DESIGN.md` records as the reason the cost of going final is smaller than it
looks.
