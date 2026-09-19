# cocotbext-ospi

A [cocotb](https://www.cocotb.org/) extension for driving octal-SPI flash
devices, plus a synthesisable OSPI flash slave model to test against.

Requires **cocotb 2.0+** and a simulator; the tests run on Icarus Verilog.

## Protocol

A transaction is framed by `OSPI_CS` (active low). `mode` selects how many of
the eight `OSPI_IO` lines carry data at once, which sets what a byte costs:

| `mode` | Name | Lanes | Clocks per byte |
|---|---|---|---|
| 0 | single | 1 | 8 |
| 1 | dual | 2 | 4 |
| 2 | quad | 4 | 2 |
| 3 | octal | 8 | 1 |

Bits travel most-significant first on the low `lanes` lines. Every command
carries a 24-bit address; memory is 256 bytes, so its low byte selects the
cell.

| Operation | Sequence |
|---|---|
| Page program | `0x02` \| addr[23:0] \| data |
| Read | `0x03` \| addr[23:0] \| dummy \| *data* |
| Sector erase | `0x20` \| addr[23:0] |

The slave drives `OSPI_IO` only during a read's data phase. The dummy clock
after the address gives the master a full cycle to release the bus before the
slave starts driving, so the two never contend.

`HOLD_N` is **active low**: high is normal operation, and pulling it low
freezes the interface mid-transaction without losing state. Memory powers up
erased (`0xFF`).

## Usage

```python
import cocotb
from cocotb.clock import Clock
from cocotbext.ospi import OspiFlash

@cocotb.test()
async def test_round_trip(dut):
    cocotb.start_soon(Clock(dut.OSPI_CLK, 20, units="ns").start())

    flash = OspiFlash(dut)
    await flash.initialize()

    # The same byte round-trips through any lane width.
    for mode in (0, 1, 2, 3):
        await flash.write(0x10, 0xA5, mode=mode)
        assert await flash.read(0x10, mode=mode) == 0xA5

    await flash.erase(0x10, mode=2)
    assert await flash.read(0x10, mode=2) == 0xFF
```

## Bus signals

`OspiBus.from_entity(dut)` picks up `OSPI_CLK`, `OSPI_CS`, `OSPI_IO` and
`mode`, plus `io_out` and `io_oe`.

A simulator will not let the testbench drive an `inout` net directly, so the
top level splits the master's half of `OSPI_IO` into a driven value
(`io_out`) and an output enable (`io_oe`); dropping `io_oe` hands the bus to
the flash:

```verilog
wire [7:0] OSPI_IO;
assign OSPI_IO = io_oe ? io_out : 8'bzzzzzzzz;
```

See `verilog/ospi_flash_test.v`.

## Layout

| Path | Contents |
|---|---|
| `cocotbext/ospi/ospi_flash.py` | `OspiFlash` — write / read / erase / hold |
| `cocotbext/ospi/ospi_bus.py` | `OspiBus` — lane-width aware byte transfers |
| `cocotbext/ospi/ospi_config.py` | `OspiConfig`, `lanes_for_mode` |
| `verilog/ospi_flash.v` | OSPI flash slave model |
| `verilog/ospi_flash_test.v` | cocotb top level with the tri-state split |

## Running the tests

```
pip install cocotb pytest
make -C tests
```

```
** TESTS=8 PASS=8 FAIL=0 SKIP=0 **
```
