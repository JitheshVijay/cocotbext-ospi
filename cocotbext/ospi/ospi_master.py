import cocotb
from cocotb.triggers import Timer, RisingEdge
from .ospi_bus import OspiBus
from .ospi_config import OspiConfig

class OspiMaster:
    def __init__(self, bus: OspiBus, config: OspiConfig):
        self.bus = bus
        self.config = config

    async def write(self, data):
        await self._start_transaction()
        for byte in data:
            await self._write_byte(byte)
        await self._end_transaction()

    async def read(self, length):
        await self._start_transaction()
        data = [await self._read_byte() for _ in range(length)]
        await self._end_transaction()
        return data

    async def _start_transaction(self):
        self.bus.cs.value = 0 if self.config.cs_active_low else 1
        await Timer(1, units='ns')

    async def _end_transaction(self):
        self.bus.cs.value = 1 if self.config.cs_active_low else 0
        await Timer(1, units='ns')

    async def _write_byte(self, byte):
        for i in range(2):
            nibble = (byte >> (4 * (1 - i))) & 0xF
            self.bus.io0.value = (nibble >> 0) & 1
            self.bus.io1.value = (nibble >> 1) & 1
            self.bus.io2.value = (nibble >> 2) & 1
            self.bus.io3.value = (nibble >> 3) & 1
            if self.config.bus_width == 'octal':
                self.bus.io4.value = (nibble >> 4) & 1
                self.bus.io5.value = (nibble >> 5) & 1
                self.bus.io6.value = (nibble >> 6) & 1
                self.bus.io7.value = (nibble >> 7) & 1
            await RisingEdge(self.bus.sclk)
        await Timer(1, units='ns')

    async def _read_byte(self):
        byte = 0
        for i in range(2):
            await RisingEdge(self.bus.sclk)
            nibble = (
                (int(self.bus.io3.value) << 3) |
                (int(self.bus.io2.value) << 2) |
                (int(self.bus.io1.value) << 1) |
                int(self.bus.io0.value)
            )
            if self.config.bus_width == 'octal':
                nibble |= (
                    (int(self.bus.io4.value) << 4) |
                    (int(self.bus.io5.value) << 5) |
                    (int(self.bus.io6.value) << 6) |
                    (int(self.bus.io7.value) << 7)
                )
            byte = (byte << 4) | nibble
        return byte

