import cocotb
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge
from cocotb.result import TestFailure
from cocotb.log import SimLog
from cocotbext.ospi.ospi_bus import OspiBus
from cocotbext.ospi.ospi_flash import OspiFlash
from cocotb.clock import Clock

@cocotb.test()
async def print_dut_signals(dut):
    log = SimLog("cocotb.print_dut_signals")
    log.info("OSPI_CLK: %s" % dut.OSPI_CLK.value)
    log.info("OSPI_CS: %s" % dut.OSPI_CS.value)
    for i in range(8):
        log.info(f"OSPI_IO{i}: %s" % getattr(dut, f"OSPI_IO{i}").value)

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    dut._log.info("Starting test_ospi_flash_fast_read")
    c = Clock(dut.OSPI_CLK, 10, 'ns')
    await cocotb.start(c.start())
    
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [getattr(dut, f"OSPI_IO{i}") for i in range(8)]
    
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()
    
    address = 0x01
    length = 1

    # Single mode test
    await ospi.write(address, [0xA5], mode=0)
    read_data = await ospi.fast_read(address, length, mode=0)
    dut._log.info(f"Read data {read_data} in single mode")
    assert read_data == [0xA5], f"Fast read data {read_data} does not match written data [0xA5] in single mode"
    
    # Dual mode test
    await ospi.write(address, [0xA6], mode=1)
    read_data = await ospi.fast_read(address, length, mode=1)
    dut._log.info(f"Read data {read_data} in dual mode")
    assert read_data == [0xA6], f"Fast read data {read_data} does not match written data [0xA6] in dual mode"
    
    # Quad mode test
    await ospi.write(address, [0xA7], mode=2)
    read_data = await ospi.fast_read(address, length, mode=2)
    dut._log.info(f"Read data {read_data} in quad mode")
    assert read_data == [0xA7], f"Fast read data {read_data} does not match written data [0xA7] in quad mode"
    
    # Octal mode test
    await ospi.write(address, [0xA8], mode=3)
    read_data = await ospi.fast_read(address, length, mode=3)
    dut._log.info(f"Read data {read_data} in octal mode")
    assert read_data == [0xA8], f"Fast read data {read_data} does not match written data [0xA8] in octal mode"

@cocotb.test()
async def test_ospi_flash_io_operations(dut):
    dut._log.info("Starting test_ospi_flash_io_operations")
    c = Clock(dut.OSPI_CLK, 10, 'ns')
    await cocotb.start(c.start())
    
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [getattr(dut, f"OSPI_IO{i}") for i in range(8)]
    
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    address = 0x02

    # Single mode test
    await ospi.write(address, [0xB5], mode=0)
    read_data = await ospi.read(address, 1, mode=0)
    assert read_data == [0xB5], f"Read data {read_data} does not match written data [0xB5] in single mode"

    # Dual mode test
    await ospi.write(address, [0xB6], mode=1)
    read_data = await ospi.read(address, 1, mode=1)
    assert read_data == [0xB6], f"Read data {read_data} does not match written data [0xB6] in dual mode"

    # Quad mode test
    await ospi.write(address, [0xB7], mode=2)
    read_data = await ospi.read(address, 1, mode=2)
    assert read_data == [0xB7], f"Read data {read_data} does not match written data [0xB7] in quad mode"

    # Octal mode test
    await ospi.write(address, [0xB8], mode=3)
    read_data = await ospi.read(address, 1, mode=3)
    assert read_data == [0xB8], f"Read data {read_data} does not match written data [0xB8] in octal mode"

@cocotb.test()
async def test_ospi_flash_hold_operations(dut):
    dut._log.info("Starting test_ospi_flash_hold_operations")
    c = Clock(dut.OSPI_CLK, 10, 'ns')
    await cocotb.start(c.start())
    
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [getattr(dut, f"OSPI_IO{i}") for i in range(8)]
    
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    address = 0x03

    # Write data and hold operation
    await ospi.write(address, [0xC5], mode=0)
    await ospi.hold_operation()
    read_data = await ospi.read(address, 1, mode=0)
    assert read_data == [0xC5], f"Read data {read_data} does not match written data [0xC5] after hold operation"

    await ospi.release_hold()
    await ospi.write(address, [0xC6], mode=1)
    read_data = await ospi.read(address, 1, mode=1)
    assert read_data == [0xC6], f"Read data {read_data} does not match written data [0xC6] after releasing hold"
