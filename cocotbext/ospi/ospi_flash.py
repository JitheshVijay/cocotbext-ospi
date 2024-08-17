import cocotb
from cocotb.triggers import Timer, RisingEdge
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
        self.dut.OSPI_CS.value = 1  
        self.dut.write_enable.value = 0
        self.dut.read_enable.value = 0
        self.dut.erase_enable.value = 0
        self.dut.data_in.value = 0
        self.dut.address.value = 0
        self.dut.HOLD_N.value = 0


    async def write(self, address, data, mode):
        command = {
            0: 0x02,  # Page program command
            1: 0xA2,  # Extended program command
            2: 0x32,  # Quad page program command
            3: 0x38,  # Octal page program command 
        }.get(mode, None)

        # Activate chip select (low)
        self.dut.OSPI_CS.value = 0

        # Set address
        self.dut.address.value = address
        
        # Set write enable
        self.dut.write_enable.value = 1
        self.dut._log.info("write_enable set to 1")

        # Wait for a clock cycle to ensure signal propagation
        await RisingEdge(self.dut.OSPI_CLK)

        # Handle single byte and multi-byte writes
        for byte in data:
            self.dut.data_in.value = byte
            await RisingEdge(self.dut.OSPI_CLK)

        # Set write enable back to 0 after the data is written
        self.dut.write_enable.value = 0
        self.dut._log.info("write_enable set to 0")

        # Perform the actual write operation using the OspiBus interface
        self.dut._log.info("Before OSPI write operation")
        await self.ospi.write(command, address, data, mode)

        # Deactivate chip select (high)
        self.dut.OSPI_CS.value = 1
        self.dut._log.info("After OSPI write operation")

        await Timer(100, units='ns')

        # Read back to verify write operation
        self.dut._log.info("Before OSPI read operation for verification")
        verify_data = await self.ospi.read(command, address, mode, len(data))
        self.dut._log.info("After OSPI read operation for verification")
        self.dut._log.info(f"Data read back from address {address:#04x}: {verify_data}")

        # Verification of written data
        assert verify_data == data, f"Verification failed: Expected {data}, got {verify_data}"





    async def read(self, address, length, mode):
        command = {
            0: 0x03,  # Single mode read
            1: 0xBB,  # Dual mode read
            2: 0xEB,  # Quad mode read
            3: 0x0B,  # Octal mode read
        }.get(mode, None)

        if command is None:
            raise ValueError("Unsupported read mode: {}".format(mode))

        # Activate chip select (low)
        self.dut.OSPI_CS.value = 0

        # Set address
        self.dut.address.value = address
        
        # Enable read
        self.dut.read_enable.value = 1
        self.dut._log.info("read_enable set to 1")

        # Wait for a clock cycle to ensure signal propagation
        await RisingEdge(self.dut.OSPI_CLK)

        # Perform the actual read operation using the OspiBus interface
        read_data = await self.ospi.read(command, address, mode, length)

        # Deactivate chip select (high)
        self.dut.OSPI_CS.value = 1
        
        # Disable read
        self.dut.read_enable.value = 0
        self.dut._log.info("read_enable set to 0")

        self.dut._log.info(f"Reading from address {address:#04x} length: {length} in mode: {mode}")
        self.dut._log.info(f"Data read: {read_data}")

        expected_data = self.data_store.get(address, [0x00] * length)
        self.dut._log.info(f"Expected data: {expected_data}, Read data: {read_data}")
        assert read_data == expected_data, (
            f"Read data mismatch at address {address:#04x}. Expected: {expected_data}, Actual: {read_data}"
        )

        return read_data

    
    async def erase(self, address, mode):
        command = {
            0: 0x20,  # Sector erase command (example)
            1: 0xD8,  # Block erase command (example)
            2: 0xC7,  # Chip erase command (example)
        }.get(mode, None)

        if command is None:
            raise ValueError("Unsupported erase mode: {}".format(mode))

        self.dut._log.info(f"Erasing at address {address:#04x} in mode: {mode}")

        # Activate chip select (low)
        self.dut.OSPI_CS.value = 0

        # Set address for erase (if applicable)
        if mode != 2:  # Chip erase does not need an address
            self.dut.address.value = address
        
        # Set erase enable (if applicable)
        self.dut.erase_enable.value = 1
        await RisingEdge(self.dut.OSPI_CLK)

        # Send the erase command
        await self.ospi.erase(command, address, mode)

        # Deactivate chip select (high)
        self.dut.OSPI_CS.value = 1

        # Set erase enable back to 0
        self.dut.erase_enable.value = 0
        self.dut._log.info("erase_enable set to 0")

        # Wait for the erase operation to complete
        await Timer(1000, units='ns')

        self.dut._log.info("Erase operation completed")



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




