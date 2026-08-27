#!/usr/bin/env python3
"""Generate the slipcase conformance corpus described by manifest.toml.

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

META_NAME = "slipcase.metadata.toml"
PAYLOAD = b"%PDF-1.4\n% slipcase conformance corpus payload\n"

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
    ):
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
            0x031E,  # made by Unix, version 3.0
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
            entry.mode << 16,
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
# Metadata and container helpers
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


def meta_toml(payload_file: str = "report.pdf", version: str = "1.0", *, body: str = "") -> bytes:
    return (
        f'slipcase_version = "{toml_escape(version)}"\n'
        f"\n"
        f"[payload]\n"
        f'file = "{toml_escape(payload_file)}"\n'
        f"{body}"
    ).encode("utf-8")


def container(
    payload_file: str = "report.pdf",
    member_name: str | bytes | None = None,
    *,
    version: str = "1.0",
    metadata: bytes | None = None,
    payload: bytes = PAYLOAD,
    method: int = STORED,
    payload_first: bool = False,
    extras: tuple[Entry, ...] = (),
    payload_mode: int = MODE_REGULAR,
    payload_flags: int = 0,
    payload_local_name: str | bytes | None = None,
    meta_flags: int = 0,
    encrypt_metadata: bool = False,
    encrypt_payload: bool = False,
    **zip_options,
) -> bytes:
    """The shape almost every case starts from: one metadata member, one payload."""
    if member_name is None:
        member_name = payload_file
    if metadata is None:
        metadata = meta_toml(payload_file, version)

    meta_entry = Entry(
        META_NAME, metadata, method=method, flags=meta_flags, encrypt=encrypt_metadata
    )
    payload_entry = Entry(
        member_name,
        payload,
        method=method,
        flags=payload_flags,
        mode=payload_mode,
        local_name=payload_local_name,
        encrypt=encrypt_payload,
    )
    members = [payload_entry, meta_entry] if payload_first else [meta_entry, payload_entry]
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
case("accept/order-payload-first")(lambda: container(payload_first=True))
case("accept/archive-comment")(lambda: container(comment=b"built by generate.py"))
case("accept/zip64")(lambda: container(zip64=True))
case("accept/timestamps-epoch")(lambda: _epoch())
case("accept/container-filename-not-convention")(lambda: container())


def _epoch() -> bytes:
    meta = Entry(META_NAME, meta_toml(), dos_time=0, dos_date=0)
    payload = Entry("report.pdf", PAYLOAD, dos_time=0, dos_date=0)
    return build_zip([meta, payload])


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


@case("accept/extra-member-resembling-payload")
def _() -> bytes:
    decoy = Entry("report.pdf", b"the decoy, not the payload\n")
    return container("data.bin", extras=(decoy,))


@case("accept/data-descriptors")
def _() -> bytes:
    return container(payload_flags=FLAG_DATA_DESCRIPTOR, meta_flags=FLAG_DATA_DESCRIPTOR)


@case("accept/extra-fields")
def _() -> bytes:
    # 0x5455 extended timestamp (mod time only), then 0x7875 Unix uid/gid.
    timestamp = struct.pack("<HHBi", 0x5455, 5, 0x01, 1_776_000_000)
    unix_ids = struct.pack("<HHBBIBI", 0x7875, 11, 1, 4, 1000, 4, 1000)
    extra = timestamp + unix_ids
    meta = Entry(META_NAME, meta_toml(), extra=extra)
    payload = Entry("report.pdf", PAYLOAD, extra=extra)
    return build_zip([meta, payload])


@case("accept/encrypted-extra-member")
def _() -> bytes:
    secret = Entry("secret.txt", b"encrypted, and nothing depends on it\n", encrypt=True)
    return container(extras=(secret,))


case("accept/encrypted-payload")(lambda: container(encrypt_payload=True))


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
    # The central directory is authoritative, so this still matches payload.file.
    return container("report.pdf", payload_local_name="decoy.pdf")


# --------------------------------------------------------------------------
# Accept — metadata
# --------------------------------------------------------------------------


@case("accept/unknown-top-level-keys")
def _() -> bytes:
    text = (
        'slipcase_version = "1.0"\n'
        'title = "Q3 report"\n'
        'author = "D. Anderson"\n'
        'retention_class = "7y"\n\n'
        '[payload]\nfile = "report.pdf"\n'
    )
    return container(metadata=text.encode())


@case("accept/unknown-nested-tables")
def _() -> bytes:
    body = '\n[provenance.system.source]\nname = "docmgmt"\nid = 4821\n'
    return container(metadata=meta_toml(body=body))


@case("accept/unknown-keys-in-payload-table")
def _() -> bytes:
    body = 'size = 44\nsha256 = "e3b0c44298fc1c149afbf4c8996fb924"\n'
    return container(metadata=meta_toml(body=body))


@case("accept/metadata-key-order-reversed")
def _() -> bytes:
    # Dotted keys, not a table header: a bare key following [payload] would belong
    # to that table, which is what reject/version-inside-payload-table tests.
    text = 'payload.file = "report.pdf"\nslipcase_version = "1.0"\n'
    return container(metadata=text.encode())


@case("accept/metadata-comments-and-blank-lines")
def _() -> bytes:
    text = (
        "# slipcase metadata\n\n"
        '  slipcase_version = "1.0"   # the specification version\n\n\n'
        "[payload]\n"
        "  # the member this describes\n"
        '  file = "report.pdf"\n'
    )
    return container(metadata=text.encode())


@case("accept/metadata-crlf")
def _() -> bytes:
    return container(metadata=meta_toml().replace(b"\n", b"\r\n"))


@case("accept/metadata-inline-table")
def _() -> bytes:
    text = 'slipcase_version = "1.0"\npayload = { file = "report.pdf" }\n'
    return container(metadata=text.encode())


@case("accept/metadata-inline-table-multiline")
def _() -> bytes:
    # Newlines and a trailing comma inside an inline table: TOML 1.1.0, not 1.0.0.
    text = 'slipcase_version = "1.0"\n\npayload = {\n    file = "report.pdf",\n}\n'
    return container(metadata=text.encode())


@case("accept/metadata-dotted-key")
def _() -> bytes:
    text = 'slipcase_version = "1.0"\npayload.file = "report.pdf"\n'
    return container(metadata=text.encode())


case("accept/metadata-bom")(lambda: container(metadata=b"\xef\xbb\xbf" + meta_toml()))


# --------------------------------------------------------------------------
# Accept — payload
# --------------------------------------------------------------------------

case("accept/payload-zero-bytes")(lambda: container(payload=b""))
case("accept/payload-name-spaces")(lambda: container("Q3 report final.pdf"))
case("accept/payload-name-double-extension")(lambda: container("archive.tar.gz"))
case("accept/payload-name-no-extension")(lambda: container("README"))
case("accept/payload-name-leading-dot")(lambda: container(".hidden"))
case("accept/payload-name-dotdot-substring")(lambda: container("a..b"))
case("accept/payload-name-windows-reserved")(lambda: container("CON"))
case("accept/payload-name-trailing-dot")(lambda: container("report."))
case("accept/payload-nested-container")(
    lambda: container("inner.pdf.slpc", payload=container("inner.pdf"))
)
case("accept/payload-name-bidi-override")(
    lambda: container("report\u202Efdp.exe")
)
case("accept/payload-setuid-external-attributes")(
    lambda: container(payload_mode=MODE_SETUID_REGULAR)
)


@case("accept/metadata-high-compression-ratio")
def _() -> bytes:
    """A conformant container whose metadata member inflates about 900 times.

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
    return container(metadata=meta_toml(body=filler), method=DEFLATED)


