import cocotb
from cocotb.triggers import RisingEdge
from cocotb.log import SimLog
from cocotbext.ospi.ospi_bus import OspiBus
from cocotbext.ospi.ospi_flash import OspiFlash


@cocotb.test()
async def print_dut_signals(dut):
    log = SimLog("cocotb.print_dut_signals")

    for _ in range(10):  # Wait for a few clock cycles
        await RisingEdge(dut.OSPI_CLK)
    
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
async def test_ospi_flash_simple(dut):
    dut._log.info("Starting test_ospi_flash_simple")

    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [dut.OSPI_IO0, dut.OSPI_IO1, dut.OSPI_IO2, dut.OSPI_IO3, dut.OSPI_IO4, dut.OSPI_IO5, dut.OSPI_IO6, dut.OSPI_IO7]

    dut._log.info("Creating OspiFlash instance")
    try:
        ospi = OspiFlash(dut, clk, cs, io)
    except Exception as e:
        dut._log.error(f"Failed to create OspiFlash instance: {e}")
        raise

    dut._log.info("Initializing OspiFlash")
    try:
        await ospi.initialize()
    except Exception as e:
        dut._log.error(f"Initialization failed: {e}")
        raise

    await RisingEdge(clk)
    dut._log.info("Initialization complete, simple test starting")

    address = 0x01

    try:
        dut._log.info(f"Writing 0xA5 to address {hex(address)}")
        await ospi.write(address, [0xA5])
        read_data = await ospi.read(address)
        dut._log.info(f"Read data {read_data}")
        assert read_data == [0xA5], f"Read data {read_data} does not match written data [0xA5]"
    except Exception as e:
        dut._log.error(f"Simple test failed: {e}")
        raise
