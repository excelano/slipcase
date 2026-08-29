# Media type registration

SPEC §4 names `application/x.slipcase+zip`, provisional in the unregistered `x.`
tree of [RFC 6838](https://www.rfc-editor.org/rfc/rfc6838). That tree is defined
for use inside a private or otherwise limited environment, and §3.4 says a type
meant for public distribution does not belong in it. Slipcase is going into two
application stores, so the type needs a registered name.

This file is the draft registration, filled in and ready to paste. It is not the
specification and amends nothing: SPEC §4 continues to name the `x.` type until
IANA answers, and the section headed *If it is accepted* below is what changes
when it does.

**The route is the vendor tree.** `application/vnd.excelano.slipcase+zip`, by
expert review, through the form at <https://www.iana.org/form/media-types>. It
costs nothing, goes to `media-types@iana.org` for a couple of weeks of public
discussion, and needs no standards body. The standards tree is not available
without one; the personal tree is for an individual rather than for a company's
format. Measured against the live registry on 2026-08-29: 1,172 vendor-tree
entries under `application` and 19 personal-tree, no entry matching `slipcase`
or `slpc`, and `+zip` is a registered structured syntax suffix ([RFC
6839](https://www.rfc-editor.org/rfc/rfc6839), registered 2012-11-27) carried by
34 application types, several of them vendor-tree. The name and the shape are
both free.

The form's fields are the RFC 6838 §5.6 template with three of the older RFC
4288 names still on it, preceded by two of its own for the submitter. What
follows is in the form's order, every field filled, so it is copied straight
across with nothing to compose at the keyboard. The block below is the only copy
— there is deliberately no second plain-text file to drift from it.

---

## The template

```text
Your Full Name:
   David M. Anderson

Your E-mail:
   hello@excelano.com

Type name:
   application

Subtype name:
   vnd.excelano.slipcase+zip

Required parameters:
   N/A

Optional parameters:
   N/A

Encoding considerations:
   binary. A container is a ZIP archive.

Security considerations:
   A slipcase container is a ZIP archive, so the security considerations of
   "application/zip" apply to it in full. RFC 6839 notes that a media type
   registered with a +zip suffix may have additional ones. The following are
   additional.

   Identifying a container is a parse of untrusted input. A consumer cannot
   know whether a file is a container without locating the archive's central
   directory, decompressing the member named "slipcase.metadata.toml", and
   parsing it as TOML, and it must do all of that before anything about the
   file has been established. This is not the position of a general ZIP
   consumer, which chooses what to extract and may decline. Deflate returns a
   little over a thousand bytes for every byte it is given, before whatever
   the TOML parser then spends, and a consumer invoked automatically (a
   scanner, an indexer, a shell extension asked for a preview) is invoked on
   whatever happens to be present.

   The specification therefore requires an implementation to bound the
   decompressed size of the metadata member, and the depth to which it parses
   that member, and to report a container exceeding either bound as
   undetermined rather than as non-conformant. The size the central directory
   records for a member is not that bound. Nothing checks that figure against
   what the member inflates to, and mainstream ZIP implementations do not
   enforce it, so a directory entry declaring a hundred bytes may still yield
   two hundred megabytes. The bound has to be applied to the bytes as they
   arrive.

   The payload is arbitrary. The format constrains neither its type nor its
   content nor its length, so the security considerations of whatever the
   payload turns out to be apply to the payload, and a container is a
   transport for them. A consumer that hands a payload to a system handler is
   invoking that handler on content that arrived from elsewhere, and should
   treat it with whatever care its platform's rules for downloaded content
   require.

   Two practices follow from that and are not requirements of this
   specification, which takes no position on what a consumer does with a
   payload once it has one. Where the host platform records that a file
   arrived from elsewhere, an implementation that extracts a payload can put
   the same record on the copy, so that the platform's own handling of
   downloaded content reaches the payload rather than stopping at the
   container. And where a consumer reports what it found rather than deciding
   for the user, what it reports should come from the container: the
   specification's requirement that an extracted payload not receive the
   archive's permission bits means a payload stored executable does not extract
   executable, which is a fact a consumer can state without guessing at the
   payload's type from its name.

   The metadata is unauthenticated. This version of the format defines no
   signature, attestation, checksum, or fixity mechanism. Nothing inside a
   container establishes who wrote it, or that its metadata describes its
   payload, and a consumer must not present the metadata as though something
   had.

   The payload's name cannot express a path. "payload.file" is required to be
   a plain filename: non-empty, not "." or "..", not equal to the metadata
   member's name, and containing no solidus, reverse solidus, colon, C0
   character, or DEL. An implementation is required to reject a container
   violating this rather than to sanitize the name, so that a container
   cannot direct a write outside the directory its caller chose. An
   implementation is separately required to create an extracted payload with
   the permissions a newly created file would ordinarily receive, and never
   to apply permission bits recorded in the archive, so that a container
   cannot make the file it extracts executable.

   A member name is attacker-controlled text that a person reads in order to
   decide whether to open something. The specification requires the Unicode
   bidirectional formatting characters (U+061C, U+200E-U+200F, U+202A-U+202E,
   U+2066-U+2069) to be displayed in an escaped form rather than applied, so
   that a name cannot be arranged to read as an extension it does not have.

   Undetermined can be arranged. The format defines no encryption of its own
   and forbids none, so a container whose metadata member is encrypted can be
   established neither as conformant nor as non-conformant. A program
   treating that verdict as a reason to skip the file can be made to skip on
   purpose, while the payload sits in the same archive unencrypted and
   legible to anything that never consulted the metadata. Undetermined is a
   reason to look further rather than a reason to stop.

   Nesting is not bounded. A payload may itself be a container, the
   arrangement carries no defined meaning, and nothing in the specification
   limits how deep it may go. An implementation that follows a payload into
   another container needs a depth limit of its own.

Interoperability considerations:
   A container is an ordinary ZIP archive, so a consumer that has never heard
   of the format can open one with any ZIP tool and recover both members.
   The relationship holds in one direction only. An archive preceded by other
   data, such as a self-extracting stub, and a file holding one archive after
   another, are both readable by many ZIP implementations and both excluded
   by the format, which requires the end of central directory record to end
   the file and its recorded offsets to be taken from the start of it.

   Member names are decoded before they are compared, as UTF-8 where general
   purpose bit 11 is set and as CP437 otherwise, and are then compared
   exactly over code points, case-sensitively and with no Unicode
   normalization applied to either side. An implementation applying a
   different rule can fail to find a payload that another implementation
   finds.

   The format defines no canonical TOML serialization, because TOML defines
   none. Two writers given the same metadata need not produce identical
   bytes, so comparing bytes is not a test of equivalence.

   The value of "slipcase_version" implies no compatibility at any level,
   including between values differing only in their minor component. An
   implementation written against one version cannot assume it can read a
   container declaring a higher one.

   A conformance corpus accompanies the specification, at
   <https://github.com/excelano/slipcase/tree/v1.0/conformance>. It gives an
   implementer a set of containers with recorded verdicts to check against.

Published specification:
   slipcase - Specification, version 1.0, final.
   <https://github.com/excelano/slipcase/blob/v1.0/SPEC.md>

   Dedicated to the public domain under CC0 1.0, so it may be implemented,
   quoted, or embedded by anyone.

Application Usage:
   Slipcase, a desktop application for Linux, macOS, and Windows that opens a
   container, presents its metadata as an editable tree, and hands the
   payload to the system handler registered for it.
   <https://github.com/excelano/slipcase-desktop>

   slpc, a Rust library that reads and writes containers.
   <https://github.com/excelano/slpc-rust>

   The list is not exhaustive.

Fragment identifier considerations:
   As specified for the +zip structured syntax suffix in RFC 6839. No
   fragment identifier syntax is defined for "application/zip", and this
   specification defines none of its own for this type.

Restrictions on usage:
   N/A

Provisional registrations:
   N/A. This is a vendor-tree registration; the field applies to the
   standards tree.

Additional Information:
   Deprecated alias names for this type:
      application/x.slipcase+zip, provisional in the unregistered x. tree of
      RFC 6838 section 3.4. It is what the specification and the released
      implementations named before this registration, and it is kept as an
      alias so that installations predating the registration continue to
      resolve.

   Magic number(s):
      None. The specification reserves no magic bytes and defines no
      identification by content. A container begins with the bytes any ZIP
      archive begins with, and is identified by opening the archive and
      finding a conformant metadata member.

   File extension(s):
      slpc

   Macintosh file type code(s):
      N/A. The Uniform Type Identifier is com.excelano.slipcase, which
      conforms to public.zip-archive and public.data.

   Object Identifiers:
      N/A

Intended usage:
   COMMON

Other Information & Comments:
   The extension and the media type both live outside the container and
   neither appears inside one. This is deliberate: a container carries no
   member recording its own type, and a reader establishes what it is holding
   by reading the metadata member rather than by trusting a name.

Contact Person:
   David M. Anderson <hello@excelano.com>

Author:
   David M. Anderson

Change controller:
   Excelano
```

---

## What had to be settled first, and how each was

**Nothing is outstanding: the template above is ready to send.** The heading no
longer counts them, because the count in it would have been wrong twice by now.
Each entry is kept struck rather than deleted, because what a question was before
it was answered is the part a later reader needs.

~~**The contact address, which the registry publishes and keeps.**~~
**Settled: `hello@excelano.com`.** The entry carries a name and an address
permanently, lightly obfuscated on IANA's own pages and not at all in the
mailing list archives, and it outlives whoever held the mailbox, so a role
address Excelano controls beats a personal one. `hello@excelano.com` is the only
one the company publishes — `excelano.com` carries it in three places, including
as the contact for legal and privacy questions on the page both stores link to
— so it is an address already demonstrated to deliver rather than one invented
for this form.

~~**`SPEC.md` still says `Status: draft`.**~~ **Settled: 1.0 is final as of
2026-08-29.** A vendor-tree registration does not require a published
specification at all, let alone a finished one, so this was never a blocker. It
was what the reviewer would see first, and the answer to *why draft* would have
had to be that the format is in fact settled — which belongs in the document
rather than in a reply to a review. `DESIGN.md` §3.2 records why, and
`CONTRIBUTING.md`'s version rule has flipped to the half that was waiting: a
change to what counts as a conformant container now moves `slipcase_version`,
and the corpus is what decides which changes those are.

~~**Whether the security section says enough about handing a payload to a system
handler.**~~ **Settled 2026-08-29, and the section now says it.** Both of the
questions this was waiting on were taken: an executable payload is reported and
not gated, and the extracted copy is not executable because the specification
forbids applying the archive's permission bits; and a container that arrived
from elsewhere has that fact carried onto the payload where the platform records
such a thing. Neither is a requirement this specification imposes, so both are
written as practices rather than as rules, which is what keeps the registration
from claiming more than §3 says. `excelano/slipcase-desktop`'s `DESIGN.md` §5
holds the reasoning and its `CHECKLIST.md` holds the measurements on all three
platforms.

## If it is accepted

The type string appears in no container, which is what keeps this small: nothing
already written has to be rewritten, and only the platform databases and the
documents change. It is not, however, the six places it looks like from SPEC §4.
Measured on 2026-08-29, `application/x.slipcase+zip` appears in 18 files across
the two repositories, and the Linux icon and MIME package are *named* for the
type as well, so the rename reaches filenames and not only contents.

In `excelano/slipcase`: SPEC §4 names the registered type and records
`application/x.slipcase+zip` as the name it supersedes, and `DESIGN.md` gains the
matching entry. `CONTRIBUTING.md` requires a rule and its reasoning to travel
together, and DESIGN records no reasoning for §4 at all today, which is a gap
this is the occasion to close rather than a new one to open.

In `excelano/slipcase-desktop`, the parts that are code:
`packaging/linux/application-x.slipcase+zip.xml` is renamed for the new type and
carries `<alias type="application/x.slipcase+zip"/>`, and `install.sh` and
`uninstall.sh` follow it, along with the icon file that shares its name;
`packaging/macos/Info.plist.in` updates the `public.mime-type` tag;
`packaging/windows/install.ps1` and `uninstall.ps1` update `$contentType`; and
`AppxManifest.xml.in` updates the `ContentType` attribute. The rest are prose in
`README.md`, `DESIGN.md`, `CHECKLIST.md`, the three handovers, and the Linux CI
workflow, which asserts the type and will fail until it is changed.

Upgrading an installed 0.1.0 needs more than the alias, on two platforms.
Installing the renamed XML beside the old one registers both as real types
rather than one as an alias, so the old package file has to be removed;
`uninstall.sh` already names it, and the install path should delete it before
running `update-mime-database`. On Windows the old key under
`HKCR\MIME\Database\Content Type\` outlives the upgrade unless something
removes it, and a stale entry there maps `.slpc` to a type nothing claims.
Neither is hard, and neither happens by itself.

Not worth doing yet, and recorded here so the question is not asked twice.
Contributing the type to freedesktop's `shared-mime-info` would let a Linux
desktop recognise a container with Slipcase not installed, but upstream wants a
format with users and one application at 0.1.0 does not have them. PRONOM, the
UK National Archives' preservation registry, issues an identifier and takes
submissions, and matters when somebody is archiving containers. Neither of those
nor a `file(1)` magic pattern can identify a container by content, because the
specification reserves no magic bytes on purpose.
