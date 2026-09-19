"""Micron MT35XU512ABA in 8D-8D-8D.

These cover what makes this part different from the Macronix one: the
repeated (not inverted) command extension, CFR0V/CFR1V rather than CR2, and
double transfer rate.
"""

import cocotb
from cocotb.clock import Clock

from cocotbext.ospi.devices import (
    MT35XU512ABA, MX25UM51345G,
    CFR0V, CFR1V, CFR0V_OCTAL_DTR, CFR0V_EXT_SPI, OCTAL_DTR_DUMMY,
    FSR_READY, FSR_E_ERR, FSR_P_ERR, FSR_PT_ERR,
    PROTO_1S_1S_1S, PROTO_8D_8D_8D,
)
from cocotbext.ospi.xspi_flash import XspiFlash, STATUS_WEL, STATUS_WIP


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    flash = XspiFlash(dut, MT35XU512ABA)
    await flash.initialize()
    return flash


@cocotb.test()
async def test_boots_in_extended_spi(dut):
    """The part comes up single-lane and identifies itself there."""
    flash = await setup(dut)
    assert flash.protocol == PROTO_1S_1S_1S
    assert await flash.read_id() == [0x2C, 0x5B, 0x1A]


@cocotb.test()
async def test_cfr0v_defaults_to_extended_spi(dut):
    """CFR0V reads 0xFF out of reset."""
    flash = await setup(dut)
    assert await flash.read_register(CFR0V) == CFR0V_EXT_SPI


@cocotb.test()
async def test_enter_octal_dtr_and_identify(dut):
    """Writing CFR1V then CFR0V switches to 8D-8D-8D; the ID still reads.

    This exercises the whole DTR path at once: a two-byte command with a
    repeated extension, a 4-byte address, 8 dummy cycles, and data clocked
    on both edges.
    """
    flash = await setup(dut)
    await flash.enter_octal(PROTO_8D_8D_8D)
    assert flash.protocol == PROTO_8D_8D_8D
    assert flash.dtr
    assert await flash.read_id() == [0x2C, 0x5B, 0x1A]


@cocotb.test()
async def test_dummy_cycles_were_programmed_first(dut):
    """CFR1V holds the array-read dummy count the driver then relies on."""
    flash = await setup(dut)
    await flash.enter_octal()
    assert await flash.read_register(CFR1V) == OCTAL_DTR_DUMMY
    assert await flash.read_register(CFR0V) == CFR0V_OCTAL_DTR


@cocotb.test()
async def test_extension_is_repeat_not_invert(dut):
    """Micron repeats the opcode; the Macronix complement is rejected.

    The two profiles disagree here on purpose -- it is the most likely thing
    to be wrong in a controller ported between the vendors.

    As above, rejection is the model's choice rather than a documented
    silicon behaviour.
    """
    flash = await setup(dut)
    await flash.enter_octal()

    wren = MT35XU512ABA.ops["WREN"]
    assert MT35XU512ABA.extension(wren.opcode) == wren.opcode
    assert MX25UM51345G.extension(wren.opcode) == (~wren.opcode) & 0xFF

    # Send WREN with the *inverted* extension a Macronix part would want.
    await flash.master.start()
    await flash.master.send_byte_dtr(wren.opcode, lanes=8)
    await flash.master.send_byte_dtr((~wren.opcode) & 0xFF, lanes=8)
    await flash.master.stop()

    assert not await flash.read_status() & STATUS_WEL, \
        "WREN honoured despite a Macronix-style inverted extension"

    # The repeated extension works.
    await flash.write_enable()
    assert await flash.read_status() & STATUS_WEL


@cocotb.test()
async def test_program_and_read_in_octal_dtr(dut):
    """Program and read back over the DTR octal bus."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.program(0x00000010, [0xA5, 0x5A, 0x81, 0x18])
    assert await flash.read(0x00000010, 4) == [0xA5, 0x5A, 0x81, 0x18]


@cocotb.test()
async def test_program_requires_write_enable(dut):
    """Page program with no WEL is ignored."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash._transfer("PP", address=0x00000020, write=[0x11, 0x22])
    assert await flash.read(0x00000020, 2) == [0xFF, 0xFF]


