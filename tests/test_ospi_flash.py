import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb.log import SimLog
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'cocotbext/ospi/ospi_flash.py')))
from ospi_flash import OspiFlash

@cocotb.test()
async def print_dut_signals(dut):
    log = SimLog("cocotb.print_dut_signals")
    log.info(f"Available attributes in dut: {dir(dut)}")
    cocotb.log.info(f"OSPI_CLK: {dut.OSPI_CLK.value}")
    cocotb.log.info(f"OSPI_CS: {dut.OSPI_CS.value}")

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    clk = "OSPI_CLK"
    cs = "OSPI_CS"
    io = "OSPI_IO"
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
    clk = "OSPI_CLK"
    cs = "OSPI_CS"
    io = "OSPI_IO"
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
    clk = "OSPI_CLK"
    cs = "OSPI_CS"
    io = "OSPI_IO"
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


