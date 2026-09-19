"""Drive one clean transaction of each kind so the waveforms can be captured.

Kept deliberately minimal -- the test suite covers behaviour; this exists
only so docs/waveforms/render.py has a short, legible VCD to draw from.
"""

import cocotb
from cocotb.clock import Clock

from cocotbext.ospi import OspiFlash, CMD_READ, CMD_DIOR, CMD_QIOR, CMD_OIOR


@cocotb.test()
async def capture(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    flash = OspiFlash(dut)
    await flash.initialize()

    # A program, so the status poll has a real WIP to report.
    await flash.program(0x000010, 0xA5)

    # The same byte at each width, for the side-by-side comparison.
    for opcode in (CMD_READ, CMD_DIOR, CMD_QIOR, CMD_OIOR):
        await flash.read(0x000010, 1, opcode=opcode)
