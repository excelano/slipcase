# Slipcase — Design Document

**Status:** design draft.
**Document version:** draft, 2026-08-20
**Specification version:** 1.0

`SPEC.md` states the rules. This document says why each one is drawn where it is,
and what was considered and rejected. Nothing here is normative: where the two
disagree, the specification wins and this document is wrong.

So this document does not restate a rule in order to explain it. A rule lives in
one place, and a change to a rule is an edit to `SPEC.md` alone; a change to the
reasoning is an edit here alone. Rules are cited as **SPEC §2.1**, never as a bare
section number, because both documents have a §3 and they are not the same
subject.

---

## 1. What this is about

`README.md` states what Slipcase is and the problem it addresses: most files have
nowhere to put metadata, and the usual answers — filenames, sidecars, a database —
each fail as soon as the file moves. This document assumes that framing and takes
up where it leaves off.

One property of it bears on almost every decision below. Slipcase is
domain-neutral: nothing in the format knows about any particular industry, system,
or kind of document. Where a rule could have been bent toward one kind of payload,
it was not.

---

## 2. Created with ordinary tools

A container can be built with `zip` and a text editor, and its contents recovered
with `unzip`. No Slipcase implementation is required at either end, on any
platform, and there is no incantation to get right:

```bash
cat > slipcase.metadata.toml <<'EOF'
slipcase_version = "1.0"

[payload]
file = "report.pdf"
EOF

zip report.pdf.slpc slipcase.metadata.toml report.pdf
```

That is a conformant container. Nothing about member order, compression method,
or byte layout is specified, so there is no way to produce a subtly wrong one by
using the wrong tool.

This is a design goal rather than a side effect. A metadata format that can only
be read by its own tooling has moved the problem rather than solved it, and the
metadata is a TOML file so a person can open it and read it with nothing
installed.

**This sets a complexity budget:** the format must be implementable in an
afternoon by someone working from `SPEC.md` alone. A rule that cannot be explained
in a sentence has to justify itself hard.

---

## 3. Why the format is the way it is

### 3.1 Container structure — SPEC §2.1, §2.3, §2.5

**Why `payload.file` is a plain filename.** A payload is one file, not a path into
a tree, and a name that cannot express a path cannot express a traversal. The
colon is excluded because on some platforms a name containing one is treated as
rooted, so joining it to a destination directory discards the destination. Control
characters are excluded because no filesystem accepts them, and a NUL is a
familiar way to make a name end early in one component of a system and not in
another.

Banning the sequence `..` wherever it appears would need exceptions — `a..b` is
a name and not a traversal — and the rule would stop being one rule.

Windows device names — `CON`, `NUL`, `COM1`, and names ending in a space or a dot
— stay legal. They are unwritable on one platform and ordinary on every other, and
a rule about traversal should not acquire a table of one operating system's
reserved words. An implementation that cannot write the name it was given has a
problem to report, not a name to change.

**Why the payload must be a regular file entry.** An earlier draft named symbolic
links alone, which left directories, device nodes, and FIFOs unaddressed for no
better reason than that links were the case worth worrying about. Naming the one
kind that is permitted is shorter and closes the rest.

**Why names are decoded before they are compared.** ZIP has no single name
encoding. A reader and a writer that decode differently will disagree about
whether `payload.file` matches any member, and the payload becomes unfindable in
the containers whose names are not ASCII.

**A rule for names flagged UTF-8 that are not UTF-8 was considered and rejected.**
ZIP lets a writer set general purpose bit 11 over arbitrary bytes and validates
nothing, and decoders diverge on invalid input: Go's `archive/zip` keeps the
raw bytes, Rust's `zip` substitutes U+FFFD, Python's `zipfile` refuses to open
the archive. A rule would have reached none of them — Go complies without
knowing it exists, Python cannot comply at all, and a Rust implementer either
has read the crate's source and already found the problem or has not and would
not apply the rule. The file it guards against needs a `payload.file` carrying
U+FFFD, which only arises when something upstream already decoded a filename
lossily.

**Why the central directory decides.** A member's name is recorded in both its
local file header and the central directory, and nothing requires the two to
agree. Without naming one authoritative, two conforming readers can be walked into
finding different payloads in the same file. Info-ZIP already resolves it this
way, reporting the disagreement and continuing with the central directory name.

