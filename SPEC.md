# slipcase — Specification

**Version:** 1.0  
**Status:** final

A slipcase container is a ZIP archive that binds a single payload file to a metadata document describing it, so that the two travel as one file.

## 1. Terminology

The key words **MUST**, **MUST NOT**, and **MAY** are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in capitals.

**Container** — a ZIP archive conforming to §2.  
**Metadata member** — the archive member named `slipcase.metadata.toml`.  
**Payload** — the archive member named by the `payload.file` key.  
**Implementation** — a program that reads or writes containers.

Section 2 states properties of a container, each of which can be checked against a file. Section 3 states requirements on implementations. Some of those can be put to an implementation by handing it a container and reading what it reports; the rest govern what it then writes or displays, and can be checked only by watching it work.

## 2. The container

### 2.1 Structure

A container MUST be a ZIP archive containing:

- exactly one member named `slipcase.metadata.toml`, conforming to §2.2; and
- exactly one member whose name equals the value of `payload.file`, conforming to §2.3.

A container MAY contain any number of additional members. They have no defined meaning. A container is not made non-conformant by their presence, whatever their names.

Member names are taken from the central directory. Where a member's local file header records a different name, the central directory is authoritative.

The archive is located by scanning backwards from the end of the file for the end of central directory record. The offsets that record holds are taken from the start of the file, so a file whose central directory does not lie where they say is not a container. This excludes an archive preceded by other data, such as a self-extracting stub, and a file holding one archive after another. Some ZIP implementations read both by adjusting the recorded offsets against wherever the archive begins; a container needs no such adjustment.

That record MUST also end the file, its own comment included, and MUST describe a single-disk archive: the count of records on this disk and the count in total are equal, and both disk numbers are zero. Where a Zip64 end of central directory record is present, the two MUST agree about how many entries the directory holds and where it begins. Each of these is a field two readers can be made to read differently, and a file whose member list depends on which reader opened it is not a container whatever else it may be.

Names are decoded before they are compared: as UTF-8 where general purpose bit 11 is set, and as CP437 otherwise. Comparison is then exact over the decoded sequence of code points. It is case-sensitive, and no Unicode normalization is applied to either side. An implementation MUST apply the same decoding and the same comparison when matching `payload.file` against member names.

### 2.2 The metadata member

