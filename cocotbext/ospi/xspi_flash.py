"""Driver for real xSPI (octal) NOR flash parts.

Unlike the generic :class:`~cocotbext.ospi.ospi_flash.OspiFlash`, this one
follows a :class:`~cocotbext.ospi.devices.profile.DeviceProfile` describing
an actual device -- its opcodes, how wide its addresses are, how many dummy
cycles each command takes, and how it is switched into octal.

The flow matches how a real controller brings a part up:

    flash = XspiFlash(dut, MX25UM51345G)
    await flash.initialize()          # single-lane SPI
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]
    await flash.enter_octal()         # write CR2, switch protocol
    assert await flash.read_id() == [0xC2, 0x80, 0x3A]   # now in octal
"""

from cocotb.triggers import RisingEdge

from .devices.profile import (
    LANES, IS_DTR, PROTO_1S_1S_1S, PROTO_8S_8S_8S, PROTO_8D_8D_8D,
)
from .ospi_bus import OspiBus
from .ospi_master import OspiMaster

STATUS_WIP = 0x01
STATUS_WEL = 0x02


class XspiFlash:
    def __init__(self, dut, profile, bus: OspiBus = None):
        self.dut = dut
        self.profile = profile
        self.bus = bus or OspiBus.from_entity(dut)
        self.master = OspiMaster(self.bus)
        self.protocol = PROTO_1S_1S_1S

    # ── protocol helpers ─────────────────────────────────────────────

    @property
    def lanes(self) -> int:
        return LANES[self.protocol]

    @property
    def octal(self) -> bool:
        return self.protocol != PROTO_1S_1S_1S

    @property
    def dtr(self) -> bool:
        return IS_DTR[self.protocol]

    def _op(self, name):
        try:
            return self.profile.ops[name]
        except KeyError:
            raise ValueError(
                f"{self.profile.name} has no {name} operation in this profile"
            ) from None

    async def _send_byte(self, byte):
        if self.dtr:
            await self.master.send_byte_dtr(byte, lanes=self.lanes)
        else:
            await self.master.send_byte(byte, lanes=self.lanes)

    async def _send_command(self, op):
        """Send the opcode, plus its extension when in octal.

        The extension is what the vendors differ on: Macronix sends the
        complement, Micron repeats the opcode. A part that gets the wrong
        extension ignores the command entirely.
        """
        await self._send_byte(op.opcode)
        if self.octal:
            await self._send_byte(self.profile.extension(op.opcode))

    async def _transfer(self, name, address=None, write=None, read=0):
        """One chip-select framed command, shaped by the profile."""
        op = self._op(name)
        addr_bytes, dummy = op.shape(self.octal)

        await self.master.start()
        await self._send_command(op)

        if addr_bytes:
            if self.dtr:
                await self.master.send_address_dtr(
                    address or 0, lanes=self.lanes, width=addr_bytes * 8
                )
            else:
                await self.master.send_address(
                    address or 0, lanes=self.lanes, width=addr_bytes * 8
                )

        if dummy:
            if self.dtr:
                await self.master.dummy_edges(dummy)
            else:
                await self.master.dummy_cycles(dummy)

        data = None
        if write is not None:
            for byte in write:
                await self._send_byte(byte & 0xFF)
        elif read:
            if self.dtr:
                data = await self.master.recv_bytes_dtr(read, lanes=self.lanes)
            else:
                data = await self.master.recv_bytes(read, lanes=self.lanes)

        await self.master.stop()
        return data

    # ── bring-up ─────────────────────────────────────────────────────

    async def initialize(self):
        """Put the bus in a known state; the part starts in single-lane SPI."""
        self.bus.io_oe.value = 0
        self.bus.io_out.value = 0
        if self.bus.hold is not None:
            self.bus.hold.value = 1     # active low: high means not held
        self.protocol = PROTO_1S_1S_1S

        # The model frames on chip-select edges, so drive one explicitly
        # rather than relying on initial values.
        self.bus.cs.value = 1
        await RisingEdge(self.bus.clk)
        self.bus.cs.value = 0
        await RisingEdge(self.bus.clk)
        self.bus.cs.value = 1
        await RisingEdge(self.bus.clk)

    async def enter_octal(self, protocol=None):
        """Switch the part into octal using its own documented sequence.

        Defaults to whichever octal protocol the part is built around --
        DTR for Micron, STR for the Macronix profile here.
        """
        if protocol is None:
            protocol = self.profile.default_octal
        if protocol not in self.profile.supported:
            raise ValueError(
                f"{self.profile.name} profile does not model {protocol}; "
                f"supported: {', '.join(self.profile.supported)}"
            )
        if self.profile.enter_octal is None:
            raise ValueError(f"{self.profile.name} has no octal entry sequence")
        await self.profile.enter_octal(self, protocol)

    async def exit_octal(self):
        if self.profile.exit_octal is None:
            raise ValueError(f"{self.profile.name} has no octal exit sequence")
        await self.profile.exit_octal(self)

    # ── registers ────────────────────────────────────────────────────

    async def read_id(self) -> list:
        return await self._transfer("RDID", address=0, read=3)

    async def read_status(self) -> int:
        return (await self._transfer("RDSR", address=0, read=1))[0]

    async def write_enable(self):
        await self._transfer("WREN")

    async def write_disable(self):
        await self._transfer("WRDI")

    async def read_register(self, cr2_address: int) -> int:
        """Read one of the address-mapped configuration registers."""
        return (await self._transfer("RDCR2", address=cr2_address, read=1))[0]

    async def write_register(self, cr2_address: int, value):
        """Write a configuration register.

        ``value`` may be a list: 8D-8D-8D cannot transfer an odd number of
        bytes, so leaving octal means writing two consecutive registers in
        one go.
        """
        if isinstance(value, int):
            value = [value]
        await self._transfer("WRCR2", address=cr2_address, write=value)

    async def is_busy(self) -> bool:
        return bool(await self.read_status() & STATUS_WIP)

    async def wait_ready(self, timeout_polls: int = 1000):
        for _ in range(timeout_polls):
            if not await self.is_busy():
                return
        raise TimeoutError(f"WIP still set after {timeout_polls} status polls")

    # ── array ────────────────────────────────────────────────────────

    async def read(self, address: int, length: int = 1) -> list:
        """Read the array using whichever read the current protocol calls for."""
        name = "8READ" if self.octal else "READ"
        return await self._transfer(name, address=address, read=length)

    async def read_byte(self, address: int) -> int:
        return (await self.read(address, 1))[0]

    async def program(self, address: int, data, wait: bool = True):
        """Page program. Sets WEL first, as the part requires.

        NOR programming clears bits only, so program into erased space.
        """
        if isinstance(data, int):
            data = [data]
        await self.write_enable()
        await self._transfer("PP", address=address, write=data)
        if wait:
            await self.wait_ready()

    async def erase_sector(self, address: int, wait: bool = True):
        await self.write_enable()
        await self._transfer("SE", address=address)
        if wait:
            await self.wait_ready()
