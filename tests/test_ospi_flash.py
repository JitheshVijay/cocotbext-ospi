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
        cs_value = dut.OSPI_CS.value.binstr  # Get binary string representation
        if 'x' in cs_value or 'z' in cs_value:
            cs = None  # Or any other default/error value
        else:
            cs = int(cs_value, 2)
        
        clk_value = dut.OSPI_CLK.value.binstr
        if 'x' in clk_value or 'z' in clk_value:
            clk = None
        else:
            clk = int(clk_value, 2)
        
        io_values = []
        for i in range(8):
            io_value = getattr(dut, f"OSPI_IO{i}").value.binstr
            if 'x' in io_value or 'z' in io_value:
                io = None
            else:
                io = int(io_value, 2)
            io_values.append(io)
        
        dut._log.info(f"CS: {cs}, CLK: {clk}, IO: {io_values}")

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    # Write data to flash
    address = 0x0001
    write_data = [0xA5]
    cocotb.log.info(f"Writing data {write_data} to address {address}")
    await write_flash(dut, address, write_data)

    # Read data from flash
    read_data = await read_flash(dut, address, len(write_data))
    cocotb.log.info(f"Read data {read_data} from address {address}")

    # Assert that the read data matches the written data
    assert read_data == write_data, f"Fast read data {read_data} does not match written data {write_data} in single mode"
