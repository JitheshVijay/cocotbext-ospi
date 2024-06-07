import cocotb
from cocotb.triggers import Timer, RisingEdge

class OspiSlave:
    def __init__(self, dut, config):
        self.dut = dut
        self.config = config

    async def read(self):
        byte = 0
        for i in range(8):
            await RisingEdge(self.dut.OSPI_CLK)
            byte = (byte << 1) | int(self.dut.OSPI_IO[0].value)
        return byte

    async def write(self, data):
        for i in range(8):
            self.dut.OSPI_IO[0].value = (data >> (7 - i)) & 1
            await RisingEdge(self.dut.OSPI_CLK)
        await Timer(1, units='ns')