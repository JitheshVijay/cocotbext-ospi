import cocotb
from cocotb.triggers import Timer
from cocotbext.ospi.ospi_bus import OspiBus


class OspiFlash:

    def __init__(self, dut, clk, cs, io):
        self.dut = dut
        self.clk = clk
        self.cs = cs
        self.io = io

        self.data_store = {}

        self.ospi = OspiBus(dut, clk, cs, io)

    async def initialize(self):
        self.dut.reset_n.value = 0
        await Timer(20, units='ns')
        self.dut.reset_n.value = 1 
        await Timer(20, units='ns')
        pass 

    async def write(self, address, data, mode):
        command = {
            0: 0x02,  
            1: 0xA2,  
            2: 0x32,  
        }.get(mode, None)

        if command is None:
            raise ValueError("Unsupported write mode: {}".format(mode))

        self.data_store[address] = data
        self.dut._log.info(
            f"Data store after write to address {address:#04x}: {self.data_store}"
        )

        await self.ospi.write(command, address, data, mode)


    async def read(self, address, length, mode):
        command = {
            0: 0x03, 
            1: 0xBB,  
            2: 0xEB,  
        }.get(mode, None)

        if command is None:
            raise ValueError("Unsupported read mode: {}".format(mode))

        
        read_data = self.data_store.get(address, [0x00] * length)

        return await self.ospi.read(command, address, mode, length)

    async def fast_read(self, address, length, mode=0):
        return await self.ospi.read(0x0B, address, mode, length)

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





