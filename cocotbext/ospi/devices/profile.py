"""Device profiles for real octal (xSPI) NOR flash parts.

Each profile records what a specific part actually does, taken from its
datasheet and cross-checked against Linux's drivers/mtd/spi-nor. The driver
is generic; everything device-specific lives here.

The two things that differ most between vendors, and that break bring-up
most often:

* **Command extension.** In octal mode a command is two bytes: the opcode
  and an extension. Macronix sends the bitwise complement, Micron repeats
  the opcode. Linux calls these SPI_NOR_EXT_INVERT and SPI_NOR_EXT_REPEAT.

* **How you get into octal at all.** The part boots in single-lane SPI and
  is switched by writing a configuration register -- a different register,
  at a different address, with a different value, on each vendor.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# Command extension types, mirroring Linux's naming.
EXT_INVERT = "invert"   # extension = ~opcode   (Macronix)
EXT_REPEAT = "repeat"   # extension = opcode    (Micron)

# Protocols, named as the industry does: <cmd>-<addr>-<data> lanes, S or D
# for single or double transfer rate.
PROTO_1S_1S_1S = "1S-1S-1S"
PROTO_8S_8S_8S = "8S-8S-8S"
PROTO_8D_8D_8D = "8D-8D-8D"

LANES = {PROTO_1S_1S_1S: 1, PROTO_8S_8S_8S: 8, PROTO_8D_8D_8D: 8}
IS_DTR = {PROTO_1S_1S_1S: False, PROTO_8S_8S_8S: False, PROTO_8D_8D_8D: True}


@dataclass
class Op:
    """One command's shape: how many address bytes and dummy cycles it takes.

    A command's shape changes with the protocol -- RDSR takes no address and
    no dummy cycles in SPI, but four address bytes and four dummy cycles in
    Macronix OPI. ``opi`` overrides ``spi`` when the part is in octal.
    """
    opcode: int
    addr_bytes: int = 0
    dummy: int = 0
    opi_addr_bytes: Optional[int] = None
    opi_dummy: Optional[int] = None

    def shape(self, octal: bool):
        if octal:
            addr = self.opi_addr_bytes if self.opi_addr_bytes is not None else self.addr_bytes
            dummy = self.opi_dummy if self.opi_dummy is not None else self.dummy
            return addr, dummy
        return self.addr_bytes, self.dummy


@dataclass
class DeviceProfile:
    name: str
    jedec_id: List[int]
    cmd_ext: str
    ops: Dict[str, Op]
    #: Written into the driver by enter_octal(); see the concrete profiles.
    enter_octal: Optional[Callable] = None
    exit_octal: Optional[Callable] = None
    #: Protocols this profile's model actually implements.
    supported: List[str] = field(default_factory=lambda: [PROTO_1S_1S_1S])
    page_size: int = 256
    sector_size: int = 4096
    #: Dummy cycles the part uses for array reads once in octal.
    array_dummy: int = 20
    #: Which octal protocol ``enter_octal()`` picks when not told. Explicit
    #: rather than inferred: a part supporting both STR and DTR octal has a
    #: preferred one, and guessing changes behaviour when a mode is added.
    octal_default: Optional[str] = None

    @property
    def default_octal(self) -> str:
        """The octal protocol ``enter_octal()`` uses when not given one."""
        if self.octal_default:
            return self.octal_default
        for proto in (PROTO_8S_8S_8S, PROTO_8D_8D_8D):
            if proto in self.supported:
                return proto
        raise ValueError(f"{self.name} profile models no octal protocol")

    def extension(self, opcode: int) -> int:
        """The second command byte sent in octal mode."""
        if self.cmd_ext == EXT_INVERT:
            return (~opcode) & 0xFF
        if self.cmd_ext == EXT_REPEAT:
            return opcode & 0xFF
        raise ValueError(f"unknown command extension type {self.cmd_ext!r}")
