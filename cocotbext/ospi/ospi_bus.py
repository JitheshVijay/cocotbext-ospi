import cocotb
from cocotb.triggers import RisingEdge, Timer

class OspiBus:
    def __init__(self, dut, clk, cs, io):
        self.dut = dut
        self.clk = clk
        self.cs = cs
        self.io = io

    async def send_command(self, command, mode):
        command_bits = format(command, f'0{len(self.io)}b')
        for i, bit in enumerate(command_bits):
            self.io[i].value = int(bit)
        await Timer(10, units='ns')

    async def write(self, command, address, data, mode=0):
        await self.send_command(command, mode)
        await self.send_address(address, mode)
        await self.send_data(data, mode)

    async def read(self, command, address, mode, length):
        if not isinstance(address, (list, tuple)):
            address = [address]
        return await self.receive_data(mode, len(address))

        
    async def send_byte(self, byte, mode):
        lanes = self.get_lanes(mode)
        for bit_position in range(8):
            bit = (byte >> (7 - bit_position)) & 0x1
            for lane in lanes:
                self.io[lane].value = bit
            await RisingEdge(self.clk)

    async def send_address(self, address, mode):
        address_bits = format(address, f'0{len(self.io) * 8}b')
        for i in range(len(self.io)):
            byte = int(address_bits[i * 8:(i + 1) * 8], 2)
            await self.send_byte(byte, mode)

    async def send_data(self, data, mode):
        for byte in data:
            for i in range(8):
                bit = (byte >> (7 - i)) & 1
                self.io[i].value = bit
                await RisingEdge(self.clk)

    async def receive_data(self, mode, length):
        data = []
        for _ in range(length):
            byte = await self.receive_byte(mode)
            data.append(byte)
        return data

    async def receive_byte(self, mode):
        byte = 0
        for bit_position in range(8):
            await RisingEdge(self.clk)
            bit = self.io[0].value
            byte = (byte << 1) | bit
        return byte


    def get_lanes(self, mode):
        if mode == 0:
            return [0]
        elif mode == 1:
            return [0, 1]
        elif mode == 2:
            return [0, 1, 2, 3]
        elif mode == 3:
            return [0, 1, 2, 3, 4, 5, 6, 7]
        else:
            raise ValueError(f"Unsupported mode: {mode}")



