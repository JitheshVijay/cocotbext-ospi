"""Functional tests for the OSPI NOR flash model and the cocotbext-ospi driver."""

import cocotb
from cocotb.clock import Clock

from cocotbext.ospi import (
    OspiFlash,
    CMD_READ, CMD_DIOR, CMD_QIOR, CMD_OIOR,
    STATUS_WEL, STATUS_WIP,
)

READ_OPCODES = [CMD_READ, CMD_DIOR, CMD_QIOR, CMD_OIOR]
NAMES = {CMD_READ: "read", CMD_DIOR: "dual I/O",
         CMD_QIOR: "quad I/O", CMD_OIOR: "octal I/O"}


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    flash = OspiFlash(dut)
    await flash.initialize()
    return flash


@cocotb.test()
async def test_jedec_id(dut):
    """The device identifies itself."""
    flash = await setup(dut)
    assert await flash.read_id() == [0xC2, 0x80, 0x39]


@cocotb.test()
async def test_erased_memory_reads_ff(dut):
    """Flash powers up erased."""
    flash = await setup(dut)
    assert await flash.read(0x000000, 4) == [0xFF] * 4


@cocotb.test()
async def test_write_enable_latch(dut):
    """WREN sets WEL and WRDI clears it."""
    flash = await setup(dut)
    assert not await flash.read_status() & STATUS_WEL
    await flash.write_enable()
    assert await flash.read_status() & STATUS_WEL
    await flash.write_disable()
    assert not await flash.read_status() & STATUS_WEL


@cocotb.test()
async def test_program_requires_write_enable(dut):
    """A program with no WEL is ignored, as the device requires."""
    flash = await setup(dut)
    await flash.master.start()
    await flash.master.send_byte(0x02, lanes=1)
    await flash.master.send_address(0x000000, lanes=1)
    await flash.master.send_byte(0xA5, lanes=1)
    await flash.master.stop()
    assert await flash.read_byte(0x000000) == 0xFF, "programmed without WEL"


@cocotb.test()
async def test_program_then_read(dut):
    """A programmed byte reads back."""
    flash = await setup(dut)
    await flash.program(0x000010, 0xA5)
    assert await flash.read_byte(0x000010) == 0xA5


@cocotb.test()
async def test_program_clears_bits_only(dut):
    """NOR programming can clear bits but never set them."""
    flash = await setup(dut)
    await flash.program(0x000020, 0xF0)
    assert await flash.read_byte(0x000020) == 0xF0
    await flash.program(0x000020, 0x0F)
    assert await flash.read_byte(0x000020) == 0x00
    await flash.erase_sector(0x000020)
    assert await flash.read_byte(0x000020) == 0xFF


@cocotb.test()
async def test_wip_is_asserted_during_program(dut):
    """The device reports busy, and WEL is consumed by the operation."""
    flash = await setup(dut)
    await flash.write_enable()
    await flash.master.start()
    await flash.master.send_byte(0x02, lanes=1)
    await flash.master.send_address(0x000030, lanes=1)
    await flash.master.send_byte(0x5A, lanes=1)
    await flash.master.stop()

    assert await flash.read_status() & STATUS_WIP, "WIP not set after program"
    await flash.wait_ready()
    status = await flash.read_status()
    assert not status & STATUS_WIP
    assert not status & STATUS_WEL, "WEL should be consumed by the program"
    assert await flash.read_byte(0x000030) == 0x5A


@cocotb.test()
async def test_page_program_multiple_bytes(dut):
    """A page program writes a run of bytes."""
    flash = await setup(dut)
    payload = [0x11, 0x22, 0x33, 0x44, 0x55]
    await flash.program(0x000040, payload)
    assert await flash.read(0x000040, len(payload)) == payload


@cocotb.test()
async def test_all_read_widths_agree(dut):
    """Single, dual, quad and octal I/O return the same bytes."""
    flash = await setup(dut)
    payload = [0x00, 0x0F, 0xF0, 0xA5, 0x5A, 0x81]
    await flash.program(0x000050, payload)

    for opcode in READ_OPCODES:
        got = await flash.read(0x000050, len(payload), opcode=opcode)
        assert got == payload, f"{NAMES[opcode]}: {[hex(b) for b in got]}"


@cocotb.test()
async def test_sector_erase_spans_the_sector(dut):
    """Erase clears its whole 4 KB sector and leaves the next one alone."""
    flash = await setup(dut)
    await flash.program(0x000000, 0x11)
    await flash.program(0x000FFF, 0x22)
    await flash.program(0x001000, 0x33)

    await flash.erase_sector(0x000000)

    assert await flash.read_byte(0x000000) == 0xFF
    assert await flash.read_byte(0x000FFF) == 0xFF
    assert await flash.read_byte(0x001000) == 0x33, "erase crossed the sector"


@cocotb.test()
async def test_reads_auto_increment(dut):
    """A read streams consecutive addresses."""
    flash = await setup(dut)
    payload = [0xDE, 0xAD, 0xBE, 0xEF]
    await flash.program(0x000060, payload)
    assert await flash.read(0x000060, 4) == payload


@cocotb.test()
async def test_hold_preserves_state(dut):
    """Data survives a hold, and the device works again afterwards."""
    flash = await setup(dut)
    await flash.program(0x000070, 0xC5)

    await flash.hold()
    await flash.release_hold()

    assert await flash.read_byte(0x000070) == 0xC5
    await flash.erase_sector(0x000070)
    await flash.program(0x000070, 0xC6)
    assert await flash.read_byte(0x000070, opcode=CMD_OIOR) == 0xC6
