"""Bus-level OSPI master: lane-width aware transfers on OSPI_IO."""

from cocotb.triggers import FallingEdge, RisingEdge

from .ospi_config import lanes_for_mode


class OspiBus:
    """Drives the OSPI signal bundle as the master.

    ``io_out``/``io_oe`` are the master's half of the bidirectional data bus:
    a simulator cannot have the testbench drive an ``inout`` net directly, so
    the top level splits it into a value and an output enable. Dropping
    ``io_oe`` releases the bus so the slave can drive read data onto it.

    The slave samples on the rising edge of the clock, so the master changes
    data on the falling edge and samples slave-driven data there too -- never
    reading the edge that is changing the value.
    """

    def __init__(self, dut, clk, cs, io, io_out, io_oe, mode_sig=None):
        self.dut = dut
        self.clk = clk
        self.cs = cs
        self.io = io
        self.io_out = io_out
        self.io_oe = io_oe
        self.mode_sig = mode_sig

    @classmethod
    def from_entity(cls, entity, prefix: str = "OSPI"):
        """Pick the bus signals out of ``entity`` by name."""
        return cls(
            dut=entity,
            clk=getattr(entity, f"{prefix}_CLK"),
            cs=getattr(entity, f"{prefix}_CS"),
            io=getattr(entity, f"{prefix}_IO"),
            io_out=entity.io_out,
            io_oe=entity.io_oe,
            mode_sig=getattr(entity, "mode", None),
        )

    def set_mode(self, mode: int):
        """Select the lane width for subsequent transfers."""
        lanes_for_mode(mode)  # validates
        if self.mode_sig is not None:
            self.mode_sig.value = mode

    async def start_transaction(self):
        await FallingEdge(self.clk)
        self.cs.value = 0
        self.io_oe.value = 1

    async def end_transaction(self):
        await FallingEdge(self.clk)
        self.io_oe.value = 0
        self.cs.value = 1

    async def send_byte(self, byte: int, mode: int):
        """Send one byte, most-significant bits first, ``lanes`` at a time."""
        lanes = lanes_for_mode(mode)
        mask = (1 << lanes) - 1
        for shift in range(8 - lanes, -1, -lanes):
            self.io_out.value = (byte >> shift) & mask
            self.io_oe.value = 1
            await RisingEdge(self.clk)   # slave latches here
            await FallingEdge(self.clk)  # safe point to change the data

    async def send_address(self, address: int, mode: int):
        """Send the 24-bit address, most-significant byte first."""
        for shift in (16, 8, 0):
            await self.send_byte((address >> shift) & 0xFF, mode)

    def release(self):
        """Stop driving OSPI_IO so the slave can drive it."""
        self.io_oe.value = 0

    async def recv_byte(self, mode: int) -> int:
        """Read one byte the slave is driving, sampling mid-bit."""
        lanes = lanes_for_mode(mode)
        mask = (1 << lanes) - 1
        byte = 0
        for _ in range(8 // lanes):
            byte = (byte << lanes) | (int(self.io.value) & mask)
            await FallingEdge(self.clk)
        return byte
