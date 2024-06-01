# cocotbext-ospi

## Documentation
To properly handle OSPI (Octal SPI), which involves eight data lines (IO0-IO7), we need to update the module to include these lines and adjust the communication logic accordingly. Below is the revised Verilog module and testbench documentation to support OSPI with eight data lines.

### Creating a custom cocotbext.ospi
Directory Structure of OSPI module:

```markdown
cocotbext/
    __init__.py
    ospi/
        __init__.py
        ospi_bus.py
        ospi_master.py
        ospi_slave.py
        ospi_config.py
```

cocotbext/__init__.py
```
# This file is empty
```
cocotbext/ospi/__init__.py

```
from .ospi_bus import OspiBus
from .ospi_master import OspiMaster
from .ospi_slave import OspiSlave
from .ospi_config import OspiConfig

__all__ = ["OspiBus", "OspiMaster",  "OspiSlave" "OspiConfig"]
```
##### QspiBus 
This class will handle the initialization of the OSPI signals.

qspi_bus.py
```python
import cocotb
from cocotb.handle import SimHandle

class OspiBus:
    def __init__(self, sclk, cs, io0, io1, io2, io3, io4, io5, io6, io7):
        self.sclk = sclk    # Serial clock signal
        self.cs = cs        # Chip select signal
        self.io0 = io0      # Data line 0
        self.io1 = io1      # Data line 1
        self.io2 = io2      # Data line 2
        self.io3 = io3      # Data line 3
        self.io4 = io4      # Data line 4
        self.io5 = io5      # Data line 5
        self.io6 = io6      # Data line 6
        self.io7 = io7      # Data line 7

    @classmethod
    def from_prefix(cls, entity: SimHandle, prefix: str):
        # Retrieve signals based on prefix
        sclk = getattr(entity, f"{prefix}_sclk")
        cs = getattr(entity, f"{prefix}_cs")
        io0 = getattr(entity, f"{prefix}_io0")
        io1 = getattr(entity, f"{prefix}_io1")
        io2 = getattr(entity, f"{prefix}_io2")
        io3 = getattr(entity, f"{prefix}_io3")
        io4 = getattr(entity, f"{prefix}_io4")
        io5 = getattr(entity, f"{prefix}_io5")
        io6 = getattr(entity, f"{prefix}_io6")
        io7 = getattr(entity, f"{prefix}_io7")
        return cls(sclk, cs, io0, io1, io2, io3, io4, io5, io6, io7)

```
ospi_master.py
```python
import cocotb
from cocotb.triggers import Timer, RisingEdge

class OspiMaster:
    def __init__(self, bus: QspiBus, config: QspiConfig):
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
                # Additional lines for quad mode
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
            if self.config.quad_mode:
                # Additional lines for quad mode
                nibble |= (
                    (int(self.bus.io4.value) << 4) |
                    (int(self.bus.io5.value) << 5) |
                    (int(self.bus.io6.value) << 6) |
                    (int(self.bus.io7.value) << 7)
                )
            byte = (byte << 4) | nibble  # Combine the nibble into the byte
        return byte
```
ospi_slave.py
```python
class OspiSlave:
    def __init__(self, dut, config):
        self.dut = dut
        self.config = config

    async def read(self):
        byte = 0
        for i in range(8):
            await RisingEdge(self.dut.OSPI_CLK)
            byte = (byte << 1) | int(self.dut.OSPI_IO[0].value)
        return byte

    async def write(self, data):
        for i in range(8):
            self.dut.OSPI_IO[0].value = (data >> (7 - i)) & 1
            await RisingEdge(self.dut.OSPI_CLK)
        await Timer(1, units='ns')
```
ospi_config.py
```python
class OspiConfig:
    def __init__(self, word_width, sclk_freq, cpol, cpha, cs_active_low, io_mode='octal'):
        self.word_width = word_width  # Data width in bits
        self.sclk_freq = sclk_freq    # Serial clock frequency
        self.cpol = cpol              # Clock polarity
        self.cpha = cpha              # Clock phase
        self.cs_active_low = cs_active_low  # Chip select active low flag
        self.io_mode = io_mode        # I/O mode: 'single', 'dual', 'quad', 'octal'

    def __str__(self):
        return (f'OspiConfig(word_width={self.word_width}, sclk_freq={self.sclk_freq}, '
                f'cpol={self.cpol}, cpha={self.cpha}, cs_active_low={self.cs_active_low}, '
                f'io_mode={self.io_mode})')
```
### OSPI Flash Memory Interface Documentation

