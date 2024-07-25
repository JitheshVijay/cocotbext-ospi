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

    async def write(self, address, data, mode):
        command = {
            0: 0x02,  
            1: 0xA2,  
            2: 0x32,  
        }.get(mode, None)

        if command is None:
            raise ValueError("Unsupported write mode: {}".format(mode))

        self.dut._log.info(f"Writing to address {address:#04x} data: {data} in mode: {mode}")

        # Update data store
        self.data_store[address] = data

        # Perform the actual write operation using the OspiBus interface
        await self.ospi.write(command, address, data, mode)

        await Timer(100, units='ns')

        # Read back to verify write operation
        verify_data = await self.ospi.read(command, address, mode, len(data))
        self.dut._log.info(f"Data read back from address {address:#04x}: {verify_data}")
        assert verify_data == data, f"Verification failed: Expected {data}, got {verify_data}"

    async def read(self, address, length, mode):
        command = {
            0: 0x03,  # Single mode read
            1: 0xBB,  # Dual mode read
            2: 0xEB,  # Quad mode read
        }.get(mode, None)

        if command is None:
            raise ValueError("Unsupported read mode: {}".format(mode))

        # Perform the actual read operation using the OspiBus interface
        read_data = await self.ospi.read(command, address, mode, length)

        self.dut._log.info(f"Reading from address {address:#04x} length: {length} in mode: {mode}")
        self.dut._log.info(f"Data read: {read_data}")

        expected_data = self.data_store.get(address, [0x00] * length)
        self.dut._log.info(f"Expected data: {expected_data}, Read data: {read_data}")
        assert read_data == expected_data, (
            f"Read data mismatch at address {address:#04x}. Expected: {expected_data}, Actual: {read_data}"
        )

        return read_data

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






