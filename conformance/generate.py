#!/usr/bin/env python3
"""Generate the Slipcase conformance corpus described by manifest.toml.

Every container is built here rather than committed as a blob, so the corpus is
reviewable as source and reproducible byte for byte. Nothing is random and every
timestamp is fixed, so regenerating an unchanged case produces an identical file.

The archives are written by the small ZIP writer below rather than by the
standard library. zipfile cannot produce several of the cases the corpus needs:
duplicate member names, a local file header that disagrees with the central
directory, a CP437 name with general purpose bit 11 clear, or an entry that is
not a regular file.

Usage:
    python3 generate.py [--out DIR] [--list]

Requires Python 3.11 or later for tomllib.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys
import tomllib
import zipfile
import zlib

HERE = pathlib.Path(__file__).parent
MANIFEST = HERE / "manifest.toml"

FLYLEAF_NAME = "slipcase.flyleaf.toml"
FLYLEAF_NAME_1_0 = "slipcase.metadata.toml"
CONTENT = b"%PDF-1.4\n% slipcase conformance corpus content file\n"

# A fixed MS-DOS timestamp: 2026-08-20 12:00:00. Reproducibility over realism.
DOS_TIME = (12 << 11) | (0 << 5) | 0
DOS_DATE = ((2026 - 1980) << 9) | (8 << 5) | 20

STORED, DEFLATED = 0, 8

FLAG_ENCRYPTED = 0x0001
FLAG_DATA_DESCRIPTOR = 0x0008
FLAG_UTF8 = 0x0800

MODE_REGULAR = 0o100644
MODE_DIRECTORY = 0o040755
MODE_SYMLINK = 0o120777
MODE_FIFO = 0o010644
MODE_SETUID_REGULAR = 0o104755

ZIP_PASSWORD = b"conformance"

SIG_LOCAL = 0x04034B50
SIG_DESCRIPTOR = 0x08074B50
SIG_CENTRAL = 0x02014B50
SIG_EOCD = 0x06054B50
SIG_ZIP64_EOCD = 0x06064B50
SIG_ZIP64_LOCATOR = 0x07064B50


# --------------------------------------------------------------------------
# ZipCrypto, for the encryption cases
# --------------------------------------------------------------------------

CRC_TABLE = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if _c & 1 else 0)
    CRC_TABLE.append(_c)


class ZipCrypto:
    """The legacy PKWARE stream cipher. Weak by design and adequate for fixtures."""

    def __init__(self, password: bytes):
        self.keys = [0x12345678, 0x23456789, 0x34567890]
        for byte in password:
            self._update(byte)

    def _update(self, byte: int) -> None:
        k0, k1, k2 = self.keys
        k0 = (k0 >> 8) ^ CRC_TABLE[(k0 ^ byte) & 0xFF]
        k1 = (k1 + (k0 & 0xFF)) & 0xFFFFFFFF
        k1 = (k1 * 134775813 + 1) & 0xFFFFFFFF
        k2 = (k2 >> 8) ^ CRC_TABLE[(k2 ^ (k1 >> 24)) & 0xFF]
        self.keys = [k0, k1, k2]

    def _keystream_byte(self) -> int:
        temp = (self.keys[2] | 2) & 0xFFFF
        return ((temp * (temp ^ 1)) >> 8) & 0xFF

    def encrypt(self, data: bytes) -> bytes:
        out = bytearray()
        for byte in data:
            out.append(byte ^ self._keystream_byte())
            self._update(byte)
        return bytes(out)


def encrypt_member(data: bytes, crc: int) -> bytes:
    """Prefix the 12-byte encryption header and encrypt, as ZIP specifies."""
    cipher = ZipCrypto(ZIP_PASSWORD)
    header = bytes(range(11)) + bytes([(crc >> 24) & 0xFF])
    return cipher.encrypt(header + data)


# --------------------------------------------------------------------------
# ZIP writing
# --------------------------------------------------------------------------


class Entry:
    """One archive member, with full control over how it is recorded.

    `name` as str is encoded UTF-8, setting general purpose bit 11 when it is not
    pure ASCII. As bytes it is written raw and the caller owns the flag, which is
    how the CP437 cases are built.

    `local_name` overrides the name recorded in the local file header only, so
    the two records can be made to disagree.
    """

    def __init__(
        self,
        name: str | bytes,
        data: bytes = b"",
        *,
        method: int = STORED,
        flags: int = 0,
        mode: int = MODE_REGULAR,
        local_name: str | bytes | None = None,
        extra: bytes = b"",
        encrypt: bool = False,
        dos_time: int = DOS_TIME,
        dos_date: int = DOS_DATE,
        made_by: int = 0x031E,
        external: int | None = None,
    ):
        # Who wrote the archive, and what it recorded about the file. Both are
        # per entry rather than per archive because the only case that needs
        # them needs them to disagree with every other case: an MS-DOS creator
        # records no Unix mode at all, and `external` is then a DOS attribute
        # byte rather than a mode shifted into the high half.
        self.made_by = made_by
        self.external = external
        self.name, name_flag = self._encode(name)
        self.local_name = self._encode(local_name)[0] if local_name is not None else self.name
        self.data = data
        self.method = method
        self.flags = flags | name_flag
        self.mode = mode
        self.extra = extra
        self.dos_time = dos_time
        self.dos_date = dos_date

        self.crc = zlib.crc32(data) & 0xFFFFFFFF
        self.uncompressed_size = len(data)

        if method == DEFLATED:
            compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
            body = compressor.compress(data) + compressor.flush()
        else:
            body = data

        if encrypt:
            body = encrypt_member(body, self.crc)
            self.flags |= FLAG_ENCRYPTED

        self.body = body
        self.compressed_size = len(body)

    @staticmethod
    def _encode(name: str | bytes) -> tuple[bytes, int]:
        if isinstance(name, bytes):
            return name, 0
        encoded = name.encode("utf-8")
        return encoded, 0 if name.isascii() else FLAG_UTF8


def build_zip(entries: list[Entry], *, comment: bytes = b"", zip64: bool = False) -> bytes:
    """Assemble entries into an archive. Offsets are computed, nothing is checked."""
    out = bytearray()
    offsets: list[int] = []

    for entry in entries:
        offsets.append(len(out))
        streaming = bool(entry.flags & FLAG_DATA_DESCRIPTOR)
        out += struct.pack(
            "<IHHHHHIIIHH",
            SIG_LOCAL,
            20,
            entry.flags,
            entry.method,
            entry.dos_time,
            entry.dos_date,
            0 if streaming else entry.crc,
            0 if streaming else entry.compressed_size,
            0 if streaming else entry.uncompressed_size,
            len(entry.local_name),
            len(entry.extra),
        )
        out += entry.local_name + entry.extra + entry.body
        if streaming:
            out += struct.pack(
                "<IIII",
                SIG_DESCRIPTOR,
                entry.crc,
                entry.compressed_size,
                entry.uncompressed_size,
            )

    central_start = len(out)
    for entry, offset in zip(entries, offsets):
        out += struct.pack(
            "<IHHHHHHIIIHHHHHII",
            SIG_CENTRAL,
            entry.made_by,  # Unix, version 3.0, unless the entry says otherwise
            20,
            entry.flags,
            entry.method,
            entry.dos_time,
            entry.dos_date,
            entry.crc,
            entry.compressed_size,
            entry.uncompressed_size,
            len(entry.name),
            len(entry.extra),
            0,  # comment length
            0,  # disk number
            0,  # internal attributes
            entry.mode << 16 if entry.external is None else entry.external,
            offset,
        )
        out += entry.name + entry.extra
    central_size = len(out) - central_start

    if zip64:
        zip64_eocd_offset = len(out)
        out += struct.pack(
            "<IQHHIIQQQQ",
            SIG_ZIP64_EOCD,
            44,  # size of the remainder of this record
            0x031E,
            45,
            0,
            0,
            len(entries),
            len(entries),
            central_size,
            central_start,
        )
        out += struct.pack("<IIQI", SIG_ZIP64_LOCATOR, 0, zip64_eocd_offset, 1)
        out += struct.pack(
            "<IHHHHIIH",
            SIG_EOCD,
            0,
            0,
            0xFFFF,
            0xFFFF,
            0xFFFFFFFF,
            0xFFFFFFFF,
            len(comment),
        )
    else:
        out += struct.pack(
            "<IHHHHIIH",
            SIG_EOCD,
            0,
            0,
            len(entries),
            len(entries),
            central_size,
            central_start,
            len(comment),
        )
    out += comment
    return bytes(out)


# --------------------------------------------------------------------------
# Flyleaf and container helpers
# --------------------------------------------------------------------------


def toml_escape(value: str) -> str:
    """Escape a string for a TOML basic string, including control characters."""
    out = []
    for char in value:
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return "".join(out)


def flyleaf_toml(content_file: str = "report.pdf", version: str = "1.1", *, body: str = "") -> bytes:
    return (
        f'slipcase_version = "{toml_escape(version)}"\n'
        f"\n"
        f"[content]\n"
        f'file = "{toml_escape(content_file)}"\n'
        f"{body}"
    ).encode("utf-8")


def flyleaf_toml_1_0(content_file: str = "report.pdf") -> bytes:
    """A version 1.0 flyleaf: the key that version used, declaring that version."""
    return (
        'slipcase_version = "1.0"\n'
        "\n"
        "[payload]\n"
        f'file = "{toml_escape(content_file)}"\n'
    ).encode("utf-8")


def container(
    content_file: str = "report.pdf",
    member_name: str | bytes | None = None,
    *,
    version: str = "1.1",
    flyleaf: bytes | None = None,
    content: bytes = CONTENT,
    method: int = STORED,
    content_first: bool = False,
    extras: tuple[Entry, ...] = (),
    content_mode: int = MODE_REGULAR,
    content_flags: int = 0,
    content_local_name: str | bytes | None = None,
    flyleaf_flags: int = 0,
    encrypt_flyleaf: bool = False,
    encrypt_content: bool = False,
    **zip_options,
) -> bytes:
    """The shape almost every case starts from: one flyleaf, one content file."""
    if member_name is None:
        member_name = content_file
    if flyleaf is None:
        flyleaf = flyleaf_toml(content_file, version)

    flyleaf_entry = Entry(
        FLYLEAF_NAME, flyleaf, method=method, flags=flyleaf_flags, encrypt=encrypt_flyleaf
    )
    content_entry = Entry(
        member_name,
        content,
        method=method,
        flags=content_flags,
        mode=content_mode,
        local_name=content_local_name,
        encrypt=encrypt_content,
    )
    members = [content_entry, flyleaf_entry] if content_first else [flyleaf_entry, content_entry]
    return build_zip(members + list(extras), **zip_options)


CASES: dict[str, callable] = {}


def case(case_id: str):
    def register(fn):
        CASES[case_id] = fn
        return fn

    return register


# --------------------------------------------------------------------------
# Accept — structure and unconstrained properties
# --------------------------------------------------------------------------

case("accept/minimal")(lambda: container())
case("accept/deflated")(lambda: container(method=DEFLATED))
case("accept/order-content-file-first")(lambda: container(content_first=True))
case("accept/archive-comment")(lambda: container(comment=b"built by generate.py"))
case("accept/zip64")(lambda: container(zip64=True))
case("accept/timestamps-epoch")(lambda: _epoch())
case("accept/container-filename-not-convention")(lambda: container())


def _epoch() -> bytes:
    flyleaf = Entry(FLYLEAF_NAME, flyleaf_toml(), dos_time=0, dos_date=0)
    content = Entry("report.pdf", CONTENT, dos_time=0, dos_date=0)
    return build_zip([flyleaf, content])


@case("accept/extra-members-tool-artifacts")
def _() -> bytes:
    extras = (
        Entry("__MACOSX/", b"", mode=MODE_DIRECTORY),
        Entry("__MACOSX/._report.pdf", b"\x00\x05\x16\x07"),
        Entry(".DS_Store", b"\x00\x00\x00\x01Bud1"),
        Entry("desktop.ini", b"[.ShellClassInfo]\r\n"),
    )
    return container(extras=extras)


@case("accept/extra-member-arbitrary")
def _() -> bytes:
    return container(extras=(Entry("notes.txt", b"an unrelated member\n"),))


@case("accept/extra-member-resembling-content-file")
def _() -> bytes:
    decoy = Entry("report.pdf", b"the decoy, not the content file\n")
    return container("data.bin", extras=(decoy,))


@case("accept/data-descriptors")
def _() -> bytes:
    return container(content_flags=FLAG_DATA_DESCRIPTOR, flyleaf_flags=FLAG_DATA_DESCRIPTOR)


@case("accept/extra-fields")
def _() -> bytes:
    # 0x5455 extended timestamp (mod time only), then 0x7875 Unix uid/gid.
    timestamp = struct.pack("<HHBi", 0x5455, 5, 0x01, 1_776_000_000)
    unix_ids = struct.pack("<HHBBIBI", 0x7875, 11, 1, 4, 1000, 4, 1000)
    extra = timestamp + unix_ids
    flyleaf = Entry(FLYLEAF_NAME, flyleaf_toml(), extra=extra)
    content = Entry("report.pdf", CONTENT, extra=extra)
    return build_zip([flyleaf, content])


@case("accept/encrypted-extra-member")
def _() -> bytes:
    secret = Entry("secret.txt", b"encrypted, and nothing depends on it\n", encrypt=True)
    return container(extras=(secret,))


case("accept/encrypted-content-file")(lambda: container(encrypt_content=True))


@case("accept/version-1-0-names-as-extras")
def _() -> bytes:
    """A 1.1 container that also carries both of 1.0's names.

    An extra member named slipcase.metadata.toml and a [payload] table in the
    flyleaf, each naming decoy.pdf, which is not a member. SPEC Appendix C says
    the 1.0 names carry no meaning here: one is an additional member and the
    other an additional key. A reader that consults either finds a member that
    does not exist.
    """
    body = '\n[payload]\nfile = "decoy.pdf"\n'
    legacy = Entry(FLYLEAF_NAME_1_0, flyleaf_toml_1_0("decoy.pdf"))
    return container(flyleaf=flyleaf_toml(body=body), extras=(legacy,))


# --------------------------------------------------------------------------
# Accept — name decoding and matching
# --------------------------------------------------------------------------

case("accept/name-utf8-bit11-set")(lambda: container("rapport-financiér.pdf"))
case("accept/name-cjk-utf8")(lambda: container("報告書.pdf"))


@case("accept/name-cp437-bit11-clear")
def _() -> bytes:
    # U+00E9 is 0x82 in CP437. Bit 11 stays clear, so a reader must decode CP437.
    name = "caf\u00e9.txt"
    return container(name, name.encode("cp437"))


@case("accept/local-header-name-differs")
def _() -> bytes:
    # The central directory is authoritative, so this still matches content.file.
    return container("report.pdf", content_local_name="decoy.pdf")


# --------------------------------------------------------------------------
# Accept — flyleaf
# --------------------------------------------------------------------------


@case("accept/unknown-top-level-keys")
def _() -> bytes:
    text = (
        'slipcase_version = "1.1"\n'
        'title = "Q3 report"\n'
        'author = "D. Anderson"\n'
        'retention_class = "7y"\n\n'
        '[content]\nfile = "report.pdf"\n'
    )
    return container(flyleaf=text.encode())


@case("accept/unknown-nested-tables")
def _() -> bytes:
    body = '\n[provenance.system.source]\nname = "docmgmt"\nid = 4821\n'
    return container(flyleaf=flyleaf_toml(body=body))


@case("accept/unknown-keys-in-content-table")
def _() -> bytes:
    body = 'size = 44\nsha256 = "e3b0c44298fc1c149afbf4c8996fb924"\n'
    return container(flyleaf=flyleaf_toml(body=body))


@case("accept/flyleaf-key-order-reversed")
def _() -> bytes:
    # Dotted keys, not a table header: a bare key following [content] would belong
    # to that table, which is what reject/version-inside-content-table tests.
    text = 'content.file = "report.pdf"\nslipcase_version = "1.1"\n'
    return container(flyleaf=text.encode())


@case("accept/flyleaf-comments-and-blank-lines")
def _() -> bytes:
    text = (
        "# slipcase flyleaf\n\n"
        '  slipcase_version = "1.1"   # the specification version\n\n\n'
        "[content]\n"
        "  # the member this describes\n"
        '  file = "report.pdf"\n'
    )
    return container(flyleaf=text.encode())


@case("accept/flyleaf-crlf")
def _() -> bytes:
    return container(flyleaf=flyleaf_toml().replace(b"\n", b"\r\n"))


@case("accept/flyleaf-inline-table")
def _() -> bytes:
    text = 'slipcase_version = "1.1"\ncontent = { file = "report.pdf" }\n'
    return container(flyleaf=text.encode())


@case("accept/flyleaf-inline-table-multiline")
def _() -> bytes:
    # Newlines and a trailing comma inside an inline table: TOML 1.1.0, not 1.0.0.
    text = 'slipcase_version = "1.1"\n\ncontent = {\n    file = "report.pdf",\n}\n'
    return container(flyleaf=text.encode())


@case("accept/flyleaf-dotted-key")
def _() -> bytes:
    text = 'slipcase_version = "1.1"\ncontent.file = "report.pdf"\n'
    return container(flyleaf=text.encode())


case("accept/flyleaf-bom")(lambda: container(flyleaf=b"\xef\xbb\xbf" + flyleaf_toml()))


# --------------------------------------------------------------------------
# Accept — content file
# --------------------------------------------------------------------------

case("accept/content-file-zero-bytes")(lambda: container(content=b""))
case("accept/content-file-name-spaces")(lambda: container("Q3 report final.pdf"))
case("accept/content-file-name-double-extension")(lambda: container("archive.tar.gz"))
case("accept/content-file-name-no-extension")(lambda: container("README"))
case("accept/content-file-name-leading-dot")(lambda: container(".hidden"))
case("accept/content-file-name-dotdot-substring")(lambda: container("a..b"))
case("accept/content-file-name-windows-reserved")(lambda: container("CON"))
case("accept/content-file-name-trailing-dot")(lambda: container("report."))
case("accept/content-file-nested-container")(
    lambda: container("inner.pdf.slpc", content=container("inner.pdf"))
)
case("accept/content-file-name-bidi-override")(
    lambda: container("report\u202Efdp.exe")
)
case("accept/content-file-setuid-external-attributes")(
    lambda: container(content_mode=MODE_SETUID_REGULAR)
)


@case("accept/content-file-no-mode-recorded")
def _() -> bytes:
    """A conformant container written by an MS-DOS tool, so no member records a
    Unix mode.

    Every other `accept` case here is written by a Unix creator and records
    0644, which means the corpus had no container at all for the question *what
    does a reader say when the archive records no mode?* — and a reader has to
    answer it, because the answer is *nothing* and the obvious implementation
    answers 0664 instead.

    That is not hypothetical. A ZIP library's `unix_mode()` invents a mode for a
    DOS entry rather than returning nothing, so a reader that asks the library
    rather than reading the external attributes reports a mode that was never
    recorded — and an application that shows *this content file is executable* off
    the back of it says so about a file nobody marked. `excelano/slipcase-desktop`
    hit exactly that and reads the attributes directly because of it; its own
    walkthrough then found it had no fixture to check the fix against, and made
    one by hand on one platform. This is that container, in the place all three
    of its platforms can reach.

    Creator system 0 with version 2.0, which `unzip -Z` reports as `2.0 fat`,
    and external attributes 0x20 — the DOS archive bit, which is what a DOS tool
    sets and is not a mode in the high sixteen bits. Nothing here is
    non-conformant: §2.5 forbids rejecting a container over external attributes,
    and this case is about what a reader *reports*, which §3 leaves to it.
    """
    dos = {"made_by": 0x0014, "external": 0x20}
    return build_zip(
        [
            Entry(FLYLEAF_NAME, flyleaf_toml("report.pdf", "1.1"), **dos),
            Entry("report.pdf", CONTENT, **dos),
        ]
    )


@case("accept/flyleaf-high-compression-ratio")
def _() -> bytes:
    """A conformant container whose flyleaf inflates about 900 times.

    Deliberately small in absolute terms — 64 KiB — so that it sits under any
    bound SPEC 6 would lead an implementation to choose. It was a quarter of a
    megabyte for half a day, which was too close: measured 2026-08-27, a viewer
    that renders the document costs about 200 MB for that much metadata, so a
    bound set with that measurement in hand would have refused a container this
    corpus says must be accepted.

    What it catches is the naive reading of SPEC 6: a reader that refuses on the
    ratio rather than on the size refuses this, and this is a container it MUST
    NOT refuse. No fixture can test the bound itself, because the bound belongs
    to the implementation and no verdict here can depend on it.
    """
    filler = "# " + "0" * (64 * 1024) + "\n"
    return container(flyleaf=flyleaf_toml(body=filler), method=DEFLATED)


# --------------------------------------------------------------------------
# Reject — structure
# --------------------------------------------------------------------------

case("reject/not-a-zip")(lambda: b"This is not an archive. It is a sentence.\n")
case("reject/no-flyleaf")(lambda: build_zip([Entry("report.pdf", CONTENT)]))
case("reject/empty-archive")(lambda: build_zip([]))


@case("reject/no-content-file")
def _() -> bytes:
    return build_zip([Entry(FLYLEAF_NAME, flyleaf_toml())])


@case("reject/flyleaf-in-subdirectory")
def _() -> bytes:
    members = [
        Entry(f"sub/{FLYLEAF_NAME}", flyleaf_toml()),
        Entry("report.pdf", CONTENT),
    ]
    return build_zip(members)


@case("reject/duplicate-flyleaves")
def _() -> bytes:
    members = [
        Entry(FLYLEAF_NAME, flyleaf_toml()),
        Entry(FLYLEAF_NAME, flyleaf_toml("other.pdf")),
        Entry("report.pdf", CONTENT),
    ]
    return build_zip(members)


@case("reject/duplicate-flyleaves-agreeing")
def _() -> bytes:
    """Two byte-identical members named slipcase.flyleaf.toml.

    The sibling above disagrees about content.file, so a reader taking the last
    duplicate rejects it for naming an absent content file and a reader taking the
    first accepts it — the verdict follows whichever duplicate the library
    happened to return, and a last-wins reader is credited with a check it never
    ran. Here the two agree, so nothing downstream can fail and only counting
    the entries detects anything.
    """
    members = [
        Entry(FLYLEAF_NAME, flyleaf_toml()),
        Entry(FLYLEAF_NAME, flyleaf_toml()),
        Entry("report.pdf", CONTENT),
    ]
    return build_zip(members)


@case("reject/duplicate-content-files")
def _() -> bytes:
    members = [
        Entry(FLYLEAF_NAME, flyleaf_toml()),
        Entry("report.pdf", CONTENT),
        Entry("report.pdf", b"a second member with the same name\n"),
    ]
    return build_zip(members)


def _duplicate_content_file_zip(**zip_options) -> bytearray:
    """Three central directory entries, the last a duplicate content file.

    The shape every case below hides from one parser or the other: whether a
    reader sees the third entry is the whole question.
    """
    return bytearray(
        build_zip(
            [
                Entry(FLYLEAF_NAME, flyleaf_toml()),
                Entry("report.pdf", CONTENT),
                Entry("report.pdf", b"a second member with the same name\n"),
            ],
            **zip_options,
        )
    )


@case("reject/eocd-counts-disagree")
def _() -> bytes:
    """The end of central directory record's two counts do not match.

    Byte 8 is *entries on this disk* and byte 10 is *entries in total*. Every
    writer sets them equal; read apart they choose how many members a reader
    sees. Measured 2026-08-27 against the reference implementation, which read
    the total while its ZIP dependency read the count on this disk: declaring 3
    and 2 hid a duplicate content file behind a conformant verdict, and the content file
    served was the one the count never covered.
    """
    data = _duplicate_content_file_zip()
    at = data.rfind(b"PK\x05\x06")
    struct.pack_into("<H", data, at + 10, 2)
    return bytes(data)


@case("reject/eocd-not-at-end-of-file")
def _() -> bytes:
    """Two end of central directory records, the last one overrunning the file.

    The file carries its directory twice. The first record is well formed and
    names all three members, the duplicate included. The second is appended
    after it, names only the first two, and declares a comment that runs past
    the end of the file.

    A reader that takes the last signature it finds believes the second record,
    sees two members and no duplicate, and says conformant. A reader that checks
    the declared length before believing it rejects that record, falls back to
    the first, and finds three. Two readers, two answers, one file.

    Written this way after the first attempt did not discriminate: a single
    record with an overrunning comment is refused by the ZIP layer on its own,
    so the corpus agreed with itself whether or not a reader checked anything.
    Measured 2026-08-27.
    """
    full = _duplicate_content_file_zip()
    at = full.rfind(b"PK\x05\x06")
    cd_start = struct.unpack_from("<I", full, at + 16)[0]

    # The first two central headers, verbatim. Their recorded local-header
    # offsets are already absolute and stay correct wherever this copy sits.
    walk, kept = cd_start, []
    for _ in range(2):
        nlen, elen, clen = struct.unpack_from("<HHH", full, walk + 28)
        size = 46 + nlen + elen + clen
        kept.append(bytes(full[walk : walk + size]))
        walk += size
    short = b"".join(kept)

    out = bytearray(full)
    short_at = len(out)
    out += short
    out += struct.pack(
        "<IHHHHIIH",
        SIG_EOCD,
        0,
        0,
        2,              # two entries: the duplicate is not in this copy
        2,
        len(short),
        short_at,
        0xFFFF,         # a comment that is not there
    )
    return bytes(out)


@case("reject/eocd-split-across-disks")
def _() -> bytes:
    """The record says the archive is split across disks.

    SPEC 2.1 requires both disk numbers to be zero. Nothing produces a
    multi-disk container and no reader here could read one, so the choice is
    between saying so and reading whichever part happens to be in front of you.
    The three other fields §2.1 pins got cases when the rule was written; this
    one did not, which is why it is here.
    """
    data = _duplicate_content_file_zip()
    at = data.rfind(b"PK\x05\x06")
    struct.pack_into("<H", data, at + 4, 1)
    return bytes(data)


@case("reject/zip64-gate-mismatch")
def _() -> bytes:
    """Only the directory-size field carries the Zip64 sentinel.

    Which of the two records a reader believes depends on which fields it
    accepts as the signal to look for a Zip64 one. The plain record here is
    complete and consistent and simply understates the count; the Zip64 record
    beside it holds the truth, and the third member is visible only to a reader
    that goes and looks.
    """
    data = _duplicate_content_file_zip(zip64=True)
    z64 = data.find(struct.pack("<I", SIG_ZIP64_EOCD))
    real_offset = struct.unpack_from("<Q", data, z64 + 48)[0]
    at = data.rfind(b"PK\x05\x06")
    struct.pack_into("<H", data, at + 8, 2)
    struct.pack_into("<H", data, at + 10, 2)
    struct.pack_into("<I", data, at + 12, 0xFFFFFFFF)
    struct.pack_into("<I", data, at + 16, real_offset)
    return bytes(data)


@case("reject/archive-preceded-by-data")
def _() -> bytes:
    """A conformant container with a self-extracting-style stub in front of it.

    Every offset in the end of central directory record is now short by the
    length of the stub. Info-ZIP, Python's zipfile and the Rust zip crate all
    recover by measuring the discrepancy and adding it back, which is what SPEC
    2.1 declines to do: the offsets are taken from the start of the file.
    """
    return b"MZ" + b"\x00" * 4094 + container()


@case("reject/two-archives-in-one-file")
def _() -> bytes:
    """Two whole containers, one after the other, naming different content files.

    A reader scanning backwards finds the second archive's record, whose offsets
    are relative to where that archive begins and so land inside the first. A
    reader adjusting for that reads the second container; one parsing forwards
    reads the first. SPEC 2.1 refuses the file rather than picking, for the
    reason it refuses duplicate names rather than picking.
    """
    return container("first.pdf") + container("second.pdf")


# --------------------------------------------------------------------------
# Reject — name matching
# --------------------------------------------------------------------------


@case("reject/flyleaf-name-case-mismatch")
def _() -> bytes:
    members = [
        Entry("SLIPCASE.FLYLEAF.TOML", flyleaf_toml()),
        Entry("report.pdf", CONTENT),
    ]
    return build_zip(members)


case("reject/content-file-name-case-mismatch")(lambda: container("Report.pdf", "report.pdf"))


@case("reject/content-file-name-nfd-vs-nfc")
def _() -> bytes:
    # content.file carries U+00E9; the member name carries e + U+0301.
    return container("caf\u00e9.txt", "cafe\u0301.txt")


@case("reject/local-header-name-only-match")
def _() -> bytes:
    # Only the local header says report.pdf, and the local header does not decide.
    return container("report.pdf", "decoy.pdf", content_local_name="report.pdf")


# --------------------------------------------------------------------------
# Reject — flyleaf
# --------------------------------------------------------------------------

case("reject/flyleaf-empty")(lambda: container(flyleaf=b""))
case("reject/flyleaf-invalid-toml")(
    lambda: container(flyleaf=b'slipcase_version = "1.1\n\n[content]\nfile = "report.pdf"\n')
)
case("reject/flyleaf-not-utf8")(
    lambda: container(flyleaf=b'slipcase_version = "1.1"\n\n[content]\nfile = "caf\xe9.pdf"\n')
)
case("reject/missing-slipcase-version")(
    lambda: container(flyleaf=b'[content]\nfile = "report.pdf"\n')
)
case("reject/missing-content-file-key")(
    lambda: container(flyleaf=b'slipcase_version = "1.1"\n\n[content]\n')
)
case("reject/missing-content-table")(lambda: container(flyleaf=b'slipcase_version = "1.1"\n'))
case("reject/version-not-string")(
    lambda: container(flyleaf=b'slipcase_version = 1.1\n\n[content]\nfile = "report.pdf"\n')
)
case("reject/content-file-not-string")(
    lambda: container(flyleaf=b'slipcase_version = "1.1"\n\n[content]\nfile = 42\n')
)
case("reject/version-inside-content-table")(
    lambda: container(
        flyleaf=b'[content]\nfile = "report.pdf"\n\nslipcase_version = "1.1"\n'
    )
)
case("reject/content-not-a-table")(
    lambda: container(flyleaf=b'slipcase_version = "1.1"\ncontent = "report.pdf"\n')
)


# --------------------------------------------------------------------------
# Reject — content.file
# --------------------------------------------------------------------------
# Each carries a member matching the stated name wherever ZIP allows it, so the
# only violation is §2.3 itself.

case("reject/content-file-empty")(lambda: container("", "report.pdf"))
case("reject/content-file-dot")(lambda: container(".", "report.pdf"))
case("reject/content-file-dotdot")(lambda: container("..", "report.pdf"))
case("reject/content-file-forward-slash")(lambda: container("sub/report.pdf"))
case("reject/content-file-backslash")(lambda: container("sub\\report.pdf"))
case("reject/content-file-traversal")(lambda: container("../../etc/passwd"))
case("reject/content-file-colon-drive")(lambda: container("C:report.pdf"))
case("reject/content-file-colon-plain")(lambda: container("notes:draft.txt"))
case("reject/content-file-equals-flyleaf")(lambda: container(FLYLEAF_NAME, "report.pdf"))

# A parser may refuse the escape itself, in which case the container is rejected
# for a different reason and the verdict is unchanged.
case("reject/content-file-nul")(lambda: container("rep\u0000ort.pdf"))
case("reject/content-file-newline")(lambda: container("report\u000apdf"))
case("reject/content-file-del")(lambda: container("report\u007fpdf"))


# --------------------------------------------------------------------------
# Reject — content file entry type
# --------------------------------------------------------------------------

case("reject/content-file-symlink")(
    lambda: container(content=b"/etc/passwd", content_mode=MODE_SYMLINK)
)
case("reject/content-file-directory-entry")(
    lambda: container(content=b"", content_mode=MODE_DIRECTORY)
)
case("reject/content-file-fifo-entry")(lambda: container(content=b"", content_mode=MODE_FIFO))


# --------------------------------------------------------------------------
# Undetermined and out of scope
# --------------------------------------------------------------------------

case("undetermined/encrypted-flyleaf")(lambda: container(encrypt_flyleaf=True))
case("out-of-scope/version-2-0")(lambda: container(version="2.0"))
case("out-of-scope/version-malformed")(lambda: container(version="banana"))
case("out-of-scope/version-empty-string")(lambda: container(version=""))


@case("out-of-scope/version-1-0")
def _() -> bytes:
    """A conformant 1.0 container, as SPEC Appendix C describes one.

    The declaration is out of this version's scope by SPEC 2.4, but reaching
    that verdict takes knowing 1.0's flyleaf name: a reader that knows only
    this version's finds no flyleaf at all and never reads the declaration.
    """
    return build_zip([Entry(FLYLEAF_NAME_1_0, flyleaf_toml_1_0()), Entry("report.pdf", CONTENT)])


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def load_manifest() -> list[dict]:
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)["case"]


def check_coverage(manifest: list[dict]) -> None:
    """The manifest and the generator must describe the same corpus."""
    declared = {entry["id"] for entry in manifest}
    built = set(CASES)
    missing = sorted(declared - built)
    extra = sorted(built - declared)
    problems = []
    if missing:
        problems.append("declared in the manifest with no builder:\n  " + "\n  ".join(missing))
    if extra:
        problems.append("built here but absent from the manifest:\n  " + "\n  ".join(extra))
    if problems:
        sys.exit("generate.py: " + "\n".join(problems))


# Flyleaves using TOML 1.1.0 syntax that the standard library cannot parse, since
# tomllib implements 1.0.0. Skipped by the self-check rather than passed silently.
NEEDS_TOML_11 = {"accept/flyleaf-inline-table-multiline"}


def check_cases(manifest: list[dict], out_dir: pathlib.Path) -> list[str]:
    """Re-read what was written and hold it to §2.2 and §2.1.

    A case declared conformant must actually be conformant. Checking only that
    content.file resolves is not enough: it misses a document whose
    slipcase_version was captured by a preceding table header, which is how
    accept/flyleaf-key-order-reversed shipped wrong: the half that was checked
    was fine.
    """
    problems = []
    for entry in manifest:
        case_id, verdict = entry["id"], entry["expect"]
        if verdict not in ("accept", "out-of-scope") or case_id in NEEDS_TOML_11:
            continue
        path = out_dir / entry.get("filename", f"{case_id}.slpc")
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.namelist()
                is_1_0 = FLYLEAF_NAME not in members
                flyleaf = archive.read(FLYLEAF_NAME_1_0 if is_1_0 else FLYLEAF_NAME)
        except Exception as error:
            problems.append(f"{case_id}: unreadable archive: {error}")
            continue
        if flyleaf.startswith(b"\xef\xbb\xbf"):
            flyleaf = flyleaf[3:]
        try:
            document = tomllib.loads(flyleaf.decode("utf-8"))
        except Exception as error:
            problems.append(f"{case_id}: flyleaf does not parse: {error}")
            continue
        if not isinstance(document.get("slipcase_version"), str):
            problems.append(
                f"{case_id}: no root slipcase_version (root keys: {sorted(document)})"
            )
        # A 1.0 case is held to 1.0's names; SPEC Appendix C says nothing else differs.
        table_name = "payload" if is_1_0 else "content"
        table = document.get(table_name)
        target = table.get("file") if isinstance(table, dict) else None
        if not isinstance(target, str):
            problems.append(f"{case_id}: {table_name}.file is not a string")
        elif target not in members:
            problems.append(f"{case_id}: {table_name}.file {target!r} names no member")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "cases")
    parser.add_argument("--list", action="store_true", help="list case ids and exit")
    args = parser.parse_args()

    manifest = load_manifest()
    check_coverage(manifest)

    if args.list:
        for entry in manifest:
            print(f"{entry['expect']:14} {entry['id']}")
        return 0

    counts: dict[str, int] = {}
    for entry in manifest:
        data = CASES[entry["id"]]()
        path = args.out / entry.get("filename", f"{entry['id']}.slpc")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        counts[entry["expect"]] = counts.get(entry["expect"], 0) + 1

    total = sum(counts.values())
    print(f"wrote {total} containers to {args.out}")
    for verdict in sorted(counts):
        print(f"  {verdict:14} {counts[verdict]}")

    problems = check_cases(manifest, args.out)
    if problems:
        print("\nself-check failed:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    skipped = len(NEEDS_TOML_11)
    print(f"self-check passed ({skipped} skipped, needing a TOML 1.1.0 parser)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
