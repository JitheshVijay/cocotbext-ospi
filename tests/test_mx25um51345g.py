"""Macronix MX25UM51345G: behaviour taken from the datasheet.

These check the things that differ between a real octal part and a generic
octal memory -- the CR2 mode switch, the inverted command extension, the
address phase and dummy cycles that register reads grow in OPI, and the
configurable array dummy cycles.
"""

import cocotb
from cocotb.clock import Clock

from cocotbext.ospi.devices import (
    MX25UM51345G, CR2_MODE, CR2_DUMMY, CR2_MODE_SOPI, CR2_MODE_SPI,
    DUMMY_CYCLES, PROTO_1S_1S_1S, PROTO_8S_8S_8S, PROTO_8D_8D_8D,
    CR2_MODE_DOPI,
)
from cocotbext.ospi.xspi_flash import XspiFlash, STATUS_WEL, STATUS_WIP


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    flash = XspiFlash(dut, MX25UM51345G)
    await flash.initialize()
    return flash


@cocotb.test()
async def test_boots_in_spi(dut):
    """The part comes up single-lane, and identifies itself there."""
    flash = await setup(dut)
    assert flash.protocol == PROTO_1S_1S_1S
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]


@cocotb.test()
async def test_cr2_mode_register_defaults_to_spi(dut):
    """CR2[0x00000000] reads 0 -- SPI -- out of reset."""
    flash = await setup(dut)
    assert await flash.read_register(CR2_MODE) == CR2_MODE_SPI


@cocotb.test()
async def test_enter_octal_and_identify(dut):
    """Writing CR2 switches the part to 8S-8S-8S; the ID still reads back.

    This is the real bring-up sequence, and it exercises the parts of the
    protocol that only exist in octal: the two-byte command, the address
    phase RDID grows, and its four dummy cycles.
    """
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8S_8S_8S)
    assert flash.protocol == PROTO_8S_8S_8S
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]


@cocotb.test()
async def test_mode_register_reads_back_in_octal(dut):
    """Once switched, CR2 itself reads back over the octal bus."""
    flash = await setup(dut)
    await flash.enter_octal()
    assert await flash.read_register(CR2_MODE) == CR2_MODE_SOPI


@cocotb.test()
async def test_returns_to_spi(dut):
    """Clearing CR2 puts the part back on one lane."""
    flash = await setup(dut)
    await flash.enter_octal()
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]

    await flash.exit_octal()
    assert flash.protocol == PROTO_1S_1S_1S
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]


@cocotb.test()
async def test_wrong_command_extension_is_ignored(dut):
    """A command whose extension is not the complement does nothing.

    Macronix uses SPI_NOR_EXT_INVERT. Sending a repeated opcode instead --
    what a Micron part would want -- must not be honoured, which is exactly
    the failure a controller hits with the wrong extension configured.
    """
    flash = await setup(dut)
    await flash.enter_octal()

    wren = MX25UM51345G.ops["WREN"]
    assert MX25UM51345G.extension(wren.opcode) == (~wren.opcode) & 0xFF

    # Send WREN with a repeated opcode rather than its complement.
    await flash.master.start()
    await flash.master.send_byte(wren.opcode, lanes=8)
    await flash.master.send_byte(wren.opcode, lanes=8)   # wrong extension
    await flash.master.stop()

    assert not await flash.read_status() & STATUS_WEL, \
        "WREN was honoured despite a bad command extension"

    # The correct extension still works.
    await flash.write_enable()
    assert await flash.read_status() & STATUS_WEL


@cocotb.test()
async def test_program_and_read_in_octal(dut):
    """Program and read back over the octal bus."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.program(0x00000010, [0xA5, 0x5A, 0x81])
    assert await flash.read(0x00000010, 3) == [0xA5, 0x5A, 0x81]


@cocotb.test()
async def test_program_requires_write_enable(dut):
    """Page program with no WEL is ignored."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash._transfer("PP", address=0x00000020, write=[0x11])
    assert await flash.read_byte(0x00000020) == 0xFF


@cocotb.test()
async def test_program_clears_bits_only(dut):
    """NOR programming can clear bits but never set them."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.program(0x00000030, 0xF0)
    assert await flash.read_byte(0x00000030) == 0xF0
    await flash.program(0x00000030, 0x0F)
    assert await flash.read_byte(0x00000030) == 0x00

    await flash.erase_sector(0x00000030)
    assert await flash.read_byte(0x00000030) == 0xFF


@cocotb.test()
async def test_wip_is_set_during_program(dut):
    """The part reports busy, and the program consumes WEL."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.write_enable()
    await flash._transfer("PP", address=0x00000040, write=[0x5A])

    assert await flash.read_status() & STATUS_WIP
    await flash.wait_ready()

    status = await flash.read_status()
    assert not status & STATUS_WIP
    assert not status & STATUS_WEL, "WEL should be consumed by the program"
    assert await flash.read_byte(0x00000040) == 0x5A