**Why the recorded offsets are taken from the start of the file.** A ZIP's end of
central directory record says where the central directory begins, and that number
is an offset from the start of the archive rather than from the start of the file.
Where something has been put in front of the archive — a self-extracting stub,
usually — the two differ, and mainstream implementations recover by measuring the
discrepancy and adding it to every offset they read. Info-ZIP does this, Python's
`zipfile` does this, and so does the Rust `zip` crate.

Declining to do it costs interoperability and buys what allowing no duplicate
bought: a file with one reading. Adjusting offsets makes a file holding two
archives readable as either, depending on where a reader starts, and it lets one file be a
container and an executable at once, each reader finding the thing it came for.
That is content-type confusion, and it is the attack a format invites when its whole
purpose is to hand a payload to whatever the operating system has registered for
it. Duplicate names were refused rather than resolved because which one wins has
no good answer. Which archive wins has no better one.

The cost is real. A container carrying a stub
is not a container, and a tool that appends bytes to files breaks every container
it touches. Neither is a thing this format asks for: a container is a file with an
extension of its own, not a document smuggled inside another.

**Why the record must also end the file, and count its members once.** The rule
above was written against the two shapes anybody had thought of, and a review on
2026-08-27 found three more, all in the same record and all measured against the
reference implementation. Its end of central directory record carries two entry
counts — records on this disk, records in total — which every writer sets equal
and which that implementation and its ZIP dependency read from *different* fields;
declaring three and two hid a duplicate payload behind a conformant verdict. Its
comment length can be made to run past the end of the file, so that a reader
taking the last signature it finds and a reader checking the length before
believing it resolve two different directories. And which fields carry the Zip64
sentinel decides which of two records a reader believes.

None of the three is a disagreement about what the file means. Each is a
disagreement about which bytes the file *is*, and every one of them ends with two
conforming readers holding the same file and naming different payloads — which is
what §2.1 already refused for duplicate member names and for two archives in one
file, arriving a third time through a smaller door. So the record is required to
be internally consistent rather than merely present, and a reader is spared
having to match another reader's field-by-field behaviour to stay in agreement
with it.

**Why comparison is exact.** Case-sensitive and without normalization, because
both alternatives are worse: case folding depends on locale, and normalizing means
a payload can be found under a name it does not carry. The cost falls on writers
taking names from macOS, which returns NFD where most sources produce NFC, and
that is a writer's problem with a writer's fix.

**Why there is one of each defined member and not at least one.** ZIP permits
duplicate names, and a format that allowed them would have to say which duplicate
wins — a question with no good answer, and one that other ZIP-based formats have
spent years watching tools disagree about.

**Why extra members are allowed.** Both defined members are found by name, so
nothing about locating them depends on what else is present. A rule against extra
members would make every archive produced by macOS Finder invalid while buying
nothing, and nothing extracts them in any case.

**Why the specification lists what it does not constrain.** An implementer reading
about a ZIP-based format will reasonably wonder whether member order, compression
method, timestamps, encryption, or Zip64 are pinned. SPEC §2.5 answers all of them
at once so that nobody writes a reader that rejects a container for a property the
format never cared about. A zero-byte payload is valid for the same reason: an
empty file is a file, and someone would otherwise guess it was not.

**Why no magic bytes.** The extension and media type live outside the container.
The alternative — a `mimetype` member stored uncompressed at a known offset — is
examined and rejected in §5.

### 3.2 The metadata member — SPEC §2.2, §2.4

**Why it is mandatory, and why its name is fixed.** There is no such thing as a
Slipcase container without metadata. The fixed name is what makes the payload
discoverable, since the payload's own name is not known in advance.

**Why the TOML version is pinned.** An implementer otherwise does not know which
grammar to write against. It is unrelated to `slipcase_version`, which names this
specification rather than the metadata language.

**Why a byte order mark is permitted.** TOML says nothing about a leading mark and
parsers split on whether to strip one or reject it, so the format decides rather
than leaving it to whichever library an implementation happens to link. Rejecting
would punish someone whose editor inserted a character they cannot see, which sits
badly with a format that advertises hand-editing.

**Why an unreadable metadata member is undetermined.** SPEC §2.5 does not permit
rejecting a container because a member is encrypted, while SPEC §2.2 requires the
metadata member to parse as TOML, which an encrypted member does not. The
requirement therefore applies to the decrypted content, and a container whose
metadata cannot be read is undetermined rather than non-conformant. A reader
without the key knows it cannot answer the question, and that is different from
knowing the answer is no.

