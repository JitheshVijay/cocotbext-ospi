"""Micron MT35XU512ABA — 512 Mb 1.8 V Xccela octal NOR flash.

Taken from Linux drivers/mtd/spi-nor/micron-st.c, which is tested against
the real part, plus the Xccela/JESD251 conventions it follows.

The part boots in extended SPI and is switched into octal DTR by writing two
volatile configuration registers with WRITE VOLATILE REGISTER (0x81):

    CFR1V @ 0x01   dummy cycles for array reads (20 for 8D-8D-8D)
    CFR0V @ 0x00   0xE7 enters octal DTR, 0xFF returns to extended SPI

Order matters: the dummy-cycle count has to be right *before* the protocol
changes, because the very next read already uses it.

The command extension repeats the opcode rather than inverting it. That is
the single most likely thing to be wrong in a controller ported from a
Macronix part, and the two models disagree about it deliberately.
"""

from .profile import (
    DeviceProfile, Op, EXT_REPEAT,
    PROTO_1S_1S_1S, PROTO_8D_8D_8D,
)

CFR0V = 0x00
CFR1V = 0x01

CFR0V_OCTAL_DTR = 0xE7
CFR0V_EXT_SPI = 0xFF
CFR1V_DEFAULT = 0x1F

#: Dummy cycles Linux programs for 8D-8D-8D at the part's top speed.
OCTAL_DTR_DUMMY = 20


async def _enter_octal(flash, protocol=PROTO_8D_8D_8D):
    """Write CFR1V then CFR0V, in that order."""
    await flash.write_register(CFR1V, OCTAL_DTR_DUMMY)
    await flash.write_register(CFR0V, CFR0V_OCTAL_DTR)
    flash.protocol = protocol
    MT35XU512ABA.ops["READ"].opi_dummy = OCTAL_DTR_DUMMY


async def _exit_octal(flash):
    """Return to extended SPI.

    A 1-byte transfer is impossible in 8D-8D-8D -- eight lanes on both edges
    move two bytes per clock -- so CFR0V and CFR1V are written together as
    one 2-byte transfer. Linux does the same thing for the same reason.
    """
    await flash.write_register(CFR0V, [CFR0V_EXT_SPI, CFR1V_DEFAULT])
    flash.protocol = PROTO_1S_1S_1S


MT35XU512ABA = DeviceProfile(
    name="MT35XU512ABA",
    jedec_id=[0x2C, 0x5B, 0x1A],
    cmd_ext=EXT_REPEAT,
    supported=[PROTO_1S_1S_1S, PROTO_8D_8D_8D],
    octal_default=PROTO_8D_8D_8D,
    array_dummy=OCTAL_DTR_DUMMY,
    ops={
        "RDID":  Op(0x9F, addr_bytes=0, dummy=0, opi_dummy=8),
        "RDSR":  Op(0x05, addr_bytes=0, dummy=0, opi_dummy=8),
        "WREN":  Op(0x06),
        "WRDI":  Op(0x04),
        # Register access is address-mapped, like Macronix's CR2, but with
        # its own opcodes and a 1-byte register index inside a 4-byte field.
        "RDCR2": Op(0x85, addr_bytes=4, dummy=0, opi_dummy=8),
        "WRCR2": Op(0x81, addr_bytes=4, dummy=0),
        "RSTEN": Op(0x66),
        "RST":   Op(0x99),

        "READ":  Op(0x13, addr_bytes=4, dummy=0),    # extended SPI
        "8READ": Op(0xFD, addr_bytes=4, opi_dummy=OCTAL_DTR_DUMMY),
        "RDSFDP": Op(0x5A, addr_bytes=3, dummy=8, opi_addr_bytes=4, opi_dummy=20),
        "PP":    Op(0x12, addr_bytes=4, dummy=0),
        "SE":    Op(0x21, addr_bytes=4, dummy=0),
    },
    enter_octal=_enter_octal,
    exit_octal=_exit_octal,
)
