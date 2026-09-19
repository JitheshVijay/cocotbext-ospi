"""Macronix MX25UM51345G — 512 Mb 1.8 V Octa Flash.

Datasheet Rev 1.3 (2020-02-05), cross-checked against Linux
drivers/mtd/spi-nor/macronix.c.

The part boots in single-lane SPI. Octal is enabled by writing
Configuration Register 2, which is address-mapped -- WRCR2 (0x72) carries a
4-byte CR2 address, so one opcode reaches several registers:

    0x00000000  bit0 SOPI (STR octal), bit1 DOPI (DTR octal); 0 = SPI
    0x00000200  DQS configuration
    0x00000300  DC[2:0], dummy cycles for array reads

Command extension is the bitwise complement: 8READ is EC/13, PP4B is 12/ED.
"""

from .profile import (
    DeviceProfile, Op, EXT_INVERT,
    PROTO_1S_1S_1S, PROTO_8S_8S_8S, PROTO_8D_8D_8D,
)

# CR2 addresses.
CR2_MODE = 0x00000000
CR2_DQS = 0x00000200

# CR2[0x00000200] bits.
CR2_DQS_DOS = 0x02      # DQS on STR mode
CR2_DQS_PRC = 0x01      # DTR DQS pre-cycle
CR2_DUMMY = 0x00000300

# CR2[0x00000000] values.
CR2_MODE_SPI = 0x00
CR2_MODE_SOPI = 0x01   # 8S-8S-8S
CR2_MODE_DOPI = 0x02   # 8D-8D-8D

# Security register bits, datasheet Table 5.
SCUR_WPSEL = 0x80    # 0 = BP protection, 1 = advanced sector protection
SCUR_E_FAIL = 0x40   # last erase failed or the region was protected
SCUR_P_FAIL = 0x20   # last program failed or the region was protected
SCUR_ESB = 0x08      # erase suspended
SCUR_PSB = 0x04      # program suspended
SCUR_LDSO = 0x02     # secured OTP locked down (one-way)
SCUR_OTP = 0x01      # secured OTP factory-lock indicator

# CR2[0x00000300] DC[2:0] -> array read dummy cycles, from the datasheet's
# "Dummy Cycle and Frequency Table".
DUMMY_CYCLES = {0b000: 20, 0b001: 18, 0b010: 16, 0b011: 14,
                0b100: 12, 0b101: 10, 0b110: 8, 0b111: 6}


async def _enter_octal(flash, protocol=PROTO_8S_8S_8S):
    """Switch the part into octal by writing CR2.

    The write itself goes out in the *current* protocol; the new one applies
    from the next command onward, which is why the driver re-reads the ID
    afterwards to confirm the switch took.
    """
    value = CR2_MODE_SOPI if protocol == PROTO_8S_8S_8S else CR2_MODE_DOPI
    await flash.write_register(CR2_MODE, value)
    flash.protocol = protocol


async def _exit_octal(flash):
    await flash.write_register(CR2_MODE, CR2_MODE_SPI)
    flash.protocol = PROTO_1S_1S_1S


MX25UM51345G = DeviceProfile(
    name="MX25UM51345G",
    jedec_id=[0xC2, 0x80, 0x3A],
    cmd_ext=EXT_INVERT,
    supported=[PROTO_1S_1S_1S, PROTO_8S_8S_8S, PROTO_8D_8D_8D],
    octal_default=PROTO_8S_8S_8S,
    array_dummy=20,
    ops={
        # Register access. Note how RDSR and RDID gain an address phase and
        # dummy cycles in octal that they do not have in SPI -- a classic
        # bring-up trap.
        "RDID":  Op(0x9F, addr_bytes=0, dummy=0, opi_addr_bytes=4, opi_dummy=4),
        "RDSR":  Op(0x05, addr_bytes=0, dummy=0, opi_addr_bytes=4, opi_dummy=4),
        "WREN":  Op(0x06),
        "WRDI":  Op(0x04),
        "RDCR2": Op(0x71, addr_bytes=4, dummy=0, opi_dummy=4),
        "WRCR2": Op(0x72, addr_bytes=4, dummy=0),
        # Software reset: RSTEN must immediately precede RST.
        "RSTEN": Op(0x66),
        "RST":   Op(0x99),

        # Security register and advanced sector protection.
        "RDSCUR": Op(0x2B, addr_bytes=0, dummy=0, opi_addr_bytes=4, opi_dummy=4),
        "WRSCUR": Op(0x2F),
        "WPSEL":  Op(0x68),
        "WRDPB":  Op(0xE1, addr_bytes=4, dummy=0),
        "RDDPB":  Op(0xE0, addr_bytes=4, dummy=0, opi_dummy=4),

        # Program/erase suspend and resume.
        "SUSPEND": Op(0xB0),
        "RESUME":  Op(0x30),

        # Array access.
        "READ":  Op(0x13, addr_bytes=4, dummy=0),    # SPI 4-byte read
        "8READ": Op(0xEC, addr_bytes=4, opi_dummy=20),   # STR octal
        "8DTRD": Op(0xEE, addr_bytes=4, opi_dummy=20),   # DTR octal
        # RDSFDP takes 3 address bytes and 8 dummy cycles in SPI, but 4 and
        # 20 in OPI -- so discovery has to know which mode it is in.
        "RDSFDP": Op(0x5A, addr_bytes=3, dummy=8, opi_addr_bytes=4, opi_dummy=20),
        "PP":    Op(0x12, addr_bytes=4, dummy=0),
        "SE":    Op(0x21, addr_bytes=4, dummy=0),
    },
    enter_octal=_enter_octal,
    exit_octal=_exit_octal,
)
