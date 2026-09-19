"""Macronix MX25UM51345G: behaviour taken from the datasheet.

These check the things that differ between a real octal part and a generic
octal memory -- the CR2 mode switch, the inverted command extension, the
address phase and dummy cycles that register reads grow in OPI, and the
configurable array dummy cycles.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Edge, Timer

from cocotbext.ospi.devices import (
    MX25UM51345G, CR2_MODE, CR2_DUMMY, CR2_MODE_SOPI, CR2_MODE_SPI,
    DUMMY_CYCLES, PROTO_1S_1S_1S, PROTO_8S_8S_8S, PROTO_8D_8D_8D,
    CR2_MODE_DOPI, CR2_DQS, CR2_DQS_DOS,
    SCUR_WPSEL, SCUR_E_FAIL, SCUR_P_FAIL, SCUR_ESB, SCUR_PSB,
)
from cocotbext.ospi.sfdp import (
    FOURBAIT_READ, FOURBAIT_PP, FOURBAIT_READ_1_4_4,
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


# ── xSPI Profile 1.0 (JESD251) ───────────────────────────────────────

@cocotb.test()
async def test_profile1_is_advertised(dut):
    """The part carries an xSPI Profile 1.0 table describing its octal DTR."""
    flash = await setup(dut)
    info = await flash.discover()

    assert info.supports_octal_dtr
    assert [hex(h.param_id) for h in info.headers] == [
        "0xff00", "0xff05", "0xff84",
    ]
    # 8DTRD is the DTR octal read.
    assert info.octal_dtr_read_opcode == 0xEE
    # RDSR grows a 4-byte address and 4 dummy cycles in OPI.
    assert info.rdsr_dummy == 4
    assert info.rdsr_addr_bytes == 4


@cocotb.test()
async def test_profile1_matches_the_profile_we_ship(dut):
    """What the part advertises agrees with the profile we drive it by.

    If these ever disagree, one of them is wrong -- and a controller that
    trusted SFDP would be reading with the wrong opcode or dummy count.
    """
    flash = await setup(dut)
    info = await flash.discover()

    assert info.octal_dtr_read_opcode == MX25UM51345G.ops["8DTRD"].opcode
    rdsr = MX25UM51345G.ops["RDSR"]
    assert info.rdsr_dummy == rdsr.opi_dummy
    assert info.rdsr_addr_bytes == rdsr.opi_addr_bytes


@cocotb.test()
async def test_configure_octal_dtr_purely_from_sfdp(dut):
    """Drive the part using only what it told us about itself.

    No profile constants: the opcode and dummy count come from the Profile
    1.0 table, which is how a controller handles a flash it has no entry
    for. The read has to actually work afterwards.
    """
    flash = await setup(dut)
    info = await flash.configure_from_sfdp(mhz=200)
    assert info.octal_dtr_dummy[200] == 20

    await flash.enter_octal(PROTO_8D_8D_8D)
    await flash.program(0x00000400, [0x5E, 0xED])
    assert await flash.read(0x00000400, 2) == [0x5E, 0xED]


@cocotb.test()
async def test_advertised_dummy_cycles_really_work(dut):
    """Each frequency bin's advertised count is one the part accepts.

    The Profile table quotes a count per speed; if any of them were wrong a
    controller running at that speed would read garbage. Walk them all,
    program CR2 to match, and check the data still comes back.
    """
    flash = await setup(dut)
    info = await flash.discover()
    await flash.enter_octal(PROTO_8D_8D_8D)
    await flash.program(0x00000500, [0xAB, 0xCD])

    # CR2 DC[2:0] -> cycle count, from the datasheet table.
    bits_for_cycles = {cycles: bits for bits, cycles in DUMMY_CYCLES.items()}

    for mhz in sorted(info.octal_dtr_dummy, reverse=True):
        cycles = info.octal_dtr_dummy[mhz]
        assert cycles in bits_for_cycles, (
            f"{mhz} MHz advertises {cycles} dummy cycles, which CR2 cannot "
            f"express (DC table has {sorted(bits_for_cycles)})"
        )
        await flash.write_register(CR2_DUMMY, bits_for_cycles[cycles])
        MX25UM51345G.ops["8DTRD"].opi_dummy = cycles

        got = await flash.read(0x00000500, 2)
        assert got == [0xAB, 0xCD], f"{mhz} MHz / {cycles} dummy: got {got}"

    # Restore both sides.
    await flash.write_register(CR2_DUMMY, 0b000)
    MX25UM51345G.ops["8DTRD"].opi_dummy = DUMMY_CYCLES[0b000]


# ── security register and advanced sector protection ─────────────────

@cocotb.test()
async def test_security_register_defaults(dut):
    """Out of reset nothing is failed, suspended or locked."""
    flash = await setup(dut)
    scur = await flash.read_security()

    assert not scur & SCUR_WPSEL, "should start in BP protection mode"
    assert not scur & (SCUR_E_FAIL | SCUR_P_FAIL)
    assert not scur & (SCUR_ESB | SCUR_PSB)


@cocotb.test()
async def test_wpsel_switches_to_advanced_protection(dut):
    """WPSEL sets the mode bit, and needs WEL like any other write."""
    flash = await setup(dut)

    # Without WEL it does nothing.
    await flash._transfer("WPSEL")
    assert not await flash.read_security() & SCUR_WPSEL

    await flash.enable_advanced_protection()
    assert await flash.read_security() & SCUR_WPSEL


@cocotb.test()
async def test_protected_sector_refuses_program_and_says_so(dut):
    """A DPB-protected sector fails the program and reports P_FAIL.

    Reporting matters more than refusing: a controller that only checks WIP
    sees a clean completion and believes the write landed.
    """
    flash = await setup(dut)
    await flash.enable_advanced_protection()
    await flash.write_protection_bit(0x00000000, True)
    assert await flash.read_protection_bit(0x00000000)

    await flash.program(0x00000000, [0xA5], wait=False)
    scur = await flash.read_security()

    assert scur & SCUR_P_FAIL, "protected program did not set P_FAIL"
    assert await flash.read_byte(0x00000000) == 0xFF, "protected sector changed"


@cocotb.test()
async def test_protected_sector_refuses_erase(dut):
    """A protected sector fails the erase and reports E_FAIL."""
    flash = await setup(dut)
    await flash.program(0x00002000, [0x5A])
    assert await flash.read_byte(0x00002000) == 0x5A

    await flash.enable_advanced_protection()
    await flash.write_protection_bit(0x00002000, True)

    await flash.erase_sector(0x00002000, wait=False)
    assert await flash.read_security() & SCUR_E_FAIL
    assert await flash.read_byte(0x00002000) == 0x5A, "protected sector erased"


@cocotb.test()
async def test_clearing_protection_lets_the_write_through(dut):
    """Dropping the DPB restores normal programming."""
    flash = await setup(dut)
    await flash.enable_advanced_protection()
    await flash.write_protection_bit(0x00003000, True)

    await flash.program(0x00003000, [0x11], wait=False)
    assert await flash.read_byte(0x00003000) == 0xFF

    await flash.write_protection_bit(0x00003000, False)
    assert not await flash.read_protection_bit(0x00003000)

    await flash.program(0x00003000, [0x11])
    assert await flash.read_byte(0x00003000) == 0x11


# ── program / erase suspend and resume ───────────────────────────────

@cocotb.test()
async def test_erase_suspend_and_resume(dut):
    """Suspend stops an erase mid-flight; resume finishes it."""
    flash = await setup(dut)
    await flash.program(0x00004000, [0xC3])

    # Start the erase but do not wait for it.
    await flash.erase_sector(0x00004000, wait=False)
    await flash.suspend()

    scur = await flash.read_security()
    assert scur & SCUR_ESB, "ESB not set after suspending an erase"
    assert not await flash.read_status() & STATUS_WIP, \
        "a suspended part should report ready"
    # The erase has not finished, so the byte is still there.
    assert await flash.read_byte(0x00004000) == 0xC3

    await flash.resume()
    assert not await flash.read_security() & SCUR_ESB
    await flash.wait_ready()
    assert await flash.read_byte(0x00004000) == 0xFF


@cocotb.test()
async def test_program_suspend_sets_psb_not_esb(dut):
    """Suspending a program sets PSB; the two are distinguishable."""
    flash = await setup(dut)

    await flash.program(0x00005000, [0x3C], wait=False)
    await flash.suspend()

    scur = await flash.read_security()
    assert scur & SCUR_PSB, "PSB not set after suspending a program"
    assert not scur & SCUR_ESB, "a program suspend must not set ESB"

    await flash.resume()
    await flash.wait_ready()
    assert await flash.read_byte(0x00005000) == 0x3C


@cocotb.test()
async def test_program_is_rejected_during_erase_suspend(dut):
    """Datasheet Table 7: PP is not an acceptable command while suspended.

    Some parts allow program-during-erase-suspend and some do not. This one
    does not, and a controller written against a part that does would
    silently lose the write.
    """
    flash = await setup(dut)
    await flash.erase_sector(0x00006000, wait=False)
    await flash.suspend()
    assert await flash.read_security() & SCUR_ESB

    await flash.program(0x00006000, [0x77], wait=False)
    assert await flash.read_byte(0x00006000) == 0xFF, \
        "page program was honoured during an erase suspend"

    await flash.resume()
    await flash.wait_ready()


@cocotb.test()
async def test_reads_are_allowed_during_suspend(dut):
    """Reads and status polls are on Table 7's acceptable list."""
    flash = await setup(dut)
    await flash.program(0x00007000, [0xBE, 0xEF])

    await flash.erase_sector(0x00007000, wait=False)
    await flash.suspend()

    assert await flash.read(0x00007000, 2) == [0xBE, 0xEF]
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]

    await flash.resume()
    await flash.wait_ready()
    assert await flash.read(0x00007000, 2) == [0xFF, 0xFF]


