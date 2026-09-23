# Contributing

Slipcase is a specification. Most of what it needs is not code.

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
name that the `content.file` exclusions fail to exclude, or an ambiguity that lets
two conforming readers resolve the same container differently.

## A rule and its reasoning travel together

`SPEC.md` states what a conformant container is. `DESIGN.md` records why each rule
is the way it is. A change to one needs the matching change to the other in the
same commit, or the reasoning behind a rule ends up written down nowhere.

## The conformance corpus is not normative

Where a case in `conformance/` and `SPEC.md` disagree, the specification wins and
the case is a bug. See `conformance/README.md`.

## The version key

While a version is a draft, changes to it land without moving the number.
Once a version is declared final, any change to what counts as a conformant
container moves `slipcase_version`, and editorial changes — corrections,
clarifications, added examples — do not. §2.4 is the rule; it governs this
repository as much as it governs a reader. 1.0 is final as of 2026-08-29, and
1.1 as of 2026-09-22.

A tag marks each revision of the specification: `v1.0` is the text as
declared final on 2026-08-29, and `v1.1` the text as declared final on
2026-09-22. Both exist because the media type registration cites an address
that has to outlive several years of commits, and a `blob/main` link follows
the branch. So a tag names a revision rather than a version: an editorial
change stays under its version's number under §2.4 and gets a tag of its own
rather than moving this one, and a change that moves `slipcase_version` gets
both. Editorial revisions are tagged `v1.0.1`, `v1.1.1`, and so on: the third
number counts revisions of the text and is not part of `slipcase_version`.

`conformance/` is what makes the distinction checkable rather than arguable. A
change that alters no case's verdict is editorial; one that alters any case's
verdict is not. Generate the corpus before and after and compare, which is what
`DESIGN.md` records as the reason the cost of going final is smaller than it
looks.