# --------------------------------------------------------------------------
# Reject — structure
# --------------------------------------------------------------------------

case("reject/not-a-zip")(lambda: b"This is not an archive. It is a sentence.\n")
case("reject/no-metadata-member")(lambda: build_zip([Entry("report.pdf", PAYLOAD)]))
case("reject/empty-archive")(lambda: build_zip([]))


@case("reject/no-payload-member")
def _() -> bytes:
    return build_zip([Entry(META_NAME, meta_toml())])


@case("reject/metadata-in-subdirectory")
def _() -> bytes:
    members = [
        Entry(f"sub/{META_NAME}", meta_toml()),
        Entry("report.pdf", PAYLOAD),
    ]
    return build_zip(members)


@case("reject/duplicate-metadata-members")
def _() -> bytes:
    members = [
        Entry(META_NAME, meta_toml()),
        Entry(META_NAME, meta_toml("other.pdf")),
        Entry("report.pdf", PAYLOAD),
    ]
    return build_zip(members)


@case("reject/duplicate-metadata-members-agreeing")
def _() -> bytes:
    """Two byte-identical members named slipcase.metadata.toml.

    The sibling above disagrees about payload.file, so a reader taking the last
    duplicate rejects it for naming an absent payload and a reader taking the
    first accepts it — the verdict follows whichever duplicate the library
    happened to return, and a last-wins reader is credited with a check it never
    ran. Here the two agree, so nothing downstream can fail and only counting
    the entries detects anything.
    """
    members = [
        Entry(META_NAME, meta_toml()),
        Entry(META_NAME, meta_toml()),
        Entry("report.pdf", PAYLOAD),
    ]
    return build_zip(members)


