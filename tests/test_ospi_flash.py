import cocotb
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge
from cocotb.result import TestFailure
from cocotb.log import SimLog
from cocotbext.ospi.ospi_bus import OspiBus
from cocotbext.ospi.ospi_flash import OspiFlash
from cocotb.clock import Clock


@cocotb.coroutine
async def monitor_signals(dut):
    """Coroutine to monitor and log OSPI signals."""
    while True:
        await RisingEdge(dut.OSPI_CLK)
        cs = dut.OSPI_CS.value.integer
        clk = dut.OSPI_CLK.value.integer
        io = [getattr(dut, f"OSPI_IO{i}").value.integer for i in range(8)]
        dut._log.info(f"CS: {cs}, CLK: {clk}, IO: {io}")

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    dut._log.info("Starting test_ospi_flash_fast_read")
    
    # Create a clock with a period of 10 ns (100 MHz)
    c = Clock(dut.OSPI_CLK, 10, 'ns')
    await cocotb.start(c.start())
    await cocotb.start(monitor_signals(dut))
    
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
    dut._log.info(f"Single mode: Written data [0xA5], Read data {read_data}")
    assert read_data == [0xA5], f"Fast read data {read_data} does not match written data [0xA5] in single mode"

@cocotb.test()
async def test_ospi_flash_io_operations(dut):
    dut._log.info("Starting test_ospi_flash_io_operations")
    c = Clock(dut.OSPI_CLK, 10, 'ns')
    await cocotb.start(c.start())
    await cocotb.start(monitor_signals(dut))
    
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [getattr(dut, f"OSPI_IO{i}") for i in range(8)]
    
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    address = 0x02
    length = 1

    # Single mode test
    await ospi.write(address, [0xB5], mode=0)
    read_data = await ospi.read(address, length, mode=0)
    dut._log.info(f"Single mode: Written data [0xB5], Read data {read_data}")
    assert read_data == [0xB5], f"Read data {read_data} does not match written data [0xB5] in single mode"

@cocotb.test()
async def test_ospi_flash_hold_operations(dut):
    dut._log.info("Starting test_ospi_flash_hold_operations")
    c = Clock(dut.OSPI_CLK, 10, 'ns')
    await cocotb.start(c.start())
    await cocotb.start(monitor_signals(dut))
    
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [getattr(dut, f"OSPI_IO{i}") for i in range(8)]
    
    ospi = OspiFlash(dut, clk, cs, io)
    await ospi.initialize()

    if not hasattr(dut, 'HOLD_N'):
        dut._log.warning("HOLD_N signal is not defined in the DUT. Skipping hold operations tests.")
        return

    address = 0x03
    length = 1

    # Write data and hold operation
    await ospi.write(address, [0xC5], mode=0)
    await ospi.hold_operation()
    read_data = await ospi.read(address, length, mode=0)
    dut._log.info(f"After hold operation: Written data [0xC5], Read data {read_data}")
    assert read_data == [0xC5], f"Read data {read_data} does not match written data [0xC5] after hold operation"

    await ospi.release_hold()
    await ospi.write(address, [0xC6], mode=1)
    read_data = await ospi.read(address, length, mode=1)
    dut._log.info(f"After releasing hold: Written data [0xC6], Read data {read_data}")
    assert read_data == [0xC6], f"Read data {read_data} does not match written data [0xC6] after releasing hold"