**On the version.** The line is drawn at what counts as a conformant container
rather than at any edit to this document, so the number moves only when
something about containers does. Fixing a typo cannot invalidate a container
written yesterday.

**Why 1.0 is final, and what that costs.** Marked final on 2026-08-29, when the
format acquired the three things that make a version worth freezing: a
conformance corpus of 88 cases that two implementations agree on, a published
library and a released application that read containers people other than their
authors will write, and a media type registration asking IANA to record a
permanent name. The last is what forced the question rather than merely raising
it — a registration citing a specification that describes itself as unfinished
invites the reviewer's first question, and the answer would have to be that the
format is in fact settled, which is a thing to write in the document rather than
in a reply.

What it costs is the freedom `CONTRIBUTING.md` granted while the document was a
draft: a change to what counts as a conformant container now moves
`slipcase_version` instead of landing quietly. That is a smaller cost here than
it looks, because §2.4 already says the number promises nothing to a program, so
moving it breaks no contract — it announces. The corpus is what makes the
distinction checkable: a change that alters no case's verdict is editorial, and
one that alters any case's verdict is not, which is a test rather than a
judgement.

**Why conformance is relative to a version.** This specification can say whether a
container declaring `1.0` conforms to it. It cannot say anything about one
declaring `2.0`, because it does not know what `2.0` requires, and the same holds
for a value naming no version at all. Such a container is outside the question
rather than failing it. Treating an unrecognized value as non-conformance would
make every future container retroactively broken by every reader written today.

**Why the number implies no compatibility, at any level.** Every substantive
revision is one an older implementation may be unable to absorb, whether it
relaxes a rule, tightens one, or adds a required key. The one category that would
be safe — new optional keys and members — needs no version change at all, since
SPEC §3 already requires unknown ones to be preserved.

**Why any additional key is permitted, permanently.** This is the format's whole
forward-compatibility story and must never be revised. A container that carries
keys nobody has defined yet is the mechanism by which the format grows without
breaking.

**Why there is no canonical serialization.** TOML has none. Two tools writing the
same metadata will not produce identical bytes, and a container whose metadata has
been rewritten will not reproduce its original bytes even when the content is
unchanged. Anything built on top has to account for that rather than assume
re-serialization is stable.

**Why the format defines no vocabulary.** `slipcase_version` and `payload.file`
are structural: a reader cannot open the container without them, and both describe
the container rather than the payload. Every other key describes the payload, and
what those keys mean is not something a validator can check against a file.

That work belongs in a separate document with a separate lifecycle. A container
spec should stop changing once it is right; a vocabulary has to grow, because
people keep needing another key. Binding them together forces a choice between a
format that churns and a vocabulary that is stuck.

The consequence is that containers from producers who never agreed on a vocabulary
will carry `title`, `Title`, and `doc_title` side by side. That is a vocabulary
problem with a vocabulary fix, and it is not the container's to solve.

### 3.3 Nesting — SPEC §2.3

Defining a meaning for nesting would mean defining aggregation, which §5
rejects. Prohibiting it would be a rule with nothing behind it, since a
container inside a container is a payload like any other.

### 3.4 The naming convention — SPEC Appendix B

The pattern is `.gz`, `.zst`, and `.gpg`: a suffix appended to a name that keeps
its own. It was adopted rather than invented, so the awkward cases were already
solved — `archive.tar.gz.slpc`, `notes.toml.slpc`, a payload with no extension
at all.

It stays a convention rather than a rule because enforcing it would buy nothing.
`payload.file` is the only authority on what the payload is called, and a reader
that fell back to the container's own name would be guessing.

---

## 4. Why there are requirements on programs — SPEC §3

SPEC §2 states properties of a file, and a validator can check every one of them
against a container without knowing what produced it. SPEC §3 states things a
program must do, and no container can demonstrate those. The two are separated
because they are checked differently: one by a corpus, the other by running an
implementation and watching what it does.

**Order and lookup.** Nothing in SPEC §2.1 fixes member order, so a container
written by any tool in any order is conformant, and a reader that depends on order
will fail on containers it must accept. The payload is found by `payload.file`
alone for the same reason the convention in Appendix B is not a rule: the
convention is not a fallback, position is not a fallback, and no other member may
be treated as the payload.

