import cocotb
from cocotb.triggers import Timer
from cocotb.log import SimLog
from cocotbext.ospi import OspiBus, OspiFlash

@cocotb.test()
async def print_dut_signals(dut):
    log = SimLog("cocotb.print_dut_signals")
    log.info("OSPI_CLK: %s" % dut.OSPI_CLK.value)
    log.info("OSPI_CS: %s" % dut.OSPI_CS.value)
    log.info("OSPI_IO0: %s" % dut.OSPI_IO0.value)
    log.info("OSPI_IO1: %s" % dut.OSPI_IO1.value)
    log.info("OSPI_IO2: %s" % dut.OSPI_IO2.value)
    log.info("OSPI_IO3: %s" % dut.OSPI_IO3.value)
    log.info("OSPI_IO4: %s" % dut.OSPI_IO4.value)
    log.info("OSPI_IO5: %s" % dut.OSPI_IO5.value)
    log.info("OSPI_IO6: %s" % dut.OSPI_IO6.value)
    log.info("OSPI_IO7: %s" % dut.OSPI_IO7.value)

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [dut.OSPI_IO0, dut.OSPI_IO1, dut.OSPI_IO2, dut.OSPI_IO3, dut.OSPI_IO4, dut.OSPI_IO5, dut.OSPI_IO6, dut.OSPI_IO7]
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    address = 0x01
    await ospi.write(address, [0xA5], mode=0)
    read_data = await ospi.fast_read(address, mode=0)
    assert read_data == [0xA5], f"Fast read data {read_data} does not match written data [0xA5] in single mode"

    await ospi.write(address, [0xA6], mode=1)
    read_data = await ospi.fast_read(address, mode=1)
    assert read_data == [0xA6], f"Fast read data {read_data} does not match written data [0xA6] in dual mode"

    await ospi.write(address, [0xA7], mode=2)
    read_data = await ospi.fast_read(address, mode=2)
    assert read_data == [0xA7], f"Fast read data {read_data} does not match written data [0xA7] in quad mode"

    await ospi.write(address, [0xA8], mode=3)
    read_data = await ospi.fast_read(address, mode=3)
    assert read_data == [0xA8], f"Fast read data {read_data} does not match written data [0xA8] in octal mode"

@cocotb.test()
async def test_ospi_flash_io_operations(dut):
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [dut.OSPI_IO0, dut.OSPI_IO1, dut.OSPI_IO2, dut.OSPI_IO3, dut.OSPI_IO4, dut.OSPI_IO5, dut.OSPI_IO6, dut.OSPI_IO7]
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    address = 0x02
    await ospi.write(address, [0xB5], mode=0)
    read_data = await ospi.read(address, mode=0)
    assert read_data == [0xB5], f"Read data {read_data} does not match written data [0xB5] in single mode"

    await ospi.write(address, [0xB6], mode=1)
    read_data = await ospi.read(address, mode=1)
    assert read_data == [0xB6], f"Read data {read_data} does not match written data [0xB6] in dual mode"

    await ospi.write(address, [0xB7], mode=2)
    read_data = await ospi.read(address, mode=2)
    assert read_data == [0xB7], f"Read data {read_data} does not match written data [0xB7] in quad mode"

    await ospi.write(address, [0xB8], mode=3)
    read_data = await ospi.read(address, mode=3)
    assert read_data == [0xB8], f"Read data {read_data} does not match written data [0xB8] in octal mode"

@cocotb.test()
async def test_ospi_flash_hold_operations(dut):
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [dut.OSPI_IO0, dut.OSPI_IO1, dut.OSPI_IO2, dut.OSPI_IO3, dut.OSPI_IO4, dut.OSPI_IO5, dut.OSPI_IO6, dut.OSPI_IO7]
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    address = 0x03
    await ospi.write(address, [0xC5], mode=0)
    await ospi.hold_operation()
    read_data = await ospi.read(address, mode=0)
    assert read_data == [0xC5], f"Read data {read_data} does not match written data [0xC5] after hold operation"

    await ospi.release_hold()
    await ospi.write(address, [0xC6], mode=1)
    read_data = await ospi.read(address, mode=1)
    assert read_data == [0xC6], f"Read data {read_data} does not match written data [0xC6] after releasing hold"