@cocotb.test()
async def test_configurable_array_dummy_cycles(dut):
    """DC[2:0] in CR2[0x300] changes how many dummy cycles 8READ needs.

    The datasheet's table runs 20, 18, 16, 14, 12, 10, 8, 6 -- fewer dummy
    cycles for lower clock frequencies. A controller that does not track
    this reads garbage, so the driver has to follow the register.
    """
    flash = await setup(dut)
    await flash.enter_octal()
    await flash.program(0x00000050, 0x3C)

    for dc_bits, cycles in sorted(DUMMY_CYCLES.items()):
        await flash.write_register(CR2_DUMMY, dc_bits)
        assert await flash.read_register(CR2_DUMMY) == dc_bits

        # Tell the driver what the part now expects, then read.
        MX25UM51345G.ops["8READ"].opi_dummy = cycles
        got = await flash.read_byte(0x00000050)
        assert got == 0x3C, (
            f"DC={dc_bits:03b} ({cycles} dummy cycles): read {got:#04x}"
        )

    # Restore *both* sides. Leaving the device on a non-default DC while the
    # driver goes back to 20 desynchronises them and every later read returns
    # garbage -- which is the same failure this test exists to catch.
    await flash.write_register(CR2_DUMMY, 0b000)
    MX25UM51345G.ops["8READ"].opi_dummy = DUMMY_CYCLES[0b000]


@cocotb.test()
async def test_sector_erase_spans_the_sector(dut):
    """Erase clears its whole 4 KB sector and leaves the next alone."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.program(0x00000000, 0x11)
    await flash.program(0x00000FFF, 0x22)
    await flash.program(0x00001000, 0x33)

    await flash.erase_sector(0x00000000)

    assert await flash.read_byte(0x00000000) == 0xFF
    assert await flash.read_byte(0x00000FFF) == 0xFF
    assert await flash.read_byte(0x00001000) == 0x33


# ── DOPI (8D-8D-8D) ──────────────────────────────────────────────────

@cocotb.test()
async def test_enter_dopi_and_identify(dut):
    """CR2 bit 1 selects DTR octal; 8DTRD (EE/11) reads the array there."""
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8D_8D_8D)
    assert flash.protocol == PROTO_8D_8D_8D
    assert flash.dtr
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]
    assert await flash.read_register(CR2_MODE) == CR2_MODE_DOPI


@cocotb.test()
async def test_program_and_read_in_dopi(dut):
    """Program and read back at double transfer rate."""
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8D_8D_8D)

    await flash.program(0x00000100, [0xDE, 0xAD, 0xBE, 0xEF])
    assert await flash.read(0x00000100, 4) == [0xDE, 0xAD, 0xBE, 0xEF]


@cocotb.test()
async def test_dopi_rejects_an_odd_start_address(dut):
    """Datasheet note 5: in DTR OPI the start address must be even.

    A part that quietly returned the neighbouring byte instead would be far
    harder to debug than one that rejects the command, so the model rejects.
    """
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8D_8D_8D)

    await flash.program(0x00000200, [0x11, 0x22])
    assert await flash.read(0x00000200, 2) == [0x11, 0x22]

    # An odd address is refused: the device never drives, so the bus floats.
    try:
        await flash.read(0x00000201, 1)
    except ValueError as exc:
        assert "not 0 or 1" in str(exc)
    else:
        raise AssertionError("odd start address was accepted in DTR OPI")


@cocotb.test()
async def test_str_and_dtr_octal_agree(dut):
    """The same bytes come back through SOPI and DOPI."""
    flash = await setup(dut)

    await flash.enter_octal(PROTO_8S_8S_8S)
    await flash.program(0x00000300, [0xC0, 0xDE])
    via_str = await flash.read(0x00000300, 2)

    await flash.exit_octal()
    await flash.enter_octal(PROTO_8D_8D_8D)
    via_dtr = await flash.read(0x00000300, 2)

    assert via_str == via_dtr == [0xC0, 0xDE]


# ── SFDP ─────────────────────────────────────────────────────────────

@cocotb.test()
async def test_sfdp_in_spi(dut):
    """The part describes itself, before anything is configured."""
    flash = await setup(dut)
    info = await flash.discover()

    assert info.density_bits == 512 * 1024 * 1024
    assert info.size_bytes == 64 * 1024 * 1024
    assert info.address_bytes_name == "4 only"
    assert info.dtr
    assert info.page_size == 256
    assert dict((op, size) for size, op in info.erase_types) == {
        0x21: 4096, 0xDC: 65536,
    }


@cocotb.test()
async def test_sfdp_survives_the_mode_switch(dut):
    """RDSFDP works in octal too, with its different shape.

    In SPI it takes 3 address bytes and 8 dummy cycles; in OPI, 4 and 20.
    Reading the same table both ways is what proves the profile has both.
    """
    flash = await setup(dut)
    in_spi = await flash.read_sfdp(64)

    await flash.enter_octal(PROTO_8S_8S_8S)
    in_octal = await flash.read_sfdp(64)

    assert in_spi == in_octal, "SFDP differs between SPI and octal"
    assert in_spi[:4] == b"SFDP"
