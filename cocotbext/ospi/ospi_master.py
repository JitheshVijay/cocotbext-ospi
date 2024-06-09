import cocotb
from cocotb.triggers import Timer, RisingEdge
from .ospi_bus import OspiBus
from .ospi_config import OspiConfig

class OspiMaster:
    def __init__(self, bus: OspiBus, config: OspiConfig):
        self.bus = bus    # OSPI bus signals
        self.config = config  # OSPI configuration

    async def write(self, data):
        await self._start_transaction()  # Start the transaction
        for byte in data:
            await self._write_byte(byte)  # Write each byte
        await self._end_transaction()  # End the transaction

    async def read(self, length):
        await self._start_transaction()  # Start the transaction
        data = [await self._read_byte() for _ in range(length)]  # Read bytes
        await self._end_transaction()  # End the transaction
        return data  # Return the read data

    async def _start_transaction(self):
        self.bus.cs.value = 0 if self.config.cs_active_low else 1  # Assert chip select
        await Timer(1, units='ns')  # Wait for 1 ns

    async def _end_transaction(self):
        self.bus.cs.value = 1 if self.config.cs_active_low else 0  # Deassert chip select
        await Timer(1, units='ns')  # Wait for 1 ns

    async def _write_byte(self, byte):
        for i in range(2):  # Two cycles for 8 bits, as each cycle writes 4 bits
            nibble = (byte >> (4 * (1 - i))) & 0xF  # Extract 4 bits (nibble)
            self.bus.io0.value = (nibble >> 0) & 1  # Set the value for io0
            self.bus.io1.value = (nibble >> 1) & 1  # Set the value for io1
            self.bus.io2.value = (nibble >> 2) & 1  # Set the value for io2
            self.bus.io3.value = (nibble >> 3) & 1  # Set the value for io3
            if self.config.quad_mode:
                # Additional lines for octal mode
                self.bus.io4.value = (nibble >> 4) & 1  # Set the value for io4
                self.bus.io5.value = (nibble >> 5) & 1  # Set the value for io5
                self.bus.io6.value = (nibble >> 6) & 1  # Set the value for io6
                self.bus.io7.value = (nibble >> 7) & 1  # Set the value for io7
            await RisingEdge(self.bus.sclk)
        await Timer(1, units='ns')

    async def _read_byte(self):
        byte = 0
        for i in range(2):  # Two cycles for 8 bits, as each cycle reads 4 bits
            await RisingEdge(self.bus.sclk)
            # Read 4 bits from the OSPI lines and combine them into a nibble
            nibble = (
                (int(self.bus.io3.value) << 3) |
                (int(self.bus.io2.value) << 2) |
                (int(self.bus.io1.value) << 1) |
                int(self.bus.io0.value)
            )
            if self.config.octal_mode:
                # Additional lines for octal mode
                nibble |= (
                    (int(self.bus.io4.value) << 4) |
                    (int(self.bus.io5.value) << 5) |
                    (int(self.bus.io6.value) << 6) |
                    (int(self.bus.io7.value) << 7)
                )
            byte = (byte << 4) | nibble  # Combine the nibble into the byte
        return byte
