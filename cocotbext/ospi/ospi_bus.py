import cocotb
from cocotb.triggers import RisingEdge

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

    async def read(self, command, address, mode=0):
        await self.send_command(command, mode)
        await self.send_address(address, mode)
        return await self.receive_data(mode, len(address))

    async def send_byte(self, byte, mode):
        lanes = self.get_lanes(mode)
        for bit_position in range(8):
            bit = (byte >> (7 - bit_position)) & 0x1
            for lane in lanes:
                self.io[lane].value = bit
            await RisingEdge(self.clk)

    async def send_address(self, address, mode):
        lanes = self.get_lanes(mode)
        for i in range(4):
            byte = (address >> (i * 8)) & 0xFF
            for lane in lanes:
                self.io[lane].value = byte
            await RisingEdge(self.clk)

    async def send_data(self, data, mode):
        lanes = self.get_lanes(mode)
        for byte in data:
            for lane in lanes:
                self.io[lane].value = byte
            await RisingEdge(self.clk)

    async def receive_data(self, mode, length):
        lanes = self.get_lanes(mode)
        data = []
        for _ in range(length):
            byte = 0
            for lane in lanes:
                byte |= self.io[lane].value.integer << (lane * 8)
            data.append(byte)
            await RisingEdge(self.clk)
        self.cs.value = 1
        return data

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


