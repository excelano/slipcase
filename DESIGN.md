# slipcase — Design Document

**Status:** design draft. Nothing built.
**Document version:** draft, 2026-08-19
**Specification version:** 1.0

---

## 1. What slipcase is

A general-purpose container file format. A `.slpc` file is a ZIP archive holding a payload file of any type together with a TOML metadata file describing it.

It does one thing: it attaches metadata to a file. The two become one file, so copying, moving, or sending the payload carries its metadata along.

slipcase is domain-neutral. Nothing in the format knows about any particular industry, system, or kind of document.

---

## 2. The problem

Most files have nowhere to put metadata. Some formats have an embedded slot — PDF has DocInfo, Office files have OPC core properties, images have XMP — but writing to it means modifying the payload, and a great many types have no slot at all. A CSV, a proprietary CAD file, a scanned TIFF, a video: there is nowhere to record what it is, where it came from, or what it belongs to.

The usual answers each fail differently. Filenames carry very little and no two organizations' conventions agree. Sidecar files sit next to the payload until someone copies one and not the other. Databases and document management systems hold the metadata well, right up until the file leaves the system, and then the two are separated with nothing to reconnect them.

slipcase puts the file and its metadata in one container, so there is nothing to separate.

---

## 3. Created with ordinary tools

A container can be built with `zip` and a text editor, and its contents recovered with `unzip`. No slipcase implementation is required at either end, on any platform, and there is no incantation to get right:

```bash
cat > slipcase.metadata.toml <<'EOF'
slipcase_version = "1.0"

[payload]
file = "report.pdf"
EOF

zip report.pdf.slpc slipcase.metadata.toml report.pdf
```

That is a conformant container. Nothing about member order, compression method, or byte layout is specified, so there is no way to produce a subtly wrong one by using the wrong tool.

This is a design goal rather than a side effect. A metadata format that can only be read by its own tooling has moved the problem rather than solved it, and the metadata is a TOML file so a person can open it and read it with nothing installed.

**This sets a complexity budget:** the format must be implementable in an afternoon by someone working from this document alone. A rule that cannot be explained in a sentence has to justify itself hard.

---

## 4. The format

Everything in this section is a property of a file. A validator can check every rule here against a container without knowing what produced it. Requirements on programs live in §5.

Normative language throughout §4 and §5: MUST / MUST NOT / MAY.

### 4.1 Container structure

A slipcase container is a ZIP archive containing a member named `slipcase.metadata.toml` and a member named by `payload.file`.

Two rules:

- `payload.file` MUST be a plain filename: non-empty, not `.` or `..`, and containing no `/`, `\`, `:`, or control character. A payload is one file, not a path into a tree — and a name that cannot express a path cannot express a traversal. The colon is excluded because on some platforms a name containing one is treated as rooted, so joining it to a destination directory discards the destination. Control characters are excluded because no filesystem accepts them and a NUL is a familiar way to make a name end early in one component of a system and not in another.
- The payload member MUST be a regular file entry. An earlier draft named symbolic links alone, which left directories, device nodes, and FIFOs unaddressed for no better reason than that links were the case worth worrying about. Naming the one kind that is permitted is shorter and closes the rest.

Member names are compared as the archive encodes them: as UTF-8 where ZIP's general purpose bit 11 is set, and as CP437 otherwise. ZIP has no single name encoding, so a reader and a writer that decode differently will disagree about whether `payload.file` matches any member, and the payload becomes unfindable in the containers whose names are not ASCII.

Two further matching rules exist because ZIP leaves a reader room to be clever. A member's name is recorded in both its local file header and the central directory, and nothing requires the two to agree, so the central directory is named as authoritative; otherwise two conforming readers can be walked into finding different payloads in the same file. Comparison is then exact over decoded code points, case-sensitive and without normalization, because both alternatives are worse. Case folding depends on locale, and normalizing means a payload can be found under a name it does not carry. The cost falls on writers taking names from macOS, which returns NFD where most sources produce NFC, and that is a writer's problem with a writer's fix.

A container holds one metadata member and one payload member, not at least one. ZIP permits duplicate names, and a format that allowed them would have to say which duplicate wins — a question with no good answer, and one that other ZIP-based formats have spent years watching tools disagree about.

Other members' names are unconstrained, because nothing extracts them (§5). Everything else about the ZIP is unconstrained too, and the following are stated only so that an implementer does not assume a restriction that is not there:

- Additional members are permitted and have no defined meaning. Both defined members are found by name, so nothing about locating them depends on what else is present. A container produced by a tool that adds its own artifacts — `.DS_Store`, `__MACOSX/`, `desktop.ini` — is a valid container.
- Member order is not specified. Neither is compression method, timestamp, encryption, or any other byte-level detail.
- A zero-byte payload is valid. An empty file is a file.

The extension is `.slpc`. The media type is `application/x.slipcase+zip`, provisional in the unregistered `x.` tree. Neither appears inside a container: a container is identified by opening it and finding a valid `slipcase.metadata.toml`, and the format reserves no magic bytes.

### 4.2 The `slipcase.metadata.toml` member

Mandatory. There is no such thing as a slipcase container without metadata. Its name is fixed, which is what makes the payload discoverable, since the payload's own name is not.

The member MUST be valid **TOML 1.1.0** and MUST be UTF-8 encoded, as TOML 1.1.0 requires. Pinning the TOML version matters because an implementer otherwise does not know which grammar to write against; it is unrelated to `slipcase_version` below.

TOML says nothing about a leading byte order mark, and parsers split on whether to strip one or reject it, so the format decides: a mark is permitted and readers skip it. The alternative punishes someone whose editor inserted a character they cannot see, which sits badly with a format that advertises hand-editing.

Encryption forced a smaller decision. §4.1 does not permit rejecting a container because a member is encrypted, while this section requires the metadata member to parse as TOML, which an encrypted member does not. So the requirement applies to the decrypted content, and a container whose metadata cannot be read is *undetermined* rather than non-conformant. A reader without the key knows it cannot answer the question, and that is different from knowing the answer is no.

Two keys are required. No key is forbidden:

```toml
slipcase_version = "1.0"

