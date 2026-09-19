"""Bus-level OSPI master.

Timing is SPI mode 0, which is what flash parts use: the master launches
data while the clock is low and the device samples it on the rising edge;
the device launches its data while the clock is low and the master samples
on the rising edge. Nothing is ever read on the edge that changes it.

Every transfer method assumes the clock is **low on entry and leaves it low
on exit**, so transfers chain without a gap. Waiting for a falling edge at
the start of each one instead would let the rising edge in between clock an
undriven bit into the device, losing the first bit of every byte.

Lane count is per phase, not per transaction. A real octal read sends its
opcode on a single lane and only widens for the address, mode byte and data,
so every method takes its own ``lanes``.
"""

from cocotb.triggers import Edge, FallingEdge, RisingEdge

VALID_LANES = (1, 2, 4, 8)


class OspiMaster:
    def __init__(self, bus, cs_active_low: bool = True):
        self.bus = bus
        self.cs_active_low = cs_active_low

    @staticmethod
    def _check(lanes: int):
        if lanes not in VALID_LANES:
            raise ValueError(
                f"lanes must be one of {VALID_LANES}, not {lanes!r}"
            )

    # ── framing ──────────────────────────────────────────────────────

    async def start(self):
        """Assert chip select, leaving the clock low and ready to transfer."""
        await FallingEdge(self.bus.clk)
        self.bus.cs.value = 0 if self.cs_active_low else 1

    async def stop(self):
        """Release the bus and deassert chip select."""
        self.bus.io_oe.value = 0
        self.bus.cs.value = 1 if self.cs_active_low else 0
        await FallingEdge(self.bus.clk)

    # ── driving ──────────────────────────────────────────────────────

    async def send_byte(self, byte: int, lanes: int = 1):
        """Send one byte most-significant bits first, ``lanes`` bits a clock."""
        self._check(lanes)
        mask = (1 << lanes) - 1
        for shift in range(8 - lanes, -1, -lanes):
            # Already in a low phase: drive now, let the rising edge sample it.
            self.bus.io_out.value = (byte >> shift) & mask
            # Only the lanes carrying data are driven; in single-lane mode
            # io1 belongs to the device.
            self.bus.io_oe.value = mask
            await RisingEdge(self.bus.clk)
            await FallingEdge(self.bus.clk)

    async def send_address(self, address: int, lanes: int = 1, width: int = 24):
        """Send an address, most-significant byte first."""
        for shift in range(width - 8, -1, -8):
            await self.send_byte((address >> shift) & 0xFF, lanes)

    # ── turnaround and receiving ─────────────────────────────────────

    def release(self):
        """Stop driving the bus so the device can."""
        self.bus.io_oe.value = 0

    async def dummy_cycles(self, count: int):
        """Clock ``count`` cycles with the bus released.

        Wide reads need these between the address and the data so the device
        has time to turn the bus around.
        """
        self.release()
        for _ in range(count):
            await RisingEdge(self.bus.clk)
            await FallingEdge(self.bus.clk)

    def _lane_bit(self, lane: int) -> int:
        """Read one lane of the bus.

        Undriven lanes float, so the bus as a whole is rarely a clean integer
        and cannot be converted in one go -- read only the lane carrying
        data. Bit strings are most-significant first, so lane N is N places
        from the right.
        """
        bits = str(self.bus.io.value)
        bit = bits[-1 - lane]
        if bit not in "01":
            raise ValueError(
                f"io[{lane}] is '{bit}', not 0 or 1 (bus = {bits}). The device "
                f"is not driving it -- check the dummy cycle count and that "
                f"the master released the bus."
            )
        return int(bit)

    async def recv_byte(self, lanes: int = 1) -> int:
        """Read one byte the device is driving, sampling on rising edges.

        In single-lane mode the device answers on io1 (MISO); wider modes use
        the low ``lanes`` lines, most-significant first.
        """
        self._check(lanes)
        self.release()
        byte = 0
        for _ in range(8 // lanes):
            await RisingEdge(self.bus.clk)
            if lanes == 1:
                byte = (byte << 1) | self._lane_bit(1)   # io1 is MISO
            else:
                chunk = 0
                for lane in range(lanes - 1, -1, -1):
                    chunk = (chunk << 1) | self._lane_bit(lane)
                byte = (byte << lanes) | chunk
            await FallingEdge(self.bus.clk)
        return byte

    async def recv_bytes(self, count: int, lanes: int = 1) -> list:
        return [await self.recv_byte(lanes) for _ in range(count)]

    # ── double transfer rate (DTR / DDR) ─────────────────────────────
    #
    # In DTR a lane carries a bit on *both* clock edges, so an 8-lane bus
    # moves two bytes per clock and a 4-lane bus moves one. Data is set up
    # before an edge and captured on it; the device presents its own data
    # just after an edge, so the master samples on the following one.
    #
    # This is why an odd number of bytes cannot be transferred in 8D-8D-8D:
    # each clock carries two, and there is no half clock.

    async def send_byte_dtr(self, byte: int, lanes: int = 8):
        """Send one byte, ``lanes`` bits per clock edge."""
        self._check(lanes)
        mask = (1 << lanes) - 1
        for shift in range(8 - lanes, -1, -lanes):
            self.bus.io_out.value = (byte >> shift) & mask
            self.bus.io_oe.value = mask
            await Edge(self.bus.clk)

    async def send_address_dtr(self, address: int, lanes: int = 8,
                               width: int = 32):
        for shift in range(width - 8, -1, -8):
            await self.send_byte_dtr((address >> shift) & 0xFF, lanes)

    async def dummy_edges(self, count: int):
        """Clock ``count`` dummy *cycles* with the bus released.

        Counted in clocks, not edges, to match how datasheets quote them.
        """
        self.release()
        for _ in range(count):
            await RisingEdge(self.bus.clk)

    async def recv_byte_dtr(self, lanes: int = 8) -> int:
        """Read one byte the device is driving, ``lanes`` bits per edge."""
        self._check(lanes)
        self.release()
        byte = 0
        for _ in range(8 // lanes):
            await Edge(self.bus.clk)
            chunk = 0
            for lane in range(lanes - 1, -1, -1):
                chunk = (chunk << 1) | self._lane_bit(lane)
            byte = (byte << lanes) | chunk
        return byte

    async def recv_bytes_dtr(self, count: int, lanes: int = 8,
                             turnaround: int = 0) -> list:
        """Read ``count`` bytes in DTR.

        ``turnaround`` is how many edges to let pass before the first sample.
        The device presents its first data *after* the edge that ends the
        dummy phase, so sampling on that same edge catches the bus still
        released. Models that drive edge-aligned need one edge of turnaround;
        models that present data as soon as the read phase begins need none,
        so this is per-device rather than a constant.
        """
        self.release()
        for _ in range(turnaround):
            await Edge(self.bus.clk)
        return [await self.recv_byte_dtr(lanes) for _ in range(count)]
