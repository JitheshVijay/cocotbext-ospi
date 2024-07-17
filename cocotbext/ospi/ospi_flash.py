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

    async def write(self, address, data, mode):
        self.dut._log.info(f"Writing data {data} to address {address} in mode {mode}")
        self.ospi.start_transaction()
        
        if mode == 0:  # Single mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0x02)  # Command for single write
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for byte in data:
                await self.ospi.write_byte(byte)
            self.ospi.cs.value = 1
        
        elif mode == 1:  # Dual mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0xA2)  # Hypothetical command for dual write
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for byte in data:
                await self.ospi.write_byte(byte)
            self.ospi.cs.value = 1
        
        elif mode == 2:  # Quad mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0x32)  # Hypothetical command for quad write
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for byte in data:
                await self.ospi.write_byte(byte)
            self.ospi.cs.value = 1

        elif mode == 3:  # Octal mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0x82)  # Hypothetical command for octal write
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for byte in data:
                await self.ospi.write_byte(byte)
            self.ospi.cs.value = 1

        self.ospi.end_transaction()

    async def read(self, address, length, mode):
        self.dut._log.info(f"Reading data from address {address} with length {length} in mode {mode}")
        self.ospi.start_transaction()

        read_data = []
        if mode == 0:  # Single mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0x03)  # Command for single read
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for _ in range(length):
                read_data.append(await self.ospi.read_byte())
            self.ospi.cs.value = 1

        elif mode == 1:  # Dual mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0xBB)  # Hypothetical command for dual read
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for _ in range(length):
                read_data.append(await self.ospi.read_byte())
            self.ospi.cs.value = 1

        elif mode == 2:  # Quad mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0xEB)  # Hypothetical command for quad read
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for _ in range(length):
                read_data.append(await self.ospi.read_byte())
            self.ospi.cs.value = 1

        elif mode == 3:  # Octal mode
            self.ospi.cs.value = 0
            await self.ospi.write_byte(0xEC)  # Hypothetical command for octal read
            await self.ospi.write_byte((address >> 16) & 0xFF)
            await self.ospi.write_byte((address >> 8) & 0xFF)
            await self.ospi.write_byte(address & 0xFF)
            for _ in range(length):
                read_data.append(await self.ospi.read_byte())
            self.ospi.cs.value = 1

        self.ospi.end_transaction()
        self.dut._log.info(f"Read data {read_data}")
        return read_data

    async def fast_read(self, address, length, mode=0):
        return await self.ospi_bus.read(command=0x0B, address=address, mode=mode, length=length)

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