[payload]
file = "GA-DRW-0142-RevC.pdf"
```

- `slipcase_version` — string. The version of the slipcase specification the container follows.
- `payload.file` — string. The ZIP member name of the payload. MUST match a member in the archive.

**On the version.** It names the specification version, not the payload's version. Editorial revisions do not move it: fixing a typo, clarifying a paragraph, or adding an example leaves the number alone, because none of those changes what a conformant container is. Only a change to that moves it.

The number is a string, and dotted. The minor component tells a reader how large a revision was — `1.1` is a small change, `2.0` is a rework.

**Conformance is relative to a version.** This document can say whether a container declaring `1.0` conforms to it. It cannot say anything about one declaring `2.0`, because it does not know what `2.0` requires, and the same holds for a value naming no version at all. Such a container is outside the question rather than failing it. Treating an unrecognized value as non-conformance would make every future container retroactively broken by every reader written today, which is the opposite of what §5 asks for.

**The number implies no compatibility, at any level.** Every substantive revision of this format is one an older implementation may be unable to absorb, whether it relaxes a rule, tightens one, or adds a required key. The one category that would be safe — new optional keys and members — needs no version change at all, since §5 already requires unknown ones to be preserved. So the minor component carries magnitude, never a promise. What an implementation must do about that is in §5.

Everything else is free-form. A container MAY carry any additional keys, and carrying them does not make it non-conformant. This is fixed and must never be revised. What programs must do with those keys is in §5.

The format defines no canonical TOML serialization, because TOML has none. Two tools writing the same metadata will not produce identical bytes, and a container whose metadata has been rewritten will not reproduce its original bytes even when the content is unchanged.

**The format defines no vocabulary.** `slipcase_version` and `payload.file` are structural — a reader cannot open the container without them, and both describe the container rather than the payload. Every other key describes the payload, and what those keys mean is not something a validator can check against a file.

That work belongs in a separate document with a separate lifecycle. A container spec should stop changing once it is right; a vocabulary has to grow, because people keep needing another key. Binding them together forces a choice between a format that churns and a vocabulary that is stuck.

The consequence is that containers from producers who never agreed on a vocabulary will carry `title`, `Title`, and `doc_title` side by side. That is a vocabulary problem with a vocabulary fix, and it is not the container's to solve.

### 4.3 The payload

Exactly one file. Any type, any size. Its member name MUST equal `payload.file` and MUST NOT be `slipcase.metadata.toml`.

Only the names `.` and `..` are excluded, not the sequence wherever it occurs. `a..b` is a name and not a traversal, and the rule is written as an exclusion of two names so that it stays one.

Windows device names — `CON`, `NUL`, `COM1`, and names ending in a space or a dot — stay legal. They are unwritable on one platform and ordinary on every other, and a rule about traversal should not acquire a table of one operating system's reserved words. An implementation that cannot write the name it was given has a problem to report, not a name to change.

A payload MAY itself be a slipcase container. Nesting requires no special handling, since a `.slpc` inside a `.slpc` is just a payload. The format neither prohibits nesting nor defines a use for it.

### 4.4 Naming convention (non-normative)

By convention a container is named for its payload with `.slpc` appended: `foo.pdf.slpc` holds `foo.pdf`. This is the same pattern as `.gz`, `.zst`, and `.gpg`, and it keeps the payload's own extension visible, so what is inside can be guessed without opening the container. It also survives the awkward cases — `archive.tar.gz.slpc`, `notes.toml.slpc`, a payload with no extension at all.

It remains a convention and nothing more. Nothing enforces it, a container may be named anything, and `payload.file` is the only authority on what the payload is called.

---

## 5. Implementation requirements

Requirements on programs rather than on files. Nothing here is checkable against a container; it is checkable only by running an implementation against containers.

- An implementation MUST NOT depend on the order of members. Nothing in §4.1 fixes it, so a container written by any tool in any order is conformant.
- An implementation MUST locate the payload by `payload.file`. The naming convention in §4.4 is not a fallback, position is not a fallback, and no other member may be treated as the payload.
- **An implementation MUST preserve unknown keys in the metadata and MUST NOT reject a container because of them.**
- An implementation that rewrites a container MUST preserve members it does not recognize, for the same reason.
- An implementation MUST NOT assume it can read a container whose `slipcase_version` it does not recognize, including one that differs only in its minor component (§4.2).
- When extracting, an implementation MUST write only the payload and, if it needs it, `slipcase.metadata.toml`. Other members have no defined meaning and MUST NOT be written to disk. Anyone wanting a full unpack has a zip tool for that.
- An implementation MUST reject a container whose `payload.file` violates §4.1, rather than sanitizing it. Sanitizing produces a file at a path that no longer matches `payload.file`, which breaks the format's own lookup.

The unknown-keys rule does two jobs. It is the entire forward-compatibility story, and it is what makes a third-party tool that rewrites metadata safe to use, since a tool that drops keys it does not recognize destroys data silently.

Nothing else here is a security requirement. Decompression bombs, resource limits, and the rest are concerns for whatever zip parser an implementation uses, not for this format — they apply equally to every zip consumer, and a rule here would be unverifiable in both directions.

---

## 6. Non-goals

**Signatures.** Out of scope. Signing layers above slipcase, or arrives in a later specification version with its own member — which an implementation written against 1.0 will open and ignore, since §4.1 permits members it does not know. Anything built on top must account for §4.2: hash what was actually signed, rather than assuming a container re-serializes identically.

**Multiple payloads.** `payload.file` names one member, so the metadata describes one file. A container may physically hold more (§4.1), but the format assigns them no meaning and defines no aggregation mechanism. Naming N payloads would reinvent ZIP and make the metadata ambiguous about what it describes.

**Encryption.** The format adds none of its own and forbids none. Either member may be encrypted by ZIP's own mechanisms or by encrypting the file before packing it, and a container whose metadata is unreadable to a passer-by is still a container — it is attaching metadata to a file for whoever holds the key. Worth knowing rather than legislating: ZIP encryption narrows which implementations can open a container, since Go's `archive/zip` supports none of it and Info-ZIP's `unzip` has not handled AES.

**Fixity.** No checksum key, and no position on whether a payload has changed. That is a preservation question, and preservation is a separate discipline with its own formats. Anyone who wants a digest records one — the format simply does not define it, in the same way it defines no other descriptive key.

**Mutability.** The format says nothing about whether a container may be edited. A container edited yesterday is byte-identical in conformance terms to one written fresh, no reader can detect the difference, and no reader behavior depends on it. A rule nothing can check is an opinion, not a rule.

**Restricting what else the archive holds.** Considered and rejected. Both defined members are found by name, so nothing about locating them depends on what else is present, and a rule against extra members would make every archive produced by macOS Finder invalid while buying nothing. It would also mean a future signed container could not be opened by a reader written today.

**Identification by content.** The format reserves no magic bytes. EPUB, ODF, and ASiC place an uncompressed `mimetype` member first so that a fixed byte offset can be sniffed by `file(1)`, and that trick costs a fixed member order, a stored-uncompressed rule, a no-extra-fields rule, and a two-step invocation for anyone building a container by hand. Identification by opening the archive is sufficient for the format's own purposes, and the simplicity is worth more than the magic rule.
