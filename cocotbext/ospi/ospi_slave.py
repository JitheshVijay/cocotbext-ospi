import cocotb
from cocotb.triggers import Timer, RisingEdge

class OspiSlave:
    def __init__(self, dut, config):
        self.dut = dut
        self.config = config

    async def respond_to_command(self):
        while True:
            await RisingEdge(self.dut.clk)
            if self.dut.cs.value == self.config.cs_active_low:
                await self.process_command()

    async def process_command(self):
        command = await self.read_byte()
        if command == 0x03:
            address = await self.read_address()
            data = self.get_data(address)
            await self.send_data(data)
        elif command == 0x02:
            address = await self.read_address()
            data = await self.receive_data()
            self.write_data(address, data)

    async def read_byte(self):
        byte = 0
        for _ in range(8):
            await RisingEdge(self.dut.clk)
            byte = (byte << 1) | self.dut.io.value
        return byte

    async def read_address(self):
        address = 0
        for _ in range(24):
            await RisingEdge(self.dut.clk)
            address = (address << 1) | self.dut.io.value
        return address

    async def get_data(self, address):
        # Implement your own data storage and retrieval mechanism
        data = 0xFF  # Dummy data
        return data

    async def send_data(self, data):
        for byte in data:
            for _ in range(8):
                self.dut.io.value = (byte >> 7) & 1
                byte <<= 1
                await RisingEdge(self.dut.clk)

    async def receive_data(self):
        data = []
        for _ in range(256):  # Assuming max data length
            byte = 0
            for _ in range(8):
                await RisingEdge(self.dut.clk)
                byte = (byte << 1) | self.dut.io.value
            data.append(byte)
        return data

    def write_data(self, address, data):
        # Implement your own data storage mechanism
        pass

