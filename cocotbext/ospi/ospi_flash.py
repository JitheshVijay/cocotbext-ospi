import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
from cocotbext.ospi.ospi_bus import OspiBus

class OspiFlash:
    def __init__(self, dut):
        self.dut = dut
        self.ospi_bus = OspiBus.from_prefix(dut, "OSPI")

    async def initialize(self):
        self.ospi_bus.cs.value = 1
        await RisingEdge(self.ospi_bus.clk)

    async def write(self, address, data):
        self.ospi_bus.cs.value = 0
        await RisingEdge(self.ospi_bus.clk)
        self.dut.address.value = address
        self.dut.data_in.value = data
        self.dut.write_enable.value = 1
        await RisingEdge(self.ospi_bus.clk)
        self.dut.write_enable.value = 0
        self.ospi_bus.cs.value = 1

    async def read(self, address):
        self.ospi_bus.cs.value = 0
        await RisingEdge(self.ospi_bus.clk)
        self.dut.address.value = address
        self.dut.read_enable.value = 1
        await RisingEdge(self.ospi_bus.clk)
        await ReadOnly()
        data = self.dut.data_out.value.integer
        self.dut.read_enable.value = 0
        self.ospi_bus.cs.value = 1
        return data

    async def erase(self, address):
        self.ospi_bus.cs.value = 0
        await RisingEdge(self.ospi_bus.clk)
        self.dut.address.value = address
        self.dut.erase_enable.value = 1
        await RisingEdge(self.ospi_bus.clk)
        self.dut.erase_enable.value = 0
        self.ospi_bus.cs.value = 1

