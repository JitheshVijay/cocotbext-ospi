import cocotb
from cocotbext.ospi.ospi_bus import OspiBus
from cocotb.triggers import RisingEdge, Timer

class OspiFlash:
    def __init__(self, dut):
        self.dut = dut
        self.ospi_bus = OspiBus(dut, "OSPI_CLK", "OSPI_CS", "OSPI_IO", 8)

    async def initialize(self):
        self.dut.reset_n <= 0
        await Timer(10, units='ns')
        self.dut.reset_n <= 1

    async def write(self, address, data, mode=0):
        await self.ospi_bus.write(command=0x02, address=address, data=data, mode=mode)

    async def read(self, address, mode=0):
        return await self.ospi_bus.read(command=0x03, address=address, mode=mode)

    async def erase(self, address, mode=0):
        await self.ospi_bus.write(command=0x20, address=address, data=0xFF, mode=mode)


