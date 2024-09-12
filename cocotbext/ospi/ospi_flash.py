import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotbext.ospi.ospi_bus import OspiBus

class OspiFlash:
    def __init__(self, dut, clk, cs, io):
        # Initialize the OspiFlash object with DUT, clock, chip select, and IO signals.
        self.dut = dut  # DUT (Device Under Test) reference
        self.clk = clk  # Clock signal
        self.cs = cs    # Chip select signal
        self.io = io    # IO signals

        self.data_store = {}  # Dictionary to store data (if needed)

        # Initialize OspiBus interface with DUT, clock, chip select, and IO signals
        self.ospi = OspiBus(dut, clk, cs, io)

    async def initialize(self):
        # Initialize the flash memory by setting control signals to default values
        self.dut.reset_n.value = 0  # Assert reset (active low)
        await Timer(20, units='ns')  # Wait for 20 ns
        self.dut.reset_n.value = 1  # Deassert reset (active low)
        await Timer(20, units='ns')  # Wait for 20 ns
        self.dut.OSPI_CS.value = 1  # Deactivate chip select (active low)
        self.dut.write_enable.value = 0  # Set write enable to low (disabled)
        self.dut.read_enable.value = 0  # Set read enable to low (disabled)
        self.dut.erase_enable.value = 0  # Set erase enable to low (disabled)
        self.dut.data_in.value = 0  # Set data input to 0
        self.dut.address.value = 0  # Set address to 0
        self.dut.HOLD_N.value = 0  # Assert HOLD_N (active low)

    async def write(self, address, data, mode):
        # Write data to the flash memory at the specified address and mode
        command = {
            0: 0x02,  # Page program command for single mode
            1: 0xA2,  # Extended program command for dual mode
            2: 0x32,  # Quad page program command
            3: 0x38,  # Octal page program command
        }.get(mode, None)  # Get the command for the specified mode

        if command is None:
            raise ValueError("Unsupported write mode: {}".format(mode))  # Raise error for unsupported mode

        # Activate chip select (low)
        self.dut.OSPI_CS.value = 0

        # Set address for write operation
        self.dut.address.value = address

        # Set write enable to high (enabled)
        self.dut.write_enable.value = 1
        self.dut._log.info(f"write_enable set to 1 for mode {mode}")

        # Wait for a clock cycle to ensure signal propagation
        await RisingEdge(self.dut.OSPI_CLK)

        # Handle writing byte by byte, distributing bits across OSPI_IO based on mode
        for byte in data:
            self.dut.OSPI_IO.value = byte  # Set the data on OSPI_IO lines

            # Wait for one clock cycle after setting the data
            await RisingEdge(self.dut.OSPI_CLK)

        # Set write enable back to low (disabled) after the data is written
        self.dut.write_enable.value = 0
        self.dut._log.info("write_enable set to 0")

        # Perform the actual write operation using the OspiBus interface
        await self.ospi.write(command, address, data, mode)

        # Deactivate chip select (high)
        self.dut.OSPI_CS.value = 1
        self.dut.write_enable.value = 0

        await Timer(100, units='ns')  # Wait for 100 ns

        # Verify the write operation by reading back the data
        verify_data = await self.read(address, len(data), mode)
        assert verify_data == data, f"Verification failed: Expected {data}, got {verify_data}"  # Check if the written data matches the expected data

    async def read(self, address, length, mode):
        # Read data from the flash memory at the specified address and mode
        command = {
            0: 0x03,  # Single mode read command
            1: 0xBB,  # Dual mode read command
            2: 0xEB,  # Quad mode read command
            3: 0x0B,  # Octal mode read command
        }.get(mode, None)  # Get the command for the specified mode

        if command is None:
            raise ValueError(f"Unsupported read mode: {mode}")  # Raise error for unsupported mode

        # Activate chip select (low)
        self.dut.OSPI_CS.value = 0

        # Set address for read operation
        self.dut.address.value = address

        # Enable read operation
        self.dut.read_enable.value = 1

        # Wait for a clock cycle
        await RisingEdge(self.dut.OSPI_CLK)

        read_data = []  # List to store read data
        for _ in range(length):
            byte = self.dut.OSPI_IO.value  # Read data from OSPI_IO lines
            if 'z' in byte.binstr:
                # Handle high-impedance state
                read_data.append(None)  # or any other value to represent undefined data
            else:
                byte_int = byte.integer  # Convert BinaryValue to integer

                if mode == 1:
                    # Swap nibbles for dual mode
                    byte_int = ((byte_int & 0xF0) >> 4) | ((byte_int & 0x0F) << 4)
                elif mode == 2:
                    # Rearrange bits for quad mode
                    byte_int = (
                        ((byte_int & 0xC0) >> 6) |
                        ((byte_int & 0x30) >> 2) |
                        ((byte_int & 0x0C) << 2) |
                        ((byte_int & 0x03) << 6)
                    )
                elif mode == 3:
                    # Reverse bits for octal mode
                    byte_int = int(f"{byte_int:08b}"[::-1], 2)

                read_data.append(byte_int)  # Append the processed byte to read_data

            await RisingEdge(self.clk)  # Wait for the next clock cycle

        return read_data  # Return the read data

    async def erase(self, address, mode):
        # Erase data in the flash memory at the specified address and mode
        command = {
            0: 0x20,  # Sector erase command
            1: 0xD8,  # Block erase command
            2: 0xC7,  # Chip erase command
        }.get(mode, None)  # Get the command for the specified mode

        if command is None:
            raise ValueError("Unsupported erase mode: {}".format(mode))  # Raise error for unsupported mode

        self.dut._log.info(f"Erasing at address {address:#04x} in mode: {mode}")

        # Activate chip select (low)
        self.dut.OSPI_CS.value = 0

        # Set address for erase (if applicable)
        if mode != 2:  # Chip erase does not need an address
            self.dut.address.value = address
        
        # Set erase enable to high (enabled)
        self.dut.erase_enable.value = 1
        await RisingEdge(self.dut.OSPI_CLK)

        # Send the erase command using OspiBus interface
        await self.ospi.erase(command, address, mode)

        # Deactivate chip select (high)
        self.dut.OSPI_CS.value = 1

        # Set erase enable back to low (disabled)
        self.dut.erase_enable.value = 0
        self.dut._log.info("erase_enable set to 0")

        # Wait for the erase operation to complete
        await Timer(1000, units='ns')

        self.dut._log.info("Erase operation completed")

    async def fast_read(self, address, length, mode=0):
        # Perform a fast read operation using the OspiBus interface
        return await self.ospi.read(0x0B, address, mode, length)

    async def hold_operation(self):
        """Assert HOLD_N for hold operation."""
        self.dut._log.info("Asserting HOLD_N (Hold Operation)")
        self.dut.HOLD_N.value = 0  # Assert HOLD_N (active low)
        await Timer(10, units='ns')  # Simulate hold duration

    async def release_hold(self):
        """Deassert HOLD_N for hold release."""
        self.dut._log.info("Deasserting HOLD_N (Release Hold)")
        self.dut.HOLD_N.value = 1  # Release HOLD_N (inactive)
        await Timer(10, units='ns')  # Simulate release duration