**Unknown keys and unknown members.** The preservation rule does two jobs. It is
the entire forward-compatibility story, and it is what makes a third-party tool
that rewrites a container safe to use, since a tool that drops what it does not
recognize destroys data silently.

**Extraction.** Other members have no defined meaning, so writing them to disk
hands a caller files the format never described. Anyone wanting a full unpack has
a zip tool for that.

**Rejecting rather than sanitizing.** Sanitizing a bad `payload.file` produces a
file at a path that no longer matches it, which breaks the format's own lookup.

**Uniqueness by enumeration.** SPEC §2.1 says there is one member of each name and
a validator can check it against a file. What makes it a requirement on programs
too is that almost every ZIP library hides the failure: they key their own
directory by name, so two members arrive as one and counting them returns one.
Python's `zipfile` hands back the last, Java's `ZipFile.getEntry` hands back the
last, and a Rust implementation building a map gets whatever its map does. Left
unstated, several implementations can report one container conformant while
disagreeing about which bytes are its metadata, which is the shape of Android's
Master Key bug. Unlike most of this section it can be put to a container, and the
corpus does: `reject/duplicate-metadata-members-agreeing` holds two byte-identical
metadata members, so nothing downstream of the duplicate can fail and a reader
that never counted them accepts it.

**Not overwriting.** SPEC §2.3 guards the boundary of a destination directory: a
name that cannot express a path cannot leave the directory it is joined to. It
says nothing about what is already inside that directory, and it never could —
`.bashrc`, `authorized_keys` and `config` are plain filenames and conformant ones.
A tool extracting into the working directory, which is the natural default for a
tool given one argument, is the exposed case. The rule is on the write rather than
on the name, because the name is not the problem: somebody extracting a payload
called `config` into a directory that has one has a decision to make, and an
implementation's job is to ask rather than to guess. It has to be the creation
that refuses rather than a test before it, or two processes pass the test
together.

**Permission bits.** SPEC §2.5 leaves external attributes unconstrained and forbids
rejecting a container over them, and this section already limits the payload to a
regular file entry. Nothing said what mode the extracted file should carry, and
the idiomatic extraction loop in more than one language restores the recorded one.
A container conformant in every respect could therefore put a setuid, setgid or
world-writable file on disk. Forbidding the restore rather than constraining what
may be recorded keeps §2.5 as it was: a container may record anything, and no
reader acts on it.

**Escaping a name rather than applying it.** SPEC §2.3 excludes the C0 controls and
U+007F because no filesystem accepts them. The Unicode bidirectional formatting
characters are not in that position at all: they are legal on every filesystem, a
writer may hold a file that genuinely has one in its name, and adding them to
§2.3 would turn a rule about paths into a table of special cases — which is what
the same section declines to do with Windows device names. So it is a display
problem, and it is written as one.

Isolating was the alternative, and it was rejected. Wrapping the
displayed name in U+2066 and U+2069 confines the reordering to one field, and a
name that reads as `report.pdf` inside its own field is still a name that reads as
`report.pdf`; the field exists to tell somebody what they are about to open. An
override with no terminator runs to the end of the paragraph rather than the end
of the string, so an implementation relying on containment has to emit the
terminator itself and cannot trust the name to carry one.

The rule names one interpreter and there are others, which is why §3 carries a
sentence generalising it rather than a second requirement. Bidi can be stated as
a requirement because the character set is enumerable and the obligation is
identical wherever a name is shown. Markup cannot: the reserved set belongs to
whatever the name is being rendered into, and a corpus that hands a reader a
container can watch what it reports and not what a notification daemon does with
the string afterwards. The instance that could be stated was stated, in §2.3 —
which excludes the C0 controls a terminal acts on, and so closes the medium with
the worst consequences at the format rather than leaving it to display.

**The version rule.** This was once phrased as a prohibition on assuming a
container could be read. That constrained what a program believes rather than what
it does, and §5 gives the test it failed: a rule nothing can check is an opinion,
not a rule. The broad reading was worse than unfalsifiable, because it could not
be satisfied even in principle — declining to treat a `2.0` container as a `1.0`
one requires knowing what `2.0` requires, which is the one thing an implementation
written against `1.0` does not have. Naming a reportable outcome instead gives the
rule the shape of the undetermined rule beside it, and gives a corpus something to
check. What it gives up is the part that was never enforceable.

