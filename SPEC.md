# slipcase — Specification

**Version:** 1.0
**Status:** draft

A slipcase container is a ZIP archive that binds a single payload file to a metadata document describing it, so that the two travel as one file.

## 1. Terminology

The key words **MUST**, **MUST NOT**, and **MAY** are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in capitals.

**Container** — a ZIP archive conforming to §2.
**Metadata member** — the archive member named `slipcase.metadata.toml`.
**Payload** — the archive member named by the `payload.file` key.
**Implementation** — a program that reads or writes containers.

Section 2 states properties of a container, each of which can be checked against a file. Section 3 states requirements on implementations, which cannot.

## 2. The container

### 2.1 Structure

A container MUST be a ZIP archive containing:

- exactly one member named `slipcase.metadata.toml`, conforming to §2.2; and
- exactly one member whose name equals the value of `payload.file`, conforming to §2.3.

A container MAY contain any number of additional members. They have no defined meaning. A container is not made non-conformant by their presence, whatever their names.

Member names are taken from the central directory. Where a member's local file header records a different name, the central directory is authoritative.

Names are decoded before they are compared: as UTF-8 where general purpose bit 11 is set, and as CP437 otherwise. Comparison is then exact over the decoded sequence of code points. It is case-sensitive, and no Unicode normalization is applied to either side. An implementation MUST apply the same decoding and the same comparison when matching `payload.file` against member names.

*Non-normative:* a writer taking a payload name from a filesystem should know that macOS returns names in NFD where most other sources produce NFC. The two are different sequences and will not match.

### 2.2 The metadata member

The metadata member MUST be a valid [TOML 1.1.0](https://toml.io/en/v1.1.0) document, encoded as UTF-8. Where the member is encrypted, this applies to its decrypted content.

The document MAY begin with a byte order mark (U+FEFF). TOML does not address one and editors on some platforms emit it by default. An implementation MUST skip a leading byte order mark before parsing and MUST NOT treat its presence as an error.

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

In short, `payload.file` is a plain filename and never a path. A payload is one file, not a location in a tree, and a name that cannot express a path cannot express a traversal. The colon is excluded because on some platforms a name containing one is treated as rooted, and joining it to a destination directory discards the destination.

Only the names `.` and `..` are excluded, not the sequence `..` wherever it occurs. `a..b` is a permitted name.

The payload member MUST be a regular file entry. Directory entries, symbolic links, and every other entry type a ZIP implementation can record are excluded.

*Non-normative:* a permitted name is not always a writable one. `CON`, `NUL`, `COM1`, and names ending in a space or a dot are legal here and cannot be created on Windows. These rules govern what a container may say, not what a filesystem will accept.

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
- MUST locate the payload by `payload.file` alone — never by position, and never by the naming convention in Appendix B;
- MUST preserve keys in the metadata that it does not recognize, and MUST NOT reject a container because of them;
- MUST preserve members that it does not recognize when rewriting a container;
- MUST write only the payload, and the metadata member if it needs it, when extracting — other members MUST NOT be written to disk;
- MUST reject a container whose `payload.file` violates §2.3, rather than sanitizing it;
- MUST NOT assume it can read a container whose `slipcase_version` it does not recognize;
- MUST NOT report a container as conformant, or as non-conformant, when it cannot read the metadata member (§2.2).

Nothing else here is a security requirement. Resource limits when parsing ZIP or TOML are the concern of whatever libraries an implementation uses, and apply equally to every consumer of those formats.

## 4. File extension and media type

The file extension is `.slpc`. The media type is `application/x.slipcase+zip`, provisional in the unregistered `x.` tree of [RFC 6838](https://www.rfc-editor.org/rfc/rfc6838).

Neither appears inside a container. A container is identified by opening it and finding a conformant metadata member; this specification reserves no magic bytes and defines no identification by content.

## 5. Out of scope for this version

This version defines no signature or attestation mechanism, no encryption of its own, no aggregation of multiple payloads, no checksum or fixity key, and no vocabulary of descriptive metadata keys. It takes no position on whether a container may be modified after it is written.

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