@cocotb.test()
async def test_program_clears_bits_only(dut):
    """NOR programming can clear bits but never set them."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.program(0x00000030, [0xF0, 0xFF])
    assert await flash.read(0x00000030, 2) == [0xF0, 0xFF]

    await flash.program(0x00000030, [0x0F, 0x0F])
    assert await flash.read(0x00000030, 2) == [0x00, 0x0F]

    await flash.erase_sector(0x00000030)
    assert await flash.read(0x00000030, 2) == [0xFF, 0xFF]


@cocotb.test()
async def test_wip_is_set_during_program(dut):
    """The part reports busy, and the program consumes WEL."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.write_enable()
    await flash._transfer("PP", address=0x00000040, write=[0x5A, 0xA5])

    assert await flash.read_status() & STATUS_WIP
    await flash.wait_ready()

    status = await flash.read_status()
    assert not status & STATUS_WIP
    assert not status & STATUS_WEL
    assert await flash.read(0x00000040, 2) == [0x5A, 0xA5]


@cocotb.test()
async def test_leaving_octal_writes_two_registers_at_once(dut):
    """8D-8D-8D cannot move an odd number of bytes.

    Eight lanes on both edges carry two bytes per clock, so returning to
    extended SPI writes CFR0V and CFR1V together -- which is exactly what
    Linux does, and for this reason.
    """
    flash = await setup(dut)
    await flash.enter_octal()
    assert await flash.read_id() == [0x2C, 0x5B, 0x1A]

    await flash.exit_octal()
    assert flash.protocol == PROTO_1S_1S_1S
    assert not flash.dtr
    assert await flash.read_id() == [0x2C, 0x5B, 0x1A]
    assert await flash.read_register(CFR0V) == CFR0V_EXT_SPI


@cocotb.test()
async def test_sector_erase_spans_the_sector(dut):
    """Erase clears its whole 4 KB sector and leaves the next alone."""
    flash = await setup(dut)
    await flash.enter_octal()

    await flash.program(0x00000000, [0x11, 0x11])
    await flash.program(0x00000FFE, [0x22, 0x22])
    await flash.program(0x00001000, [0x33, 0x33])

    await flash.erase_sector(0x00000000)

    assert await flash.read(0x00000000, 2) == [0xFF, 0xFF]
    assert await flash.read(0x00000FFE, 2) == [0xFF, 0xFF]
    assert await flash.read(0x00001000, 2) == [0x33, 0x33]


# ── SFDP ─────────────────────────────────────────────────────────────

@cocotb.test()
async def test_sfdp_in_extended_spi(dut):
    """The part describes itself before anything is configured."""
    flash = await setup(dut)
    info = await flash.discover()

    assert info.density_bits == 512 * 1024 * 1024
    assert info.size_bytes == 64 * 1024 * 1024
    assert info.address_bytes_name == "4 only"
    assert info.dtr
    assert info.page_size == 256


@cocotb.test()
async def test_sfdp_matches_the_jedec_id_density(dut):
    """SFDP density and the ID's capacity byte tell the same story."""
    flash = await setup(dut)
    ident = await flash.read_id()
    info = await flash.discover()

    assert ident == [0x2C, 0x5B, 0x1A]
    # 0x1A is the 512 Mb capacity code for this family.
    assert info.density_bits == 512 * 1024 * 1024


@cocotb.test()
async def test_sfdp_survives_the_mode_switch(dut):
    """RDSFDP works in octal DTR too, with its different shape."""
    flash = await setup(dut)
    in_spi = await flash.read_sfdp(64)

    await flash.enter_octal()
    in_octal = await flash.read_sfdp(64)

    assert in_spi == in_octal, "SFDP differs between extended SPI and octal"
    assert in_spi[:4] == b"SFDP"


@cocotb.test()
async def test_software_reset_returns_to_extended_spi(dut):
    """RSTEN then RST drops the part back to one lane."""
    flash = await setup(dut)
    await flash.enter_octal()
    assert await flash.read_id() == [0x2C, 0x5B, 0x1A]

    await flash.reset()
    assert flash.protocol == PROTO_1S_1S_1S
    assert await flash.read_id() == [0x2C, 0x5B, 0x1A]
    assert await flash.read_register(CFR0V) == CFR0V_EXT_SPI


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
    assert info.octal_dtr_read_opcode == 0xFD
    # Micron's RDSR takes no address bytes but 8 dummy cycles -- the exact
    # opposite shape to the Macronix part, and both are advertised.
    assert info.rdsr_dummy == 8
    assert info.rdsr_addr_bytes == 0


@cocotb.test()
async def test_profile1_matches_the_profile_we_ship(dut):
    """What the part advertises agrees with the profile we drive it by."""
    flash = await setup(dut)
    info = await flash.discover()

    assert info.octal_dtr_read_opcode == MT35XU512ABA.ops["8READ"].opcode
    rdsr = MT35XU512ABA.ops["RDSR"]
    assert info.rdsr_dummy == rdsr.opi_dummy
    assert info.rdsr_addr_bytes == (rdsr.opi_addr_bytes or 0)


