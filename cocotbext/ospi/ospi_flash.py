import sys
import os

# Add the path to the cocotbext directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'D:\Manipal\cocotb\cocotbext')))

from cocotbext.ospi import OspiBus, OspiMaster, OspiSlave, OspiConfig

import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock

class OspiFlash:
    def __init__(self, dut):
        self.dut = dut
        self.ospi_bus = OspiBus.from_prefix(dut, "OSPI")
        self.ospi_config = OspiConfig(
            word_width=8,
            sclk_freq=50e6,
            cpol=False,
            cpha=False,
            cs_active_low=True,
            quad_mode=True  # Assuming quad_mode is a valid config for OSPI
        )
        self.ospi_master = OspiMaster(self.ospi_bus, self.ospi_config)

    async def reset(self):
        self.dut.OSPI_RST_b.value = 0
        await Timer(100, units='ns')
        self.dut.OSPI_RST_b.value = 1
        await Timer(100, units='ns')

    async def initialize(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, units='ns').start())
        await self.reset()

    async def write(self, address, data):
        command = [0x02]  # Page Program command for OSPI
        address_bytes = [(address >> i) & 0xFF for i in (16, 8, 0)]
        data_bytes = [data]
        await self.ospi_master.write(command + address_bytes + data_bytes)
        await Timer(1, units='ns')

    async def read(self, address):
        command = [0x03]  # Read Data command for OSPI
        address_bytes = [(address >> i) & 0xFF for i in (16, 8, 0)]
        await self.ospi_master.write(command + address_bytes)
        await Timer(1, units='ns')
        read_data = await self.ospi_master.read(1)
        return read_data[0]

    async def erase(self, address):
        command = [0x20]  # Sector Erase command for OSPI
        address_bytes = [(address >> i) & 0xFF for i in (16, 8, 0)]
        await self.ospi_master.write(command + address_bytes)
        await Timer(1, units='ns')