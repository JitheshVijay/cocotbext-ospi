class OspiBus:
    def __init__(self, dut, clk, cs, io):
        self.dut = dut
        self.clk = getattr(dut, clk)
        self.cs = getattr(dut, cs)
        self.io = [getattr(dut, f"{io}[{i}]") for i in range(8)]

    async def write(self, command, address, data, mode=0):
        # Command phase
        await self.send_command(command, mode)
        
        # Address phase
        await self.send_address(address, mode)
        
        # Data phase
        await self.send_data(data, mode)

    async def read(self, command, address, mode=0):
        # Command phase
        await self.send_command(command, mode)
        
        # Address phase
        await self.send_address(address, mode)
        
        # Data phase
        return await self.receive_data(mode)

    async def send_command(self, command, mode):
        # Only use lane 0 for the command phase
        self.io[0].value = command
        await RisingEdge(self.clk)

    async def send_address(self, address, mode):
        # Use lanes according to the mode for the address phase
        lanes = self.get_lanes(mode)
        for i in range(4):  # Assuming a 32-bit address
            for lane in lanes:
                self.io[lane].value = (address >> (i*8)) & 0xFF
            await RisingEdge(self.clk)

    async def send_data(self, data, mode):
        # Use lanes according to the mode for the data phase
        lanes = self.get_lanes(mode)
        for byte in data:
            for lane in lanes:
                self.io[lane].value = byte
            await RisingEdge(self.clk)

    async def receive_data(self, mode):
        # Use lanes according to the mode for receiving data
        lanes = self.get_lanes(mode)
        data = []
        for _ in range(len(lanes)):  # Assuming we read as many bytes as lanes
            byte = 0
            for lane in lanes:
                byte |= self.io[lane].value << (lane*8)
            data.append(byte)
            await RisingEdge(self.clk)
        return data

    def get_lanes(self, mode):
        # Map mode to lanes used
        if mode == 0:  # Single
            return [0]
        elif mode == 1:  # Dual
            return [0, 1]
        elif mode == 2:  # Quad
            return [0, 1, 2, 3]
        elif mode == 3:  # Octal
            return [0, 1, 2, 3, 4, 5, 6, 7]
        else:
            raise ValueError(f"Unsupported mode: {mode}")