@cocotb.test()
async def test_configure_octal_dtr_purely_from_sfdp(dut):
    """Drive the part using only what it told us about itself."""
    flash = await setup(dut)
    info = await flash.configure_from_sfdp(mhz=200)
    assert info.octal_dtr_dummy[200] == OCTAL_DTR_DUMMY

    await flash.enter_octal()
    await flash.program(0x00000400, [0x5E, 0xED])
    assert await flash.read(0x00000400, 2) == [0x5E, 0xED]


@cocotb.test()
async def test_the_two_vendors_advertise_different_rdsr_shapes(dut):
    """Reading SFDP is what tells the two parts apart.

    Macronix RDSR takes a 4-byte address and 4 dummy cycles in octal;
    Micron's takes none and 8. A controller hardcoded for one reads the
    wrong thing on the other, which is exactly what Profile 1.0 exists to
    prevent.
    """
    flash = await setup(dut)
    info = await flash.discover()

    assert (info.rdsr_dummy, info.rdsr_addr_bytes) == (8, 0)
    mx_rdsr = MX25UM51345G.ops["RDSR"]
    assert (mx_rdsr.opi_dummy, mx_rdsr.opi_addr_bytes) == (4, 4)


# ── flag status register ─────────────────────────────────────────────

@cocotb.test()
async def test_flag_status_ready_polarity_is_inverted(dut):
    """FSR READY is 1 when idle; the status register's WIP is 1 when busy.

    Reading FSR as though it were the status register inverts the busy
    check, so a controller either never waits or waits forever.
    """
    flash = await setup(dut)

    fsr = await flash.read_flag_status()
    assert fsr & FSR_READY, "idle part should report READY"
    assert not await flash.read_status() & STATUS_WIP

    await flash.program(0x00000010, [0x11, 0x22], wait=False)
    assert not await flash.read_flag_status() & FSR_READY, \
        "busy part should clear READY"
    assert await flash.read_status() & STATUS_WIP

    await flash.wait_ready()
    assert await flash.read_flag_status() & FSR_READY


@cocotb.test()
async def test_flag_status_latches_a_program_error(dut):
    """A program issued while busy latches P_ERR, and it stays latched.

    This is what FSR gives you over WIP: WIP only says busy or idle, so a
    write lost this way looks like success once WIP clears.
    """
    flash = await setup(dut)

    await flash.program(0x00000020, [0x33, 0x44], wait=False)
    # Second program while the first is still in flight.
    await flash._transfer("PP", address=0x00000030, write=[0x55, 0x66])

    await flash.wait_ready()
    fsr = await flash.read_flag_status()
    assert fsr & FSR_P_ERR, "no P_ERR after programming a busy part"
    assert fsr & FSR_READY, "the part should be idle again"

    # Still latched on a second read -- it is not read-to-clear.
    assert await flash.read_flag_status() & FSR_P_ERR


@cocotb.test()
async def test_clear_flag_status_clears_the_error(dut):
    """CLFSR is what clears the latched bits."""
    flash = await setup(dut)

    await flash.program(0x00000040, [0x77, 0x88], wait=False)
    await flash._transfer("PP", address=0x00000050, write=[0x99, 0xAA])
    await flash.wait_ready()
    assert await flash.read_flag_status() & FSR_P_ERR

    await flash.clear_flag_status()
    fsr = await flash.read_flag_status()
    assert not fsr & FSR_P_ERR
    assert not fsr & (FSR_E_ERR | FSR_PT_ERR)


@cocotb.test()
async def test_erase_while_busy_latches_e_err_not_p_err(dut):
    """The two error bits distinguish which kind of operation failed."""
    flash = await setup(dut)
    await flash.clear_flag_status()

    await flash.erase_sector(0x00001000, wait=False)
    await flash._transfer("SE", address=0x00002000)

    await flash.wait_ready()
    fsr = await flash.read_flag_status()
    assert fsr & FSR_E_ERR, "no E_ERR after erasing a busy part"
    assert not fsr & FSR_P_ERR, "an erase error must not set P_ERR"
    await flash.clear_flag_status()


@cocotb.test()
async def test_flag_status_readable_in_octal_dtr(dut):
    """FSR works in 8D-8D-8D, where it must transfer two bytes."""
    flash = await setup(dut)
    await flash.enter_octal()

    assert await flash.read_flag_status() & FSR_READY
    await flash.program(0x00000060, [0xBB, 0xCC])
    assert await flash.read_flag_status() & FSR_READY
    assert await flash.read(0x00000060, 2) == [0xBB, 0xCC]
