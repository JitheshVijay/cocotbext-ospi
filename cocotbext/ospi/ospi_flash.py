import cocotb
from cocotb.triggers import Timer
from cocotbext.ospi.ospi_bus import OspiBus

class OspiFlash:
    def __init__(self, dut, clk, cs, io):
        self.dut = dut
        self.clk = clk
        self.cs = cs
        self.io = io
        self.ospi = OspiBus(dut, clk, cs, io)

    async def initialize(self):
        self.dut.reset_n.value = 0 
        await Timer(10, units='ns')
        self.dut.reset_n.value = 1  

    async def write(self, address, data, mode):
        self.dut._log.info(f"Writing data {data} to address {address} in mode {mode}")
        
        if mode == 0:  # Single mode
            await self.ospi.write(0x02, address, data, mode)
        
        elif mode == 1:  # Dual mode
            await self.ospi.write(0xA2, address, data, mode)  # Hypothetical command for dual write
        
        elif mode == 2:  # Quad mode
            await self.ospi.write(0x32, address, data, mode)  # Hypothetical command for quad write

        elif mode == 3:  # Octal mode
            await self.ospi.write(0x82, address, data, mode)  # Hypothetical command for octal write

    async def read(self, address, length, mode):
        self.dut._log.info(f"Reading data from address {address} with length {length} in mode {mode}")
        
        if mode == 0:  # Single mode
            read_data = await self.ospi.read(0x03, address, mode, length)  # Command for single read
        
        elif mode == 1:  # Dual mode
            read_data = await self.ospi.read(0xBB, address, mode, length)  # Hypothetical command for dual read
        
        elif mode == 2:  # Quad mode
            read_data = await self.ospi.read(0xEB, address, mode, length)  # Hypothetical command for quad read

        elif mode == 3:  # Octal mode
            read_data = await self.ospi.read(0xEC, address, mode, length)  # Hypothetical command for octal read

        self.dut._log.info(f"Read data {read_data}")
        return read_data

    async def fast_read(self, address, length, mode=0):
        return await self.ospi.read(0x0B, address, mode, length)  # Command for fast read

    async def hold_operation(self):
        if hasattr(self.dut, 'HOLD_N'):
            self.dut.HOLD_N.value = 0
            await Timer(10, units='ns')
            self.dut.HOLD_N.value = 1
        else:
            raise AttributeError("HOLD_N signal is not defined in the DUT")

    async def release_hold(self):
        if hasattr(self.dut, 'HOLD_N'):
            self.dut.HOLD_N.value = 1
            await Timer(10, units='ns')
        else:
            raise AttributeError("HOLD_N signal is not defined in the DUT")


