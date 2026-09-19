"""Interop: drive PicoSoC's spiflash.v, a model this project did not write.

Passing here means the driver speaks real SPI flash protocol -- single-lane
command phase, 24-bit address, mode byte, dummy cycles -- rather than only
agreeing with our own model.

spiflash.v is a four-lane part, so this covers the single, dual and quad
paths. The octal path has no independent model to check against.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from cocotbext.ospi import OspiBus, OspiMaster

# Matches tests/reference/firmware.hex.
EXPECTED = [(0xA0 + i) & 0xFF for i in range(16)] + \
           [(i * 7 + 3) & 0xFF for i in range(240)]

CMD_RELEASE_POWER_DOWN = 0xAB
CMD_READ = 0x03
CMD_DIOR = 0xBB
CMD_QIOR = 0xEB

# spiflash.v uses `localparam integer latency = 8`.
DUMMY_CYCLES = 8


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    bus = OspiBus(clk=dut.clk, cs=dut.csb, io=dut.io,
                  io_out=dut.io_out, io_oe=dut.io_oe, hold=dut.HOLD_N)
    master = OspiMaster(bus)

    dut.io_oe.value = 0
    dut.io_out.value = 0
    dut.HOLD_N.value = 1

    # spiflash.v initialises its mode and counters from a chip-select edge,
    # and a value set in a declaration produces no edge.
    dut.csb.value = 1
    await RisingEdge(dut.clk)
    dut.csb.value = 0
    await RisingEdge(dut.clk)
    dut.csb.value = 1
    await RisingEdge(dut.clk)

    # The model ignores reads until brought out of power-down.
    await master.start()
    await master.send_byte(CMD_RELEASE_POWER_DOWN, lanes=1)
    await master.stop()
    return master


async def read_wide(master, opcode, lanes, address, count):
    await master.start()
    await master.send_byte(opcode, lanes=1)
    await master.send_address(address, lanes=lanes)
    if lanes > 1:
        await master.send_byte(0x00, lanes=lanes)   # mode byte
        await master.dummy_cycles(DUMMY_CYCLES)
    data = await master.recv_bytes(count, lanes=lanes)
    await master.stop()
    return data


@cocotb.test()
async def test_single_lane_read(dut):
    """0x03: command, address and data all on one lane, no dummy cycles."""
    master = await setup(dut)
    got = await read_wide(master, CMD_READ, 1, 0x000000, 8)
    assert got == EXPECTED[:8], f"got {[hex(b) for b in got]}"


@cocotb.test()
async def test_single_lane_read_at_offset(dut):
    """The address actually selects where the read starts."""
    master = await setup(dut)
    got = await read_wide(master, CMD_READ, 1, 0x000010, 8)
    assert got == EXPECTED[0x10:0x18], f"got {[hex(b) for b in got]}"


@cocotb.test()
async def test_dual_io_read(dut):
    """0xBB: single-lane command, then two lanes for address and data."""
    master = await setup(dut)
    got = await read_wide(master, CMD_DIOR, 2, 0x000000, 8)
    assert got == EXPECTED[:8], f"got {[hex(b) for b in got]}"


@cocotb.test()
async def test_quad_io_read(dut):
    """0xEB: single-lane command, then four lanes for address and data."""
    master = await setup(dut)
    got = await read_wide(master, CMD_QIOR, 4, 0x000000, 8)
    assert got == EXPECTED[:8], f"got {[hex(b) for b in got]}"


@cocotb.test()
async def test_all_widths_agree(dut):
    """The same bytes come back whichever width they are read at."""
    master = await setup(dut)
    address = 0x000020
    single = await read_wide(master, CMD_READ, 1, address, 4)
    dual = await read_wide(master, CMD_DIOR, 2, address, 4)
    quad = await read_wide(master, CMD_QIOR, 4, address, 4)
    assert single == dual == quad == EXPECTED[0x20:0x24]
