# cocotbext-ospi

OSPI flash verification for [cocotb](https://www.cocotb.org/): a bus driver,
a device-level API over the JEDEC command set, and a NOR flash model to test
against — single, dual, quad and **octal** I/O.

Requires **cocotb 2.0+**. Tests run on Icarus Verilog.

```
pip install cocotbext-ospi
```

## Why another SPI extension

[`cocotbext-spi`](https://github.com/schang412/cocotbext-spi) covers
single-lane SPI. This one covers flash specifically, up to an eight-lane
data bus, with the write-enable latch, status polling, page program and
sector erase — and it targets cocotb 2.x.

## Usage

```python
import cocotb
from cocotb.clock import Clock
from cocotbext.ospi import OspiFlash, CMD_OIOR

@cocotb.test()
async def test_flash(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())

    flash = OspiFlash(dut)
    await flash.initialize()

    assert await flash.read_id() == [0xC2, 0x80, 0x39]

    # program() sets WEL, then polls the status register until WIP clears.
    await flash.program(0x1000, [0xDE, 0xAD, 0xBE, 0xEF])

    assert await flash.read(0x1000, 4) == [0xDE, 0xAD, 0xBE, 0xEF]
    assert await flash.read(0x1000, 4, opcode=CMD_OIOR) == [0xDE, 0xAD, 0xBE, 0xEF]

    await flash.erase_sector(0x1000)
    assert await flash.read(0x1000, 4) == [0xFF] * 4
```

## The protocol, and two things that catch people out

SPI mode 0: the master launches data while the clock is low, the device
samples it on the rising edge, and vice versa.

**The opcode is always single-lane.** Only the address, mode byte and data
widen. An octal read is *not* "everything on eight lanes" — it is one
single-lane command byte, then eight-lane address and data. Getting this
wrong is the most common reason a driver talks to nothing.

**Programming only clears bits.** NOR flash needs an erase to set a bit back
to 1. Programming `0x0F` over `0xF0` gives `0x00`, not `0x0F`.

### What it looks like on the wire

All three diagrams below are generated from a real simulation — `capture.py`
runs the transactions, Icarus dumps a VCD, and `render.py` draws it. Nothing
is drawn by hand, so they cannot drift away from what the model does.

An octal I/O read. The opcode goes out one bit per clock on a single lane;
only then does the bus widen to all eight for the address and data — a whole
byte per clock. Note the dummy cycles, where neither side drives while the
bus turns around:

![Fast read octal I/O](docs/waveforms/octal-read.svg)

The same byte read at every width. This is what the wide modes buy you —
40 clocks single-lane down to 21 octal, for one byte at the same address:

![One byte at every width](docs/waveforms/width-comparison.svg)

A status read while a program is in flight. The device answers `0x01` — WIP
set — which is what `wait_ready()` polls for:

![Read status](docs/waveforms/read-status.svg)

To regenerate them:

```
make -C docs/waveforms        # run the sim, dump capture.vcd
make -C docs/waveforms svg    # capture.vcd -> *.svg
```

### Commands

| Opcode | Name | Address | Data |
|---|---|---|---|
| `0x06` | Write enable | — | — |
| `0x04` | Write disable | — | — |
| `0x05` | Read status | — | 1 lane, repeats |
| `0x9F` | JEDEC id | — | 1 lane, 3 bytes |
| `0x03` | Read | 1 lane | 1 lane |
| `0xBB` | Fast read dual I/O | 2 lanes | 2 lanes, after mode byte + dummy |
| `0xEB` | Fast read quad I/O | 4 lanes | 4 lanes, after mode byte + dummy |
| `0x8B` | Fast read octal I/O | 8 lanes | 8 lanes, after mode byte + dummy |
| `0x02` | Page program | 1 lane | 1 lane; needs WEL, sets WIP |
| `0x20` | Sector erase (4 KB) | 1 lane | — ; needs WEL, sets WIP |

Status register: bit 0 `WIP` (write in progress), bit 1 `WEL` (write enable
latch). `wait_ready()` polls it rather than assuming a fixed delay, which is
what a real controller must do.

`HOLD_N` is **active low**: high is normal operation, and pulling it low
freezes the interface mid-transaction without losing state.

## Real device models

Alongside the generic model there are models of specific parts, built from
their datasheets and cross-checked against Linux's `drivers/mtd/spi-nor`:

| Part | Protocols | Command extension | Octal entry |
|---|---|---|---|
| **Macronix MX25UM51345G** | 1S-1S-1S, 8S-8S-8S | **inverted** (`~opcode`) | CR2 `0x00000000` |
| **Micron MT35XU512ABA** | 1S-1S-1S, 8D-8D-8D | **repeated** (`opcode`) | CFR1V then CFR0V |

```python
from cocotbext.ospi.devices import MX25UM51345G
from cocotbext.ospi.xspi_flash import XspiFlash

flash = XspiFlash(dut, MX25UM51345G)
await flash.initialize()                       # the part boots single-lane
assert await flash.read_id() == [0xC2, 0x80, 0x3A]

await flash.enter_octal()                      # writes CR2, switches protocol
assert await flash.read_id() == [0xC2, 0x80, 0x3A]   # now over eight lanes
```

### Three things real parts do that a generic octal model does not

**The opcode is single-lane even in octal, and it comes in pairs.** Octal
commands are two bytes: the opcode and an extension. Macronix sends the
bitwise complement (`8READ` is `EC`/`13`), Micron repeats the opcode. Linux
calls these `SPI_NOR_EXT_INVERT` and `SPI_NOR_EXT_REPEAT`. Send the wrong
one and the part ignores the command — the two models disagree about this
deliberately, and each has a test proving it rejects the other's form.

**Commands change shape with the protocol.** `RDSR` takes no address and no
dummy cycles in SPI, but on the Macronix part in OPI it grows a 4-byte
address and four dummy cycles. `RDID` likewise. Addresses are 4 bytes, not
3.

**Dummy cycles are configurable and you must track them.** `DC[2:0]` in
Macronix CR2 `0x300` selects 20/18/16/14/12/10/8/6 cycles depending on clock
frequency; Micron's CFR1V holds the count directly. A controller that does
not follow the register reads garbage — there is a test that walks the whole
table.

### 8D-8D-8D

The Micron model runs at double transfer rate: a bit per lane on **both**
clock edges, so eight lanes move two bytes per clock. That is why an odd
number of bytes cannot be transferred in that mode, and why leaving it means
writing CFR0V and CFR1V together in one 2-byte write — which is exactly what
Linux does.

The DTR edge handling is validated against PicoSoC's `spiflash.v` quad-DTR
read (`0xED`), an independently written model, for the same reason the rest
of the interop suite exists.

### What is not modelled

DQS, SFDP, the flag status register, security and lock registers,
suspend/resume, and Macronix's DOPI (8D-8D-8D) mode. The arrays are a small
window rather than the full 64 MB so simulations stay fast; capacity is
reported honestly in the JEDEC ID.

```
make -C tests -f Makefile.mx25    # Macronix, 12 tests
make -C tests -f Makefile.mt35    # Micron, 11 tests
```

## Bus signals

`OspiBus.from_entity(dut)` picks up `clk`, `csb`, `io` and `HOLD_N`, plus
`io_out` and `io_oe`.

A simulator will not let a testbench drive an `inout` net, so the top level
splits the master's half into a value and a **per-lane** output enable:

```verilog
wire [7:0] io;
genvar g;
generate
    for (g = 0; g < 8; g = g + 1) begin : lane
        assign io[g] = io_oe[g] ? io_out[g] : 1'bz;
    end
endgenerate
```

Per-lane, not bus-wide: in single-lane mode the master drives `io0` while
the device answers on `io1`.

Note also that `csb` is left uninitialised in `ospi_flash_test.v`. The model
frames transactions on chip-select edges, and an initialiser there races
cocotb's first write at time 0 — the edge is lost and the device never
starts. `initialize()` drives the sequence explicitly.

## Testing

Two suites, and the split matters:

```
make -C tests                      # against our own JEDEC model: 12 tests
make -C tests -f Makefile.interop  # against PicoSoC's spiflash.v: 5 tests
```

The interop suite drives
[`spiflash.v`](https://github.com/YosysHQ/picorv32) — a model this project
did not write — and checks the bytes against known `$readmemh` content.

That distinction earned its keep. Testing only against our own model proves
the driver and the model agree; it does not prove either is right. Driving
somebody else's model immediately found that the master was dropping the
first bit of every byte — our model had the same off-by-one assumption, so
the closed loop had been happily agreeing with itself.

**Scope of that check:** `spiflash.v` is a four-lane part, so interop covers
the single, dual and quad paths. There is no comparable open-source octal
model, so the eight-lane path is exercised only against our own model. Treat
octal as less hardened than the rest.

## Layout

| Path | Contents |
|---|---|
| `cocotbext/ospi/ospi_flash.py` | `OspiFlash` — JEDEC command set, status polling, hold |
| `cocotbext/ospi/ospi_master.py` | `OspiMaster` — byte transfers at 1/2/4/8 lanes |
| `cocotbext/ospi/ospi_bus.py` | `OspiBus` — signal bundle |
| `cocotbext/ospi/ospi_config.py` | `OspiConfig`, `lanes_for_mode` |
| `verilog/ospi_flash.v` | NOR flash model: WEL, WIP, page program, sector erase, hold |
| `verilog/ospi_flash_test.v` | cocotb top level |
| `tests/reference/` | third-party model for interop (ISC, see its README) |

## Licence

MIT. `tests/reference/spiflash.v` is ISC, © Claire Xenia Wolf.