# ── 4-byte address instruction table ─────────────────────────────────

@cocotb.test()
async def test_4bait_advertises_four_byte_instructions(dut):
    """The part says which instructions take a 4-byte address.

    It is a 4-byte-only device, so this is not optional detail: without the
    table a controller has to guess whether to convert 3-byte opcodes, and
    guessing wrong reads the wrong address.
    """
    flash = await setup(dut)
    info = await flash.discover()

    assert info.fourbait is not None, "no 4BAIT table"
    assert info.supports_4byte(FOURBAIT_READ)
    assert info.supports_4byte(FOURBAIT_PP)
    assert not info.supports_4byte(FOURBAIT_READ_1_4_4), \
        "this part has no quad 1-4-4 read"


@cocotb.test()
async def test_4bait_erase_opcodes_match_the_bfpt(dut):
    """The 4-byte erase opcodes agree with the BFPT's erase types.

    Two tables describing the same thing is a chance for them to disagree;
    a controller reading either must land on the same opcode.
    """
    flash = await setup(dut)
    info = await flash.discover()

    from_bfpt = sorted(op for _, op in info.erase_types)
    from_4bait = sorted(info.fourbait_erase_opcodes)
    assert from_bfpt == from_4bait == [0x21, 0xDC]


@cocotb.test()
async def test_4bait_opcodes_are_the_ones_that_work(dut):
    """The advertised erase opcode actually erases.

    Closes the loop: the table says 0x21, so drive 0x21 and check it does
    what it claims.
    """
    flash = await setup(dut)
    info = await flash.discover()
    sector_erase = min(info.fourbait_erase_opcodes)
    assert sector_erase == MX25UM51345G.ops["SE"].opcode

    await flash.program(0x00008000, [0x42])
    assert await flash.read_byte(0x00008000) == 0x42
    await flash.erase_sector(0x00008000)
    assert await flash.read_byte(0x00008000) == 0xFF