This section once ended by saying that nothing else in SPEC §3 was a security
requirement, and that decompression bombs and resource limits belonged to whatever
ZIP parser an implementation used, since they applied equally to every ZIP
consumer. Four of the rules above are now security requirements. The
resource-limit claim was wrong in its premise rather than in its conclusion: a ZIP
consumer chooses what to inflate and a reader of this format does not, because
inflating the metadata member is how it finds out whether it is holding a
container. SPEC §6 takes that up, and §6 below says why it is a rule rather than a
library's business.

---

## 5. Non-goals

**Signatures.** Out of scope. Signing layers above Slipcase, or arrives in a later
specification version with its own member, which an implementation written against
1.0 will open and ignore. Anything built on top must account for the absence of a
canonical serialization: hash what was actually signed, rather than assuming a
container re-serializes identically.

**Multiple payloads.** `payload.file` names one member, so the metadata describes
one file. A container may physically hold more, but the format assigns them no
meaning and defines no aggregation mechanism. Naming N payloads would reinvent ZIP
and make the metadata ambiguous about what it describes.

**Encryption.** The format adds none of its own and forbids none. Either member may
be encrypted by ZIP's own mechanisms or by encrypting the file before packing it,
and a container whose metadata is unreadable to a passer-by is still a container:
it is attaching metadata to a file for whoever holds the key. Worth knowing rather
than legislating: ZIP encryption narrows which implementations can open a
container, since Go's `archive/zip` supports none of it and Info-ZIP's `unzip` has
not handled AES.

**Fixity.** No checksum key, and no position on whether a payload has changed. That
is a preservation question, and preservation is a separate discipline with its own
formats. Anyone who wants a digest records one; the format simply does not define
it, in the same way it defines no other descriptive key.

**Mutability.** The format says nothing about whether a container may be edited. A
container edited yesterday is byte-identical in conformance terms to one written
fresh, no reader can detect the difference, and no reader behavior depends on it.
A rule nothing can check is an opinion, not a rule.

**Restricting what else the archive holds.** Considered and rejected, for the
reasons in §3.1. It would also mean a future signed container could not be opened
by a reader written today.

**Identification by content.** The format reserves no magic bytes. EPUB, ODF, and
ASiC place an uncompressed `mimetype` member first so that a fixed byte offset can
be sniffed by `file(1)`, and that trick costs a fixed member order, a
stored-uncompressed rule, a no-extra-fields rule, and a two-step invocation for
anyone building a container by hand. Identification by opening the archive is
sufficient for the format's own purposes, and the simplicity is worth more than
the magic rule.

---

## 6. Why security considerations are a section — SPEC §6

**Why a bound is a rule and not a library's business.** The claim this replaces
held that resource limits belong to whatever library does the parsing, and apply
equally to everyone using that format. True of the payload, which nobody inflates
until somebody asks for it. Not true of the metadata member: identifying a
container *is* inflating and parsing that member, so a reader spends the memory
before it knows whether the file was a container, and a reader invoked by a file
manager spends it without anybody having asked for anything. Deflate returns a
little over a thousand bytes for each one it is given, so the file that does this
is small enough to mail.

**Why no number is given.** Every candidate was wrong somewhere. A megabyte is
generous for the two keys this format defines and mean for anybody using the
metadata for what SPEC §2.2 permits, which is anything they like. A gigabyte is no
bound at all on a phone. The limit has to come from the reader's own situation,
and requiring one without naming it is the most a format can honestly do.

**Why undetermined and not non-conformant.** The bound belongs to the reader, so
exceeding it is a fact about the reader and not about the container. A reader
answering non-conformant would be publishing its own configuration as a property
of somebody else's file, and two readers with different bounds would then disagree
about conformance, which is the disagreement SPEC §3 exists to prevent.
Undetermined already means that conformance cannot be established here, and that
is what is true.

**Why two of the four subjects are notes and not rules.** The encryption channel
and the nesting depth are both consequences of decisions taken in §5 above, and
neither can be closed without reversing one of them. Undetermined is what an
encrypted metadata member yields because the format adds no encryption and forbids
none; a rule against being skipped would be a rule about what a scanner does with
an answer, which is beyond anything this document can require. Nesting is
permitted and meaningless by SPEC §2.3, and a depth limit is only owed by
something that recurses, which the format never asks anyone to do. Writing them
down is what is left, and a property nobody wrote down is one the next implementer
rediscovers.