#### Overview
This document provides a detailed explanation of the OSPI Flash Memory Interface, implemented in Verilog, and its verification using Cocotb. The interface allows for read, write, and erase operations on the OSPI flash memory using four data lines (IO0, IO1, IO2, IO3, IO4, IO5, IO6, IO7).

### Interface Description
The OSPI (Octal Serial Peripheral Interface) is designed for communication between a master (e.g., a microcontroller) and a slave (e.g., flash memory). The interface includes the following signals:

| Signal Name   | Direction | Description                                      |
|---------------|-----------|--------------------------------------------------|
| OSPI_CLK   | Input     | OSPI serial clock input                          |
| OSPI_IO[0]    | Inout     | OSPI data line 0 (MOSI in single SPI mode)       |
| OSPI_IO[1]    | Inout     | OSPI data line 1 (MISO in single SPI mode)       |
| OSPI_IO[2]    | Inout     | OSPI data line 2                                 |
| OSPI_IO[3]    | Inout     | OSPI data line 3                                 |
| OSPI_IO[4]    | Inout     | OSPI data line 4                                 |
| OSPI_IO[5]    | Inout     | OSPI data line 5                                 |
| OSPI_IO[6]    | Inout     | OSPI data line 6                                 |
| OSPI_IO[7]    | Inout     | OSPI data line 7                                 |                                
| OSPI_DS     | Input     |Read data strobe input. Supports DDR option in OSPI boot mode.                 |
| OSPI_CS0_b        | Output     | Single device and stacked lower device chip select. Active-Low.               |
| OSPI_CS1_b| Output     | Stacked upper device chip select. Active-Low.                              |
| OSPI_RST_b | Output     | Reset output to the OSPI flash device. Active-Low.                               |

### Verilog Module
Here is the Verilog module `ospi_flash` which supports the OSPI interface:

```verilog
module ospi_flash (
    input wire OSPI_CLK,        // OSPI serial clock input
    inout wire [7:0] OSPI_IO,   // OSPI data lines (0 to 7)
    input wire OSPI_DS,         // Read data strobe input
    input wire OSPI_CS0_b,      // Chip select 0 (active low)
    input wire OSPI_CS1_b,      // Chip select 1 (active low)
    input wire OSPI_RST_b,      // Reset signal (active low)
    input wire clk,             // Clock input for internal logic
    input wire reset_n,         // Active-low reset input
    input wire write_enable,    // Write enable signal
    input wire read_enable,     // Read enable signal
    input wire erase_enable,    // Erase enable signal
    input wire [7:0] data_in,   // Data input for write operation
    input wire [7:0] address,   // Address input for memory access
    output reg [7:0] data_out   // Data output for read operation
);

    // Memory array to store data, 256 bytes in size
    reg [7:0] memory [0:255];
    reg [7:0] data_buffer;      // Buffer to handle bidirectional data lines

    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            data_out <= 8'hFF;  // Initialize data_out to 0xFF on reset
        end else begin
            if (write_enable) begin
                memory[address] <= data_in;    // Write data_in to memory at specified address
            end
            if (read_enable) begin
                data_out <= memory[address];   // Read data from memory at specified address
            end
            if (erase_enable) begin
                memory[address] <= 8'hFF;      // Erase data by writing 0xFF to memory at specified address
            end
        end
    end

    // Assign OSPI data lines based on operation mode
    assign OSPI_IO[0] = (write_enable || erase_enable) ? data_in[0] : 1'bz;
    assign OSPI_IO[1] = (write_enable || erase_enable) ? data_in[1] : 1'bz;
    assign OSPI_IO[2] = (write_enable || erase_enable) ? data_in[2] : 1'bz;
    assign OSPI_IO[3] = (write_enable || erase_enable) ? data_in[3] : 1'bz;
    assign OSPI_IO[4] = (write_enable || erase_enable) ? data_in[4] : 1'bz;
    assign OSPI_IO[5] = (write_enable || erase_enable) ? data_in[5] : 1'bz;
    assign OSPI_IO[6] = (write_enable || erase_enable) ? data_in[6] : 1'bz;
    assign OSPI_IO[7] = (write_enable || erase_enable) ? data_in[7] : 1'bz;

endmodule

```
