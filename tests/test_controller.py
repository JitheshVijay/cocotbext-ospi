"""The controller as DUT: real RTL driving a real flash model.

Everything else in this project drives a flash model from Python. Here the
RTL does the driving and cocotb only pokes its command interface -- it never
touches the flash pins. If the controller gets a phase wrong, the bytes come
back wrong, and nothing in Python can paper over it.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from cocotbext.ospi.devices import MX25UM51345G, CR2_MODE, CR2_MODE_SOPI

# Lane counts the controller understands.
SINGLE, OCTAL = 1, 8


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.cmd_valid.value = 0
    dut.cmd_has_ext.value = 0
    dut.cmd_ext.value = 0
    dut.cmd_addr.value = 0
    dut.cmd_addr_bytes.value = 0
    dut.cmd_dummy.value = 0
    dut.cmd_lanes.value = SINGLE
    dut.cmd_cmd_lanes.value = SINGLE
    dut.cmd_is_read.value = 0
    dut.cmd_len.value = 0
    dut.wdata.value = 0
    dut.rst_n.value = 0
    await Timer(50, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # Resetting the controller says nothing about the flash, which keeps
    # whatever mode the last test left it in. Send RSTEN/RST both ways --
    # single-lane, then octal with the extension byte -- so whichever the
    # part is actually in takes effect and the other is ignored as
    # malformed. Without this a test inherits the previous one's protocol.
    for lanes, ext_rsten, ext_rst in ((SINGLE, None, None),
                                      (OCTAL, 0x99, 0x66)):
        await command(dut, 0x66, ext=ext_rsten, lanes=lanes)
        await command(dut, 0x99, ext=ext_rst, lanes=lanes)


async def command(dut, opcode, *, ext=None, address=0, addr_bytes=0,
                  dummy=0, lanes=SINGLE, cmd_lanes=None, read=0, write=(),
                  timeout_ns=200_000):
    """Issue one command through the controller and collect any read data.

    ``cmd_lanes`` is how wide the opcode phase is, which is not always the
    same as the data phase: a 1-4-4 read keeps the opcode on one lane, while
    in 8-8-8 the opcode widens with everything else. Defaults to matching
    ``lanes``, which is what an octal part wants.
    """
    dut.cmd_opcode.value = opcode
    dut.cmd_ext.value = 0 if ext is None else ext
    dut.cmd_has_ext.value = 0 if ext is None else 1
    dut.cmd_addr.value = address
    dut.cmd_addr_bytes.value = addr_bytes
    dut.cmd_dummy.value = dummy
    dut.cmd_lanes.value = lanes
    dut.cmd_cmd_lanes.value = lanes if cmd_lanes is None else cmd_lanes
    dut.cmd_is_read.value = 1 if read else 0
    dut.cmd_len.value = read if read else len(write)

    payload = list(write)
    if payload:
        dut.wdata.value = payload[0]

    while not dut.cmd_ready.value:
        await RisingEdge(dut.clk)
    dut.cmd_valid.value = 1
    await RisingEdge(dut.clk)
    dut.cmd_valid.value = 0

    got, index = [], 1
    elapsed = 0
    while True:
        await RisingEdge(dut.clk)
        elapsed += 10
        if dut.rdata_valid.value:
            got.append(int(dut.rdata.value))
        if dut.wdata_next.value and index < len(payload):
            dut.wdata.value = payload[index]
            index += 1
        if dut.done.value:
            break
        if elapsed > timeout_ns:
            raise TimeoutError(
                f"controller never raised done for opcode {opcode:#04x} "
                f"(state stuck, got {len(got)}/{read} bytes)"
            )
    return got


@cocotb.test()
async def test_controller_reads_the_jedec_id(dut):
    """The simplest possible round trip: RDID over one lane."""
    await reset(dut)
    ident = await command(dut, 0x9F, read=3)
    assert ident == [0xC2, 0x81, 0x3A], f"got {[hex(b) for b in ident]}"


@cocotb.test()
async def test_controller_reads_status(dut):
    """RDSR returns a byte with WIP and WEL clear on an idle part."""
    await reset(dut)
    status = await command(dut, 0x05, read=1)
    assert status[0] & 0x03 == 0, f"status {status[0]:#04x} on an idle part"


@cocotb.test()
async def test_controller_write_enable_sets_wel(dut):
    """A command with no address or data still has to be framed correctly."""
    await reset(dut)
    assert (await command(dut, 0x05, read=1))[0] & 0x02 == 0

    await command(dut, 0x06)                     # WREN
    assert (await command(dut, 0x05, read=1))[0] & 0x02, "WEL not set"

    await command(dut, 0x04)                     # WRDI
    assert (await command(dut, 0x05, read=1))[0] & 0x02 == 0


@cocotb.test()
async def test_controller_program_and_read_back(dut):
    """Program through the RTL and read it back through the RTL.

    Exercises every phase the controller has: opcode, 4-byte address and a
    data payload out, then opcode, address and data in.
    """
    await reset(dut)
    payload = [0xDE, 0xAD, 0xBE, 0xEF]

    await command(dut, 0x06)                                   # WREN
    await command(dut, 0x12, address=0x00000100, addr_bytes=4,
                  write=payload)                               # PP4B

    # Poll WIP through the controller until the program finishes.
    for _ in range(500):
        if not (await command(dut, 0x05, read=1))[0] & 0x01:
            break
    else:
        raise TimeoutError("WIP never cleared")

    got = await command(dut, 0x13, address=0x00000100, addr_bytes=4,
                        read=len(payload))                     # READ4B
    assert got == payload, f"got {[hex(b) for b in got]}"


@cocotb.test()
async def test_controller_sector_erase(dut):
    """Erase through the RTL and see the sector come back blank."""
    await reset(dut)

    await command(dut, 0x06)
    await command(dut, 0x12, address=0x00000200, addr_bytes=4, write=[0x5A])
    for _ in range(500):
        if not (await command(dut, 0x05, read=1))[0] & 0x01:
            break
    assert (await command(dut, 0x13, address=0x00000200,
                          addr_bytes=4, read=1)) == [0x5A]

    await command(dut, 0x06)
    await command(dut, 0x21, address=0x00000200, addr_bytes=4)  # SE4B
    for _ in range(2000):
        if not (await command(dut, 0x05, read=1))[0] & 0x01:
            break
    else:
        raise TimeoutError("WIP never cleared after erase")

    assert (await command(dut, 0x13, address=0x00000200,
                          addr_bytes=4, read=1)) == [0xFF]


@cocotb.test()
async def test_controller_reads_sfdp_with_dummy_cycles(dut):
    """RDSFDP needs 8 dummy cycles: the controller has to hold the bus.

    A controller that skips the dummy phase reads the signature shifted and
    gets nothing recognisable, so this is a real check of that phase.
    """
    await reset(dut)
    sfdp = await command(dut, 0x5A, address=0, addr_bytes=3, dummy=8, read=8)
    assert bytes(sfdp[:4]) == b"SFDP", f"got {bytes(sfdp[:4])!r}"


@cocotb.test()
async def test_controller_switches_the_part_to_octal_and_reads(dut):
    """The full bring-up, done in RTL.

    Write CR2 over one lane to put the part in octal, then talk to it over
    eight with a two-byte command. This is where a controller that widens
    the opcode instead of keeping it single-lane falls over.
    """
    await reset(dut)

    # Park known data while still in single-lane mode.
    await command(dut, 0x06)
    await command(dut, 0x12, address=0x00000300, addr_bytes=4,
                  write=[0xC0, 0xDE])
    for _ in range(500):
        if not (await command(dut, 0x05, read=1))[0] & 0x01:
            break

    # CR2[0x00000000] = SOPI.
    await command(dut, 0x72, address=CR2_MODE, addr_bytes=4,
                  write=[CR2_MODE_SOPI])

    # Now octal: every command carries its complement as an extension.
    ident = await command(dut, 0x9F, ext=0x60, address=0, addr_bytes=4,
                          dummy=4, lanes=OCTAL, read=3)
    assert ident == [0xC2, 0x81, 0x3A], f"octal RDID gave {[hex(b) for b in ident]}"

    got = await command(dut, 0xEC, ext=0x13, address=0x00000300,
                        addr_bytes=4, dummy=20, lanes=OCTAL, read=2)
    assert got == [0xC0, 0xDE], f"octal read gave {[hex(b) for b in got]}"


@cocotb.test()
async def test_controller_rejects_nothing_it_should_accept(dut):
    """Every command leaves the controller ready for the next one.

    A state machine that fails to return to idle hangs the next command, so
    run a mixed sequence and check the handshake keeps working.
    """
    await reset(dut)
    for _ in range(3):
        assert (await command(dut, 0x9F, read=3)) == [0xC2, 0x81, 0x3A]
        await command(dut, 0x06)
        await command(dut, 0x04)
        assert len(await command(dut, 0x05, read=1)) == 1
    assert dut.cmd_ready.value, "controller did not return to idle"