# ── DQS read data strobe ─────────────────────────────────────────────

async def _dqs_toggles_during(flash, dut, read_coro):
    """Run a read and report whether DQS toggled while it happened."""
    seen = set()

    async def watch():
        while True:
            await Edge(dut.clk)
            seen.add(str(dut.dqs.value))

    task = cocotb.start_soon(watch())
    result = await read_coro
    task.kill()
    return result, seen


@cocotb.test()
async def test_dqs_is_parked_low_when_idle(dut):
    """DQS sits low outside a read, so a controller can gate on it."""
    flash = await setup(dut)
    await Timer(100, unit="ns")
    assert str(dut.dqs.value) == "0"


@cocotb.test()
async def test_dqs_toggles_during_a_dtr_read(dut):
    """In DTR the device strobes DQS alongside the data it returns.

    This is what lets a controller capture with the data rather than with
    its own clock -- the whole reason the pin exists.
    """
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8D_8D_8D)
    await flash.program(0x00009000, [0xA1, 0xB2])

    data, seen = await _dqs_toggles_during(
        flash, dut, flash.read(0x00009000, 2)
    )
    assert data == [0xA1, 0xB2]
    assert seen >= {"0", "1"}, f"DQS never toggled during a DTR read: {seen}"


@cocotb.test()
async def test_dqs_is_quiet_in_plain_spi(dut):
    """No strobe in single-lane SPI: DQS is an octal-mode feature."""
    flash = await setup(dut)
    await flash.program(0x0000A000, [0xC3])

    data, seen = await _dqs_toggles_during(
        flash, dut, flash.read(0x0000A000, 1)
    )
    assert data == [0xC3]
    assert seen == {"0"}, f"DQS toggled outside octal mode: {seen}"


@cocotb.test()
async def test_dos_bit_gates_dqs_in_str_octal(dut):
    """In STR octal the strobe is opt-in, via CR2[0x200] bit 1 (DOS).

    DTR always strobes; STR does not unless asked. A controller that
    enables DQS capture without setting DOS waits for edges that never come.
    """
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8S_8S_8S)
    await flash.program(0x0000B000, [0xD4])

    # Default: DOS clear, so no strobe.
    _, quiet = await _dqs_toggles_during(flash, dut, flash.read(0x0000B000, 1))
    assert quiet == {"0"}, f"DQS toggled in STR with DOS clear: {quiet}"

    await flash.write_register(CR2_DQS, CR2_DQS_DOS)
    assert await flash.read_register(CR2_DQS) == CR2_DQS_DOS

    data, busy = await _dqs_toggles_during(flash, dut, flash.read(0x0000B000, 1))
    assert data == [0xD4]
    assert busy >= {"0", "1"}, f"DOS set but DQS stayed quiet: {busy}"

    await flash.write_register(CR2_DQS, 0x00)