The metadata member MUST be a valid [TOML 1.1.0](https://toml.io/en/v1.1.0) document, encoded as UTF-8. Where the member is encrypted, this applies to its decrypted content.

The document MAY begin with a byte order mark (U+FEFF). An implementation MUST skip a leading byte order mark before parsing and MUST NOT treat its presence as an error.

A container whose metadata member cannot be read at all — because it is encrypted and the key is not held, or for any other reason — is **undetermined**: its conformance cannot be established from the file. This is not the same as non-conformance, and §2.5 continues to forbid rejecting a container on the grounds that a member is encrypted.

It MUST contain the following two keys, and MAY contain any others:

```toml
slipcase_version = "1.0"

[payload]
file = "report.pdf"
```

- **`slipcase_version`** — string. The version of this specification that the container conforms to. See §2.4.
- **`payload.file`** — string. The name of the payload member, subject to §2.3.

Additional keys are permitted at any depth. A container carrying keys not defined here, or not defined by any version of this specification, is conformant. This specification defines no other key and assigns no meaning to any key beyond the two above.

This specification defines no canonical TOML serialization, because TOML defines none. Two writers producing the same metadata will not necessarily produce identical bytes.

### 2.3 The payload

A container has exactly one payload. It MAY be of any type and any length, including zero.

`payload.file` MUST:

- be non-empty;
- not be `.` or `..`;
- not contain `/` (U+002F) or `\` (U+005C);
- not contain `:` (U+003A);
- not contain any character in the range U+0000 to U+001F, or U+007F;
- not equal `slipcase.metadata.toml`.

In short, `payload.file` is a plain filename and never a path.

Only the names `.` and `..` are excluded, not the sequence `..` wherever it occurs. `a..b` is a permitted name.

The payload member MUST be a regular file entry. Directory entries, symbolic links, and every other entry type a ZIP implementation can record are excluded.

A payload MAY itself be a container. This requires no special handling and has no defined meaning.

### 2.4 The version key

`slipcase_version` names the version of this specification, not the version of the payload and not the revision of this document. Editorial revisions — corrections, clarifications, added examples — do not change it. It changes only when what counts as a conformant container changes.

Conformance is relative to a version. This document states whether a container declaring `1.0` conforms to it and states nothing about one declaring any other value. A container declaring `2.0`, or a value naming no version at all, is outside this document's conformance question rather than failing it. This specification constrains the value's type and not its shape.

**The value implies no compatibility, at any level.** An implementation written against one version cannot assume it can read a container declaring a higher one, including one differing only in its minor component. The minor component indicates the size of a revision to a reader of this document; it is not a promise to a program.

### 2.5 Unconstrained properties

The following are stated so that an implementer does not assume a restriction that is not present. A container MUST NOT be rejected on any of these grounds:

- the order of members;
- the compression method of any member;
- timestamps, external attributes, or extra fields;
- encryption of either member, by ZIP's own mechanisms or otherwise;
- the presence of additional members of any name, including `__MACOSX/`, `.DS_Store`, and `desktop.ini`, subject to the uniqueness required by §2.1;
- the use of Zip64.

## 3. Implementation requirements

An implementation:

- MUST NOT depend on the order of members;
- MUST establish the uniqueness required by §2.1 by enumerating central directory entries, and MUST NOT rely on a name-keyed lookup that resolves duplicate names to a single entry;
- MUST locate the payload by `payload.file` alone — never by position, and never by the naming convention in Appendix B;
- MUST preserve keys in the metadata that it does not recognize, and MUST NOT reject a container because of them;
- MUST preserve members that it does not recognize when rewriting a container;
- MUST write only the payload, and the metadata member if it needs it, when extracting — other members MUST NOT be written to disk;
- MUST NOT replace an existing file when writing the payload, unless the caller has explicitly asked for replacement;
- MUST create the payload with the permissions a newly created file would ordinarily receive, and MUST NOT apply permission bits recorded in the archive;
- MUST reject a container whose `payload.file` violates §2.3, rather than sanitizing it;
- MUST render the Unicode bidirectional formatting characters (U+061C, U+200E–U+200F, U+202A–U+202E, U+2066–U+2069) in an escaped form when it displays `payload.file` or a member name, rather than applying them;
- MUST NOT report a container whose `slipcase_version` it does not recognize as conformant to a version it does recognize;
- MUST NOT report a container as conformant, or as non-conformant, when it cannot read the metadata member (§2.2).

The bidirectional requirement is one instance of a general obligation: a name is displayed and never interpreted. Where an implementation renders `payload.file` into a medium that parses what it is handed — markup in a graphical toolkit or a desktop notification, HTML in a generated report — the characters that medium reserves have to be neutralised there as well. That is not stated as a requirement because the medium belongs to the implementation rather than to this specification, and a conformance suite cannot observe it.

Several of these are security requirements. The one that is not stated here is in §6, because bounding what a reader spends is something it must do before it knows whether it is holding a container at all.

## 4. File extension and media type

The file extension is `.slpc`. The media type is `application/x.slipcase+zip`, provisional in the unregistered `x.` tree of [RFC 6838](https://www.rfc-editor.org/rfc/rfc6838).

Neither appears inside a container. A container is identified by opening it and finding a conformant metadata member; this specification reserves no magic bytes and defines no identification by content.

## 5. Out of scope for this version

This version defines no signature or attestation mechanism, no encryption of its own, no aggregation of multiple payloads, no checksum or fixity key, and no vocabulary of descriptive metadata keys. It takes no position on whether a container may be modified after it is written.

## 6. Security considerations

**Identifying a container is a parse of untrusted input.** A reader cannot know whether a file is a container without decompressing the metadata member and parsing it as TOML, and it must do that before anything about the file has been established. This is not the position of a general ZIP consumer, which chooses what to extract and may decline. Deflate can return a little over a thousand bytes for every byte it is given, before whatever the TOML parser then spends, and a reader invoked automatically — a scanner, an indexer, a shell extension asked for a preview — is invoked on whatever happens to be in the directory.

An implementation MUST bound the decompressed size of the metadata member, and the depth to which it parses that member, and MUST report a container exceeding either bound as undetermined rather than as non-conformant.

The size a central directory records for a member is not that bound. Nothing checks it against what the member inflates to, and mainstream ZIP implementations do not enforce it, so a directory entry declaring a hundred bytes may still yield two hundred megabytes. It is worth reading before inflating, because it refuses the ordinary case cheaply, but the bound has to be applied to the bytes as they arrive.

The bounds themselves are a matter for the implementation. A number fixed here would be wrong for a reader running on a phone and wrong again for one running over an archive, and the format has no way to know which it is. Undetermined is the verdict because §2.2 already gives that answer for a metadata member that cannot be read, and a reader answering non-conformant instead would be calling a large but legitimate container malformed on the strength of its own configuration.

**Undetermined can be arranged.** A container whose metadata member is encrypted is undetermined by §2.2, which follows from the format defining no encryption of its own and forbidding none. The consequence is worth stating plainly: a program treating undetermined as *skip* can be made to skip on purpose, while the payload sits in the same archive unencrypted and legible to anything that never consulted the metadata. Undetermined is a reason to look further, not a reason to stop.

**Nesting is not bounded.** §2.3 permits a container as its own payload and assigns the arrangement no meaning, and nothing in this specification limits how deep it may go. Anything that follows a payload into another container needs a depth limit of its own. A reader that does not recurse has nothing to do here.

**A member name is attacker-controlled text.** §2.3 constrains `payload.file` enough that it cannot express a path, and no further: every remaining name is one a writer was entitled to pack. It is still a string a person reads in order to decide whether to open something, which is what the display rule in §3 is for, and it is still a string that will become a filename on some filesystem whose rules this specification does not know. An implementation that cannot write the name it was given has a problem to report rather than a name to change.

## Appendix A. Example (non-normative)

A container holding `report.pdf`, built with standard tools:

```bash
cat > slipcase.metadata.toml <<'TOML'
slipcase_version = "1.0"

[payload]
file = "report.pdf"
TOML

zip report.pdf.slpc slipcase.metadata.toml report.pdf
```

`unzip report.pdf.slpc` recovers both members.

## Appendix B. Naming convention (non-normative)

By convention a container is named for its payload with `.slpc` appended: `foo.pdf.slpc` holds `foo.pdf`. This keeps the payload's own extension visible and survives payloads with double extensions or none at all.

It is a convention and nothing more. Nothing enforces it, a container may be named anything, and `payload.file` is the only authority on the payload's name.
