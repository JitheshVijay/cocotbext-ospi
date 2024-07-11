import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def simple_ospi_test(dut):
    # Initialize the OSPI flash
    dut.reset_n <= 0
    await Timer(5, units='ns')
    dut.reset_n <= 1

    # Toggle the clock and check signal toggling
    for _ in range(10):
        dut.OSPI_CLK <= 0
        await Timer(5, units='ns')
        dut.OSPI_CLK <= 1
        await Timer(5, units='ns')
    
    # Log message indicating completion
    dut._log.info("Simple OSPI test completed")

