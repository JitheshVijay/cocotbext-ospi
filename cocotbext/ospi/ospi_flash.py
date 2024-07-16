import cocotb
from cocotb.triggers import Timer
from cocotbext.ospi.ospi_bus import OspiBus

class OspiFlash:
    def __init__(self, dut, clk, cs, io):
        self.dut = dut
        self.clk = clk
        self.cs = cs
        self.io = io
        self.ospi_bus = OspiBus(dut, clk, cs, io)

    async def initialize(self):
        self.dut.reset_n.value = 0 
        await Timer(10, units='ns')
        self.dut.reset_n.value = 1  

    async def write(self, address, data, mode=0):
        await self.ospi_bus.write(command=0x02, address=address, data=data, mode=mode)

    async def read(self, address, length, mode=0):
        return await self.ospi_bus.read(command=0x03, address=address, mode=mode, length=length)

    async def fast_read(self, address, length, mode=0):
        return await self.ospi_bus.read(command=0x0B, address=address, mode=mode, length=length)

    async def hold_operation(self):
        self.dut.HOLD_N <= 0
        await Timer(10, units='ns')
        self.dut.HOLD_N <= 1

    async def release_hold(self):
        self.dut.HOLD_N <= 1
        await Timer(10, units='ns')


