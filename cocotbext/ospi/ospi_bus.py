import cocotb
from cocotb.triggers import RisingEdge, Timer
from typing import Tuple, List

class OspiBus:
    def __init__(self, dut, clk, cs, io):
        self.dut = dut
        self.clk = clk
        self.cs = cs
        self.io = io

    async def send_command(self, command, mode):
        command_bits = format(command, f'0{len(self.io)}b')
        self.dut._log.info(f"Sending command {command_bits} in mode {mode}")
        for i, bit in enumerate(command_bits):
            self.io[i].value = int(bit)
        await Timer(10, units='ns')

    async def write(self, command, address, data, mode=0):
        self.dut._log.info(f"Write operation: Command: {command}, Address: {address}, Data: {data}, Mode: {mode}")
        await self.send_command(command, mode)
        await self.send_address(address, mode)
        await self.send_data(data, mode)

    async def read(self, command, address, mode, length):
        self.dut._log.info(f"Read operation: Command: {command}, Address: {address}, Length: {length}, Mode: {mode}")
        if not isinstance(address, (list, Tuple)):
            address = [address]
        await self.send_command(command, mode)
        await self.send_address(address, mode)
        data = await self.receive_data(mode, length)
        return data

    async def send_byte(self, byte, mode):
        lanes = self.get_lanes(mode)
        byte_str = format(byte, '08b')
        self.dut._log.info(f"Sending byte {byte_str} on lanes {lanes} in mode {mode}")
        for bit_position in range(8):
            bit = (byte >> (7 - bit_position)) & 0x1
            for lane in lanes:
                self.io[lane].value = bit
            await RisingEdge(self.clk)


    async def send_address(self, address, mode):
        if isinstance(address, (list, tuple)):
            address = int(''.join(format(x, '08b') for x in address), 2)
        address_bits = format(address, f'0{len(self.io) * 8}b')
        self.dut._log.info(f"Sending address {address_bits} in mode {mode}")
        for i in range(len(address_bits) // 8):
            byte = int(address_bits[i * 8:(i + 1) * 8], 2)
            await self.send_byte(byte, mode)

    async def send_data(self, data, mode):
        self.dut._log.info(f"Sending data {data} in mode {mode}")
        for byte in data:
            await self.send_byte(byte, mode)

    async def receive_data(self, mode, length):
        self.dut._log.info(f"Receiving data of length {length} in mode {mode}")
        data = []
        for _ in range(length):
            byte = await self.receive_byte(mode)
            data.append(byte)
        self.dut._log.info(f"Received data: {data}")
        return data

    async def receive_byte(self, mode):
        byte = 0
        for bit_position in range(8):
            await RisingEdge(self.clk)
            bit = self.io[0].value
            byte = (byte << 1) | bit
        byte_str = format(byte, '08b')
        self.dut._log.info(f"Received byte {byte_str} in mode {mode}")
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



