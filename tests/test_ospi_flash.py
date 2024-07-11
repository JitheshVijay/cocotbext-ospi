import cocotb
from cocotb.triggers import Timer
from cocotbext.ospi.ospi_flash import OspiFlash

@cocotb.test()
async def simple_ospi_test(dut):
    # Create an instance of the OSPI flash
    clk = dut.OSPI_CLK
    cs = dut.OSPI_CS
    io = [dut.OSPI_IO0, dut.OSPI_IO1, dut.OSPI_IO2, dut.OSPI_IO3, dut.OSPI_IO4, dut.OSPI_IO5, dut.OSPI_IO6, dut.OSPI_IO7]
    ospi = OspiFlash(dut, clk, cs, io)
    
    # Initialize the OSPI flash
    await ospi.initialize()

    # Write a value to a specific address
    address = 0x01
    write_data = [0xAB]
    await ospi.write(address, write_data, mode=0)
    
    # Read the value back from the same address
    read_data = await ospi.read(address, mode=0)
    
    # Check if the read data matches the written data
    assert read_data == write_data, f"Read data {read_data} does not match written data {write_data}"

    # Optional: Print a message indicating the test passed
    dut._log.info(f"Simple OSPI test passed: Read data {read_data} matches written data {write_data}")
