"""Functional tests for the OSPI flash model and the cocotbext-ospi driver."""

import cocotb
from cocotb.clock import Clock

from cocotbext.ospi import OspiFlash

# 0 single, 1 dual, 2 quad, 3 octal
ALL_MODES = [0, 1, 2, 3]
MODE_NAMES = {0: "single", 1: "dual", 2: "quad", 3: "octal"}


async def setup(dut):
    """Start the OSPI clock and reset the flash."""
    cocotb.start_soon(Clock(dut.OSPI_CLK, 20, units="ns").start())
    flash = OspiFlash(dut)
    await flash.initialize()
    return flash


@cocotb.test()
async def test_write_then_read_every_mode(dut):
    """A programmed byte reads back unchanged in all four lane widths."""
    flash = await setup(dut)
    for mode in ALL_MODES:
        address = 0x10 + mode
        value = 0xA5 + mode
        await flash.write(address, value, mode=mode)
        got = await flash.read(address, mode=mode)
        assert got == value, (
            f"{MODE_NAMES[mode]} mode: read {got:#04x}, wrote {value:#04x}"
        )


@cocotb.test()
async def test_erase_restores_ff(dut):
    """Erasing returns the byte to 0xFF, in every mode."""
    flash = await setup(dut)
    for mode in ALL_MODES:
        address = 0x20 + mode
        await flash.write(address, 0x5A, mode=mode)
        assert await flash.read(address, mode=mode) == 0x5A
        await flash.erase(address, mode=mode)
        assert await flash.read(address, mode=mode) == 0xFF


@cocotb.test()
async def test_modes_share_one_memory(dut):
    """A byte written in one mode is readable in any other."""
    flash = await setup(dut)
    await flash.write(0x30, 0xC3, mode=3)   # octal
    for mode in ALL_MODES:
        got = await flash.read(0x30, mode=mode)
        assert got == 0xC3, f"read back {got:#04x} in {MODE_NAMES[mode]} mode"


@cocotb.test()
async def test_addresses_are_independent(dut):
    """Writing one address leaves its neighbours alone."""
    flash = await setup(dut)
    for offset, value in enumerate((0x11, 0x22, 0x33)):
        await flash.write(0x40 + offset, value, mode=2)
    for offset, value in enumerate((0x11, 0x22, 0x33)):
        assert await flash.read(0x40 + offset, mode=2) == value


@cocotb.test()
async def test_unwritten_memory_reads_erased(dut):
    """Flash powers up erased."""
    flash = await setup(dut)
    assert await flash.read(0x7F, mode=2) == 0xFF


@cocotb.test()
async def test_byte_values_round_trip(dut):
    """Bit patterns that stress lane packing survive the round trip."""
    flash = await setup(dut)
    values = [0x00, 0x01, 0x80, 0x0F, 0xF0, 0xFF, 0xA5, 0x5A]
    for address, value in enumerate(values):
        await flash.write(address, value, mode=1)
    for address, value in enumerate(values):
        got = await flash.read(address, mode=1)
        assert got == value, f"addr {address:#04x}: {got:#04x} != {value:#04x}"


@cocotb.test()
async def test_24_bit_address_low_byte_selects_cell(dut):
    """The address is carried as 24 bits; memory is indexed by its low byte."""
    flash = await setup(dut)
    await flash.write(0x00, 0x77, mode=2)
    assert await flash.read(0xABCD00, mode=2) == 0x77


@cocotb.test()
async def test_hold_preserves_memory(dut):
    """Data written before a hold is intact after the hold is released."""
    flash = await setup(dut)
    await flash.write(0x50, 0xC5, mode=0)

    await flash.hold()
    await flash.release_hold()

    assert await flash.read(0x50, mode=0) == 0xC5
    # And the device still accepts new traffic afterwards.
    await flash.write(0x50, 0xC6, mode=1)
    assert await flash.read(0x50, mode=1) == 0xC6
