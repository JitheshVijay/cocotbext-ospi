"""High-level driver for the OSPI flash model."""

from cocotb.triggers import FallingEdge, RisingEdge, Timer

from .ospi_bus import OspiBus
from .ospi_config import OspiConfig, lanes_for_mode

CMD_WRITE = 0x02
CMD_READ = 0x03
CMD_ERASE = 0x20


class OspiFlash:
    """Page-program / read / erase against ``ospi_flash.v``.

    Every operation is one chip-select framed transaction carrying a 24-bit
    address. ``mode`` picks the lane width -- 0 single, 1 dual, 2 quad,
    3 octal -- and the same byte round-trips through any of them.
    """

    def __init__(self, dut, bus: OspiBus = None, config: OspiConfig = None):
        self.dut = dut
        self.bus = bus or OspiBus.from_entity(dut)
        self.config = config or OspiConfig()

    async def initialize(self):
        """Pulse reset and leave the bus idle with hold released."""
        self.bus.cs.value = 1
        self.bus.io_oe.value = 0
        self.bus.io_out.value = 0
        # HOLD_N is active low: high means "not held", which is what a normal
        # transaction needs. Driving it low here would freeze the interface.
        self.dut.HOLD_N.value = 1
        self.dut.reset_n.value = 0
        await Timer(20, units="ns")
        self.dut.reset_n.value = 1
        await RisingEdge(self.bus.clk)

    async def write(self, address: int, data: int, mode: int = 0):
        """Program one byte at ``address``."""
        lanes_for_mode(mode)
        self.bus.set_mode(mode)
        await self.bus.start_transaction()
        await self.bus.send_byte(CMD_WRITE, mode)
        await self.bus.send_address(address, mode)
        await self.bus.send_byte(data & 0xFF, mode)
        await self.bus.end_transaction()

    async def read(self, address: int, mode: int = 0) -> int:
        """Read the byte at ``address``."""
        lanes_for_mode(mode)
        self.bus.set_mode(mode)
        await self.bus.start_transaction()
        await self.bus.send_byte(CMD_READ, mode)
        await self.bus.send_address(address, mode)

        # Release during the dummy clock so master and slave never both drive.
        self.bus.release()
        await RisingEdge(self.bus.clk)
        await FallingEdge(self.bus.clk)

        value = await self.bus.recv_byte(mode)
        await self.bus.end_transaction()
        return value

    async def erase(self, address: int, mode: int = 0):
        """Erase ``address`` back to 0xFF."""
        lanes_for_mode(mode)
        self.bus.set_mode(mode)
        await self.bus.start_transaction()
        await self.bus.send_byte(CMD_ERASE, mode)
        await self.bus.send_address(address, mode)
        await self.bus.end_transaction()

    async def hold(self):
        """Assert HOLD_N, freezing the interface."""
        self.dut.HOLD_N.value = 0
        await Timer(10, units="ns")

    async def release_hold(self):
        """Deassert HOLD_N, resuming normal operation."""
        self.dut.HOLD_N.value = 1
        await Timer(10, units="ns")
