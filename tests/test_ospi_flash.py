import cocotb
from cocotb.triggers import Timer
from cocotb.log import SimLog
from cocotbext.ospi.ospi_bus import OspiBus
from cocotbext.ospi.ospi_flash import OspiFlash

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
    flash = OspiFlash(dut, dut.clk, dut.cs, [dut.io0, dut.io1, dut.io2, dut.io3, dut.io4, dut.io5, dut.io6, dut.io7])
    await flash.initialize()
    
    # Write some data first
    data_to_write = [0x01, 0x02, 0x03, 0x04]
    await flash.write(0x00000000, data_to_write, mode=3)
    
    # Perform fast read
    read_data = await flash.fast_read(0x00000000, mode=3)
    assert read_data == data_to_write, f"Read data {read_data} does not match written data {data_to_write}"

