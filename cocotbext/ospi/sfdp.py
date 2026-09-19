"""SFDP — Serial Flash Discoverable Parameters (JESD216).

SFDP is the table a flash carries describing itself: density, how many
address bytes it takes, which erase types it has, its page size. A driver
reads it instead of keeping a database of part numbers.

This module both **builds** tables (so the device models can carry a correct
one) and **parses** them (so the driver can discover a part it was told
nothing about). Building and parsing from one definition is deliberate: the
tests read back through the parser what the builder put in the model, so the
two cannot drift apart.

Layout, from JESD216:

    offset 0   SFDP header, 8 bytes
               "SFDP" signature, minor/major revision, NPH, access protocol
    offset 8   one 8-byte parameter header per table
               id_lsb, minor, major, length in dwords, 3-byte pointer, id_msb
    pointer    the table itself

The Basic Flash Parameter Table (BFPT, id 0xFF00) is the one every part has.
"""

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SFDP_SIGNATURE = 0x50444653   # "SFDP" little-endian

BFPT_ID = 0xFF00

# Address-byte encoding, BFPT dword 1 bits [18:17].
ADDR_3_ONLY = 0b00
ADDR_3_OR_4 = 0b01
ADDR_4_ONLY = 0b10

ADDR_BYTES_NAME = {
    ADDR_3_ONLY: "3 only",
    ADDR_3_OR_4: "3 or 4",
    ADDR_4_ONLY: "4 only",
}


# ── building ─────────────────────────────────────────────────────────

def build_bfpt(density_bits: int, address_bytes: int = ADDR_4_ONLY,
               dtr: bool = False, page_size: int = 256,
               erase_types=((12, 0x21), (16, 0xDC)),
               dwords: int = 16) -> List[int]:
    """Build a Basic Flash Parameter Table as a list of dwords.

    ``erase_types`` is a sequence of (size as a power of two, opcode);
    4 KB is 12, 64 KB is 16.
    """
    table = [0xFFFFFFFF] * dwords

    # DWORD 1: erase granularity, 4 KB opcode, address bytes, DTR support.
    dw1 = 0
    dw1 |= (0b01 << 0)                       # uniform 4 KB erase available
    dw1 |= (erase_types[0][1] & 0xFF) << 8   # 4 KB erase opcode
    dw1 |= (address_bytes & 0b11) << 17
    if dtr:
        dw1 |= 1 << 19
    table[0] = dw1

    # DWORD 2: density in bits. A power of two is encoded as the exponent
    # with bit 31 set; anything else is the bit count minus one.
    if density_bits and (density_bits & (density_bits - 1)) == 0:
        table[1] = (1 << 31) | (density_bits.bit_length() - 1)
    else:
        table[1] = density_bits - 1

    # DWORD 8: erase types 1 and 2 (size exponent, then opcode).
    dw8 = 0
    for index, (size_pow2, opcode) in enumerate(erase_types[:2]):
        dw8 |= (size_pow2 & 0xFF) << (index * 16)
        dw8 |= (opcode & 0xFF) << (index * 16 + 8)
    table[7] = dw8

    # DWORD 11: page size, as a power of two in bits [7:4].
    if dwords >= 11:
        table[10] = (page_size.bit_length() - 1) << 4

    return table


def build_sfdp(tables: Dict[int, List[int]], major: int = 1,
               minor: int = 6) -> bytes:
    """Assemble a full SFDP image from {parameter id: dwords}."""
    count = len(tables)
    header = struct.pack("<IBBBB", SFDP_SIGNATURE, minor, major,
                         count - 1,      # NPH is the count minus one
                         0xFF)           # access protocol / unused

    # Tables start after the header and all the parameter headers.
    pointer = len(header) + count * 8
    param_headers = b""
    body = b""
    for param_id, dwords in tables.items():
        param_headers += struct.pack(
            "<BBBB", param_id & 0xFF, minor, major, len(dwords)
        )
        param_headers += bytes(
            [pointer & 0xFF, (pointer >> 8) & 0xFF, (pointer >> 16) & 0xFF]
        )
        param_headers += bytes([(param_id >> 8) & 0xFF])
        body += b"".join(struct.pack("<I", d) for d in dwords)
        pointer += len(dwords) * 4

    return header + param_headers + body


# ── parsing ──────────────────────────────────────────────────────────

@dataclass
class ParameterHeader:
    param_id: int
    major: int
    minor: int
    dwords: int
    pointer: int


@dataclass
class SfdpInfo:
    """What a driver learns from a part's SFDP."""
    major: int
    minor: int
    headers: List[ParameterHeader] = field(default_factory=list)
    bfpt: Optional[List[int]] = None

    # Decoded from the BFPT.
    density_bits: Optional[int] = None
    size_bytes: Optional[int] = None
    address_bytes: Optional[int] = None
    dtr: bool = False
    page_size: Optional[int] = None
    erase_types: List[tuple] = field(default_factory=list)

    @property
    def address_bytes_name(self) -> str:
        return ADDR_BYTES_NAME.get(self.address_bytes, "unknown")


class SfdpError(Exception):
    pass


def parse_sfdp(read) -> SfdpInfo:
    """Parse an SFDP image.

    ``read`` is a plain ``bytes``-like image, or anything indexable by
    ``[start:stop]``.
    """
    header = bytes(read[0:8])
    if len(header) < 8:
        raise SfdpError("SFDP image is shorter than its header")

    signature, minor, major, nph, _ = struct.unpack("<IBBBB", header)
    if signature != SFDP_SIGNATURE:
        raise SfdpError(
            f"bad SFDP signature {signature:#010x} "
            f"(expected {SFDP_SIGNATURE:#010x}); the part may not have SFDP, "
            f"or the read used the wrong dummy cycle count"
        )

    info = SfdpInfo(major=major, minor=minor)

    for index in range(nph + 1):
        offset = 8 + index * 8
        raw = bytes(read[offset:offset + 8])
        if len(raw) < 8:
            raise SfdpError(f"parameter header {index} runs past the image")
        id_lsb, p_minor, p_major, length = raw[0], raw[1], raw[2], raw[3]
        pointer = raw[4] | (raw[5] << 8) | (raw[6] << 16)
        param_id = (raw[7] << 8) | id_lsb
        info.headers.append(
            ParameterHeader(param_id, p_major, p_minor, length, pointer)
        )

    for head in info.headers:
        if head.param_id != BFPT_ID:
            continue
        raw = bytes(read[head.pointer:head.pointer + head.dwords * 4])
        if len(raw) < head.dwords * 4:
            raise SfdpError("BFPT runs past the image")
        info.bfpt = list(struct.unpack(f"<{head.dwords}I", raw))
        _decode_bfpt(info)

    return info


def _decode_bfpt(info: SfdpInfo):
    bfpt = info.bfpt
    dw1, dw2 = bfpt[0], bfpt[1]

    info.address_bytes = (dw1 >> 17) & 0b11
    info.dtr = bool(dw1 & (1 << 19))

    if dw2 & (1 << 31):
        info.density_bits = 1 << (dw2 & ~(1 << 31))
    else:
        info.density_bits = dw2 + 1
    info.size_bytes = info.density_bits // 8

    if len(bfpt) >= 8:
        dw8 = bfpt[7]
        for index in range(2):
            size_pow2 = (dw8 >> (index * 16)) & 0xFF
            opcode = (dw8 >> (index * 16 + 8)) & 0xFF
            if size_pow2:
                info.erase_types.append((1 << size_pow2, opcode))

    if len(bfpt) >= 11:
        shift = (bfpt[10] >> 4) & 0xF
        if shift:
            info.page_size = 1 << shift
