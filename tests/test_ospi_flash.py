import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.result import TestFailure
from cocotb.log import SimLog
from cocotbext.ospi.ospi_flash import OspiFlash
from cocotb.clock import Clock

@cocotb.test()
async def print_dut_signals(dut):
    log = cocotb.logging.getLogger("cocotb.ospi_flash_test")
    log.info("OSPI_CLK: %s" % dut.clk.value)  # Should be `dut.clk`
    log.info("OSPI_CS: %s" % dut.OSPI_CS.value)
    log.info("OSPI_IO: %s" % dut.OSPI_IO.value)
    log.info("data_in: %s" % dut.data_in.value)
    log.info("address: %s" % dut.address.value)

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    """Test to validate fast read operations in different modes."""
    dut._log.info("Starting test_ospi_flash_fast_read")
    
    # Create and start the internal clock
    clk = Clock(dut.clk, 10, 'ns')
    cocotb.start_soon(clk.start())
    
    # Create and start the OSPI clock
    ospi_clk = Clock(dut.OSPI_CLK, 20, 'ns')  # Adjust period as needed
    cocotb.start_soon(ospi_clk.start())

    
    cs = dut.OSPI_CS
    io = dut.OSPI_IO

    # Initialize the OspiFlash instance
    ospi = OspiFlash(dut, dut.OSPI_CLK, cs, io)
    await ospi.initialize()

    
    address = 0x01
    length = 1

    # Single mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xA5] in single mode")
    await ospi.write(address, [0xA5], mode=0)
    
    dut._log.info(f"Reading from address {address:#04x} in single mode")
    read_data = await ospi.read(address, length, mode=0)
    dut._log.info(f"Read data {read_data} in single mode")
    assert read_data == [0xA5], f"Fast read data {read_data} does not match written data [0xA5] in single mode"
    
    # Dual mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xA6] in dual mode")
    await ospi.write(address, [0xA6], mode=1)
    
    dut._log.info(f"Reading from address {address:#04x} in dual mode")
    read_data = await ospi.read(address, length, mode=1)
    dut._log.info(f"Read data {read_data} in dual mode")
    assert read_data == [0xA6], f"Fast read data {read_data} does not match written data [0xA6] in dual mode"
    
    # Quad mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xA7] in quad mode")
    await ospi.write(address, [0xA7], mode=2)
    
    dut._log.info(f"Reading from address {address:#04x} in quad mode")
    read_data = await ospi.read(address, length, mode=2)
    dut._log.info(f"Read data {read_data} in quad mode")
    assert read_data == [0xA7], f"Fast read data {read_data} does not match written data [0xA7] in quad mode"
    
    # Octal mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xA8] in octal mode")
    await ospi.write(address, [0xA8], mode=3)
    
    dut._log.info(f"Reading from address {address:#04x} in octal mode")
    read_data = await ospi.read(address, length, mode=3)
    dut._log.info(f"Read data {read_data} in octal mode")
    assert read_data == [0xA8], f"Fast read data {read_data} does not match written data [0xA8] in octal mode"

@cocotb.test()
async def test_ospi_flash_io_operations(dut):
    """Test to validate read and write operations in different modes."""
    dut._log.info("Starting test_ospi_flash_io_operations")
    # Create and start the internal clock
    clk = Clock(dut.clk, 10, 'ns')
    cocotb.start_soon(clk.start())
    
    # Create and start the OSPI clock
    ospi_clk = Clock(dut.OSPI_CLK, 20, 'ns')  # Adjust period as needed
    cocotb.start_soon(ospi_clk.start())

    
    cs = dut.OSPI_CS
    io = dut.OSPI_IO

    # Initialize the OspiFlash instance
    ospi = OspiFlash(dut, dut.OSPI_CLK, cs, io)
    await ospi.initialize()


    address = 0x02
    length = 1

    # Single mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xB5] in single mode")
    await ospi.write(address, [0xB5], mode=0)
    dut._log.info(f"Reading from address {address:#04x} in single mode")
    read_data = await ospi.read(address, length, mode=0)
    dut._log.info(f"Read data {read_data} in single mode")
    assert read_data == [0xB5], f"Read data {read_data} does not match written data [0xB5] in single mode"

    # Dual mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xB6] in dual mode")
    await ospi.write(address, [0xB6], mode=1)
    dut._log.info(f"Reading from address {address:#04x} in dual mode")
    read_data = await ospi.read(address, length, mode=1)
    dut._log.info(f"Read data {read_data} in dual mode")
    assert read_data == [0xB6], f"Read data {read_data} does not match written data [0xB6] in dual mode"

    # Quad mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xB7] in quad mode")
    await ospi.write(address, [0xB7], mode=2)
    dut._log.info(f"Reading from address {address:#04x} in quad mode")
    read_data = await ospi.read(address, length, mode=2)
    dut._log.info(f"Read data {read_data} in quad mode")
    assert read_data == [0xB7], f"Read data {read_data} does not match written data [0xB7] in quad mode"

    # Octal mode test
    dut._log.info(f"Writing to address {address:#04x} data: [0xB8] in octal mode")
    await ospi.write(address, [0xB8], mode=3)
    dut._log.info(f"Reading from address {address:#04x} in octal mode")
    read_data = await ospi.read(address, length, mode=3)
    dut._log.info(f"Read data {read_data} in octal mode")
    assert read_data == [0xB8], f"Read data {read_data} does not match written data [0xB8] in octal mode"

@cocotb.test()
async def test_ospi_flash_hold_operations(dut):
    """Test to validate hold operations."""
    dut._log.info("Starting test_ospi_flash_hold_operations")
    # Create and start the internal clock
    clk = Clock(dut.clk, 10, 'ns')
    cocotb.start_soon(clk.start())
    
    # Create and start the OSPI clock
    ospi_clk = Clock(dut.OSPI_CLK, 20, 'ns')  # Adjust period as needed
    cocotb.start_soon(ospi_clk.start())

    
    cs = dut.OSPI_CS
    io = dut.OSPI_IO

    # Initialize the OspiFlash instance
    ospi = OspiFlash(dut, dut.OSPI_CLK, cs, io)
    await ospi.initialize()


    if not hasattr(dut, 'HOLD_N'):
        dut._log.warning("HOLD_N signal is not defined in the DUT. Skipping hold operations tests.")
        return

    address = 0x03
    length = 1

    # Write data and hold operation
    dut._log.info(f"Writing to address {address:#04x} data: [0xC5] in single mode before hold operation")
    await ospi.write(address, [0xC5], mode=0)
    dut._log.info("Triggering hold operation")
    await ospi.hold_operation()
    dut._log.info(f"Reading from address {address:#04x} in single mode during hold operation")
    read_data = await ospi.read(address, length, mode=0)
    dut._log.info(f"Read data {read_data} during hold operation")
    assert read_data == [0xC5], f"Read data {read_data} does not match written data [0xC5] after hold operation"

    dut._log.info("Releasing hold operation")
    await ospi.release_hold()
    dut._log.info(f"Writing to address {address:#04x} data: [0xC6] in dual mode after releasing hold")
    await ospi.write(address, [0xC6], mode=1)
    dut._log.info(f"Reading from address {address:#04x} in dual mode after releasing hold")
    read_data = await ospi.read(address, length, mode=1)
    dut._log.info(f"Read data {read_data} after releasing hold")
    assert read_data == [0xC6], f"Read data {read_data} does not match written data [0xC6] after releasing hold"