@case("reject/duplicate-payload-members")
def _() -> bytes:
    members = [
        Entry(META_NAME, meta_toml()),
        Entry("report.pdf", PAYLOAD),
        Entry("report.pdf", b"a second member with the same name\n"),
    ]
    return build_zip(members)


def _duplicate_payload_zip(**zip_options) -> bytearray:
    """Three central directory entries, the last a duplicate payload.

    The shape every case below hides from one parser or the other: whether a
    reader sees the third entry is the whole question.
    """
    return bytearray(
        build_zip(
            [
                Entry(META_NAME, meta_toml()),
                Entry("report.pdf", PAYLOAD),
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
    and 2 hid a duplicate payload behind a conformant verdict, and the payload
    served was the one the count never covered.
    """
    data = _duplicate_payload_zip()
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
    full = _duplicate_payload_zip()
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
    data = _duplicate_payload_zip()
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
    data = _duplicate_payload_zip(zip64=True)
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
    """Two whole containers, one after the other, naming different payloads.

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


@case("reject/metadata-name-case-mismatch")
def _() -> bytes:
    members = [
        Entry("SLIPCASE.METADATA.TOML", meta_toml()),
        Entry("report.pdf", PAYLOAD),
    ]
    return build_zip(members)


case("reject/payload-name-case-mismatch")(lambda: container("Report.pdf", "report.pdf"))


@case("reject/payload-name-nfd-vs-nfc")
def _() -> bytes:
    # payload.file carries U+00E9; the member name carries e + U+0301.
    return container("caf\u00e9.txt", "cafe\u0301.txt")


@case("reject/local-header-name-only-match")
def _() -> bytes:
    # Only the local header says report.pdf, and the local header does not decide.
    return container("report.pdf", "decoy.pdf", payload_local_name="report.pdf")


# --------------------------------------------------------------------------
# Reject — metadata
# --------------------------------------------------------------------------

case("reject/metadata-empty")(lambda: container(metadata=b""))
case("reject/metadata-invalid-toml")(
    lambda: container(metadata=b'slipcase_version = "1.0\n\n[payload]\nfile = "report.pdf"\n')
)
case("reject/metadata-not-utf8")(
    lambda: container(metadata=b'slipcase_version = "1.0"\n\n[payload]\nfile = "caf\xe9.pdf"\n')
)
case("reject/missing-slipcase-version")(
    lambda: container(metadata=b'[payload]\nfile = "report.pdf"\n')
)
case("reject/missing-payload-file")(
    lambda: container(metadata=b'slipcase_version = "1.0"\n\n[payload]\n')
)
case("reject/missing-payload-table")(lambda: container(metadata=b'slipcase_version = "1.0"\n'))
case("reject/version-not-string")(
    lambda: container(metadata=b'slipcase_version = 1.0\n\n[payload]\nfile = "report.pdf"\n')
)
case("reject/payload-file-not-string")(
    lambda: container(metadata=b'slipcase_version = "1.0"\n\n[payload]\nfile = 42\n')
)
case("reject/version-inside-payload-table")(
    lambda: container(
        metadata=b'[payload]\nfile = "report.pdf"\n\nslipcase_version = "1.0"\n'
    )
)
case("reject/payload-not-a-table")(
    lambda: container(metadata=b'slipcase_version = "1.0"\npayload = "report.pdf"\n')
)


# --------------------------------------------------------------------------
# Reject — payload.file
# --------------------------------------------------------------------------
# Each carries a member matching the stated name wherever ZIP allows it, so the
# only violation is §2.3 itself.

case("reject/payload-file-empty")(lambda: container("", "report.pdf"))
case("reject/payload-file-dot")(lambda: container(".", "report.pdf"))
case("reject/payload-file-dotdot")(lambda: container("..", "report.pdf"))
case("reject/payload-file-forward-slash")(lambda: container("sub/report.pdf"))
case("reject/payload-file-backslash")(lambda: container("sub\\report.pdf"))
case("reject/payload-file-traversal")(lambda: container("../../etc/passwd"))
case("reject/payload-file-colon-drive")(lambda: container("C:report.pdf"))
case("reject/payload-file-colon-plain")(lambda: container("notes:draft.txt"))
case("reject/payload-file-equals-metadata")(lambda: container(META_NAME, "report.pdf"))

# A parser may refuse the escape itself, in which case the container is rejected
# for a different reason and the verdict is unchanged.
case("reject/payload-file-nul")(lambda: container("rep\u0000ort.pdf"))
case("reject/payload-file-newline")(lambda: container("report\u000apdf"))
case("reject/payload-file-del")(lambda: container("report\u007fpdf"))


# --------------------------------------------------------------------------
# Reject — payload entry type
# --------------------------------------------------------------------------

case("reject/payload-symlink")(
    lambda: container(payload=b"/etc/passwd", payload_mode=MODE_SYMLINK)
)
case("reject/payload-directory-entry")(
    lambda: container(payload=b"", payload_mode=MODE_DIRECTORY)
)
case("reject/payload-fifo-entry")(lambda: container(payload=b"", payload_mode=MODE_FIFO))


# --------------------------------------------------------------------------
# Undetermined and out of scope
# --------------------------------------------------------------------------

case("undetermined/encrypted-metadata-member")(lambda: container(encrypt_metadata=True))
case("out-of-scope/version-2-0")(lambda: container(version="2.0"))
case("out-of-scope/version-malformed")(lambda: container(version="banana"))
case("out-of-scope/version-empty-string")(lambda: container(version=""))


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


# Metadata using TOML 1.1.0 syntax that the standard library cannot parse, since
# tomllib implements 1.0.0. Skipped by the self-check rather than passed silently.
NEEDS_TOML_11 = {"accept/metadata-inline-table-multiline"}


def check_cases(manifest: list[dict], out_dir: pathlib.Path) -> list[str]:
    """Re-read what was written and hold it to §2.2 and §2.1.

    A case declared conformant must actually be conformant. Checking only that
    payload.file resolves is not enough: it misses a document whose
    slipcase_version was captured by a preceding table header, which is how
    accept/metadata-key-order-reversed shipped wrong: the half that was checked
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
                metadata = archive.read(META_NAME)
                members = archive.namelist()
        except Exception as error:
            problems.append(f"{case_id}: unreadable archive: {error}")
            continue
        if metadata.startswith(b"\xef\xbb\xbf"):
            metadata = metadata[3:]
        try:
            document = tomllib.loads(metadata.decode("utf-8"))
        except Exception as error:
            problems.append(f"{case_id}: metadata does not parse: {error}")
            continue
        if not isinstance(document.get("slipcase_version"), str):
            problems.append(
                f"{case_id}: no root slipcase_version (root keys: {sorted(document)})"
            )
        payload = document.get("payload")
        target = payload.get("file") if isinstance(payload, dict) else None
        if not isinstance(target, str):
            problems.append(f"{case_id}: payload.file is not a string")
        elif target not in members:
            problems.append(f"{case_id}: payload.file {target!r} names no member")
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
