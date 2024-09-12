import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb.binary import BinaryValue

class OspiBus:
    def __init__(self, dut, clk, cs, io):
        """
        Initialize the OspiBus object.
        
        Parameters:
        dut -- Device Under Test (DUT) reference
        clk -- Clock signal
        cs -- Chip Select signal
        io -- I/O signals
        """
        self.dut = dut  # Store reference to DUT
        self.clk = clk  # Store reference to clock
        self.cs = cs    # Store reference to chip select
        self.io = io    # Store reference to I/O signals

    def assign_io_signals(self, byte, mode):
        """
        Assign byte to OSPI_IO signals based on the operating mode.
        
        Parameters:
        byte -- Byte value to assign to I/O signals
        mode -- Mode determining how to assign bits to I/O signals
        """
        if mode == 0:
            # Single IO mode - all 8 bits go to OSPI_IO
            self.dut.OSPI_IO.value = byte  # Directly assign byte to OSPI_IO
        elif mode == 1:
            # Dual IO mode - 4 bits in lower half, 4 bits in upper half
            self.dut.OSPI_IO.value = ((byte & 0xF0) >> 4) | ((byte & 0x0F) << 4)
        elif mode == 2:
            # Quad IO mode - 2 bits in each quarter
            self.dut.OSPI_IO.value = (
                ((byte & 0xC0) >> 6) |   # Top 2 bits to OSPI_IO[0]
                ((byte & 0x30) >> 2) |   # Next 2 bits to OSPI_IO[1]
                ((byte & 0x0C) << 2) |   # Next 2 bits to OSPI_IO[2]
                ((byte & 0x03) << 6)     # Bottom 2 bits to OSPI_IO[3]
            )
        elif mode == 3:
            # Octal IO mode - reverse the bits
            self.dut.OSPI_IO.value = int(f"{byte:08b}"[::-1], 2)
        else:
            raise ValueError(f"Unsupported mode: {mode}")  # Raise error for unsupported modes

    async def send_command(self, command, mode):
        """
        Send a command based on the number of lanes.
        
        Parameters:
        command -- Command to send
        mode -- Mode for how to send the command
        """
        lanes = self.get_lanes(mode)  # Get active lanes based on mode
        command_bits = BinaryValue(command, n_bits=8, bigEndian=False)  # Convert command to BinaryValue
        self.dut._log.info(f"Sending command {command_bits.binstr} on lanes {lanes} in mode {mode}")

        self.assign_io_signals(command_bits.integer, mode)  # Assign command byte to IO signals
        await RisingEdge(self.clk)  # Wait for the rising edge of the clock

    async def write(self, command, address, data, mode=0):
        """
        Perform a write operation, spreading across lanes.
        
        Parameters:
        command -- Command to initiate the write operation
        address -- Address to write data to
        data -- Data to write
        mode -- Mode for how to send the data
        """
        self.dut._log.info(f"Write operation: Command: {command}, Address: {address}, Data: {data}, Mode: {mode}")
        await self.send_command(command, mode)  # Send the command
        await self.send_address(address, mode)  # Send the address
        await self.send_data(data, mode)  # Send the data

    async def read(self, command, address, mode, length):
        """
        Perform a read operation across lanes.
        
        Parameters:
        command -- Command to initiate the read operation
        address -- Address to read data from
        mode -- Mode for how to receive the data
        length -- Length of data to read
        """
        self.dut._log.info(f"Read operation: Command: {command}, Address: {address}, Length: {length}, Mode: {mode}")
        await self.send_command(command, mode)  # Send the command
        await self.send_address(address, mode)  # Send the address
        data = await self.receive_data(mode, length)  # Receive the data
        return data  # Return the received data

    async def erase(self, command, address, mode=0):
        """
        Perform an erase operation.
        
        Parameters:
        command -- Command to initiate the erase operation
        address -- Address to erase
        mode -- Mode for how to perform the erase
        """
        self.dut._log.info(f"Erase operation: Command: {command}, Address: {address}, Mode: {mode}")
        self.cs.value = 0  # Assert chip select
        await self.send_command(command, mode)  # Send the command
        await self.send_address(address, mode)  # Send the address
        self.cs.value = 1  # Deassert chip select

    async def send_byte(self, byte, mode):
        """
        Send a byte by spreading bits across lanes.
        
        Parameters:
        byte -- Byte to send
        mode -- Mode for how to send the byte
        """
        if isinstance(byte, BinaryValue):
            byte_value = byte  # Use existing BinaryValue if provided
        else:
            byte_value = BinaryValue(byte, n_bits=8, bigEndian=False)  # Convert to BinaryValue if not provided
        self.dut._log.info(f"Sending byte {byte_value.binstr} in mode {mode}")

        self.assign_io_signals(byte_value.integer, mode)  # Assign byte to IO signals
        await RisingEdge(self.clk)  # Wait for the rising edge of the clock

    async def send_address(self, address, mode):
        """
        Send an address byte-by-byte.
        
        Parameters:
        address -- Address to send
        mode -- Mode for how to send the address
        """
        if isinstance(address, (list, tuple)):
            # Convert list/tuple of bytes to a single integer
            address = int(''.join(format(x, '08b') for x in address), 2)
        address_value = BinaryValue(address, n_bits=32, bigEndian=False)  # Convert address to BinaryValue
        self.dut._log.info(f"Sending address {address_value.binstr} in mode {mode}")

        for i in range(4):  # Assuming a 32-bit address, send in 4 bytes
            byte = (address >> (24 - 8 * i)) & 0xFF  # Extract each byte from the address
            await self.send_byte(byte, mode)  # Send each byte

    async def send_data(self, data, mode):
        """
        Send data byte-by-byte.
        
        Parameters:
        data -- Data to send
        mode -- Mode for how to send the data
        """
        self.dut._log.info(f"Sending data {data} in mode {mode}")
        for byte in data:
            await self.send_byte(byte, mode)  # Send each byte of data

    async def receive_data(self, mode, length):
        """
        Receive data byte-by-byte.
        
        Parameters:
        mode -- Mode for how to receive the data
        length -- Length of data to receive
        """
        self.dut._log.info(f"Receiving data of length {length} in mode {mode}")
        data = []
        for _ in range(length):
            byte = await self.receive_byte(mode)  # Receive each byte
            data.append(byte)  # Append received byte to data list
        return data  # Return the received data

    async def receive_byte(self, mode):
        """
        Receive a byte from the bus.
        
        Parameters:
        mode -- Mode for how to receive the byte
        """
        byte = BinaryValue(n_bits=8, bigEndian=False)  # Initialize BinaryValue to store received byte
        lanes = self.get_lanes(mode)  # Get active lanes based on mode
        for bit_position in range(8):
            await RisingEdge(self.clk)  # Wait for the rising edge of the clock
            bit_value = 0
            for lane in lanes:
                bit_value = self.io[lane].value  # Read bit value from each lane
            byte[bit_position] = int(bit_value)  # Assign bit value to byte
        self.dut._log.info(f"Received byte: {byte.binstr}")  # Log received byte
        return byte  # Return the received byte

    def get_lanes(self, mode):
        """
        Get the active lanes based on the mode.
        
        Parameters:
        mode -- Mode for how to determine active lanes
        
        Returns:
        List of active lanes
        """
        if mode == 0:
            return [0]  # Single-lane mode
        elif mode == 1:
            return [0, 1]  # Dual-lane mode
        elif mode == 2:
            return [0, 1, 2, 3]  # Quad-lane mode
        elif mode == 3:
            return [0, 1, 2, 3, 4, 5, 6, 7]  # Octal-lane mode
        else:
            raise ValueError(f"Unsupported mode: {mode}")  # Raise error for unsupported modes

