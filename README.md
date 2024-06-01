# OSPI Interface for Cocotb
##### The Octal Serial Peripheral Interface (OSPI) extends QSPI by using eight data lines, doubling the data transfer rate and catering to applications demanding high-speed data processing. Cocotb, a flexible Python-based hardware verification framework, enables the simulation and testing of OSPI interfaces. By incorporating OSPI into Cocotb testbenches, developers can thoroughly validate the performance and correctness of high-speed hardware designs.
##### This documentation delves into the implementation and verification of OSPI interfaces using Cocotb, detailing the key components such as OSPI configuration, master and slave modules, and providing comprehensive testbench examples. These resources will assist developers in accurately simulating and validating the performance of OSPI-enabled hardware designs, ensuring they meet the stringent requirements of high-speed applications.

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
This class will handle the initialization of the OSPI signals. The OspiBus class models the signals of an OSPI bus. This includes the chip select, serial clock, and data lines. In an OSPI interface, the data lines are typically io0 to io7 for octal communication.

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
#### OspiMaster
The OspiMaster class models the behavior of an Octal SPI (OSPI) master device. This class typically handles the initiation and control of OSPI transactions, including sending commands, writing data, and reading data from a connected OSPI slave device. 
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
#### OspiSlave
The OspiSlave class models the behavior of an OSPI slave device. This class can include methods for responding to OSPI commands, such as reading and writing data. The exact implementation will depend on the specific behavior and protocols supported by the OSPI slave device.
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
##### OspiConfig
The OspiConfig class encapsulates the configuration parameters for the OSPI interface. This typically includes the word width, serial clock frequency, clock polarity, clock phase, and chip select polarity. Additionally, it can include flags for enabling special modes like quad mode or octal mode.
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
### OspiFlash
The OspiFlash class models the behavior of an Octal SPI (OSPI) flash memory device. This class typically includes methods for initializing the flash memory, reading data from it, writing data to it, and performing other operations like erasing memory blocks. The class interacts with an OSPI master to send and receive data and commands according to the OSPI protocol.
```python
import cocotb
from cocotb.triggers import Timer, RisingEdge
from cocotb.clock import Clock
from cocotbext.ospi import OspiBus, OspiConfig, OspiMaster

class OspiFlash:
    def __init__(self, dut):
        self.dut = dut
        self.ospi_bus = OspiBus.from_prefix(dut, "OSPI")
        self.ospi_config = OspiConfig(
            word_width=8,
            sclk_freq=50e6,
            cpol=False,
            cpha=False,
            cs_active_low=True,
            quad_mode=True  # Assuming quad_mode is a valid config for OSPI
        )
        self.ospi_master = OspiMaster(self.ospi_bus, self.ospi_config)

    async def reset(self):
        self.dut.OSPI_RST_b.value = 0
        await Timer(100, units='ns')
        self.dut.OSPI_RST_b.value = 1
        await Timer(100, units='ns')

    async def initialize(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, units='ns').start())
        await self.reset()

    async def write(self, address, data):
        command = [0x02]  # Page Program command for OSPI
        address_bytes = [(address >> i) & 0xFF for i in (16, 8, 0)]
        data_bytes = [data]
        await self.ospi_master.write(command + address_bytes + data_bytes)
        await Timer(1, units='ns')

    async def read(self, address):
        command = [0x03]  # Read Data command for OSPI
        address_bytes = [(address >> i) & 0xFF for i in (16, 8, 0)]
        await self.ospi_master.write(command + address_bytes)
        await Timer(1, units='ns')
        read_data = await self.ospi_master.read(1)
        return read_data[0]

    async def erase(self, address):
        command = [0x20]  # Sector Erase command for OSPI
        address_bytes = [(address >> i) & 0xFF for i in (16, 8, 0)]
        await self.ospi_master.write(command + address_bytes)
        await Timer(1, units='ns')
```
#### Explanation
#### Initialization:

The OspiFlash class initializes with the DUT (device under test) and sets up the OSPI bus and configuration using cocotbext.ospi.
#### Reset:

The reset method toggles the reset signal to reset the OSPI flash memory.
#### Initialize:

The initialize method starts a clock and calls the reset method to prepare the OSPI flash memory for operations.
#### Write Operation:

The write method sends a Page Program command (0x02), followed by the address and data bytes, to the OSPI flash memory.
#### Read Operation:

The read method sends a Read Data command (0x03), followed by the address bytes, and then reads the data from the OSPI flash memory.
#### Erase Operation:

The erase method sends a Sector Erase command (0x20), followed by the address bytes, to erase a sector of the OSPI flash memory.

### Test Case: Write and Read
```python
@cocotb.test()
async def test_ospi_flash_write_read(dut):
    flash = OSPIFlash(dut)
    await flash.initialize()
    
    address = 0x00
    data_to_write = 0xA5
    await flash.write(address, data_to_write)
    await Timer(10, units='ns')
    
    read_data = await flash.read(address)
    assert read_data == data_to_write, f"Data mismatch: {read_data} != {data_to_write}"
```
### Test Case: Erase
```python
@cocotb.test()
async def test_ospi_flash_erase(dut):
    flash = OSPIFlash(dut)
    await flash.initialize()
    
    address = 0x00
    data_to_write = 0x5A
    await flash.write(address, data_to_write)
    await Timer(10, units='ns')
    
    await flash.erase(address)
    await Timer(10, units='ns')
    
    read_data = await flash.read(address)
    assert read_data == 0xFF, f"Data after erase mismatch: {read_data} != 0xFF"
```

### OSPI Flash Test Module
This test module sets up the testbench environment to simulate the OSPI flash memory interface. 
```verilog
module ospi_flash_test;
    reg ospi_sclk;             // OSPI serial clock
    reg [7:0] ospi_io;         // OSPI data lines
    reg ospi_cs;               // OSPI chip select
    reg reset_n;               // Active-low reset signal
    reg clk;                   // Clock signal
    reg write_enable;          // Write enable signal
    reg read_enable;           // Read enable signal
    reg erase_enable;          // Erase enable signal
    reg [7:0] data_in;         // Data input for memory operations
    reg [7:0] address;         // Address input for memory operations
    wire [7:0] data_out;       // Data output from memory operations

    ospi_flash dut (
        .ospi_sclk(ospi_sclk),
        .ospi_cs(ospi_cs),
        .ospi_io(ospi_io),
        .reset_n(reset_n),
        .clk(clk),
        .write_enable(write_enable),
        .read_enable(read_enable),
        .erase_enable(erase_enable),
        .data_in(data_in),
        .address(address),
        .data_out(data_out)
    );

    initial begin
        $dumpfile("waves.vcd");
        $dumpvars(0, ospi_flash_test);
        
        ospi_sclk = 0;
        ospi_io = 8'b00000000;
        ospi_cs = 1;
        reset_n = 0;
        clk = 0;
        write_enable = 0;
        read_enable = 0;
        erase_enable = 0;
        data_in = 0;
        address = 0;
        
        #10 reset_n = 1;
    end
    always #5 clk = ~clk;

    // Generate OSPI clock
    always #10 ospi_sclk = ~ospi_sclk;
endmodule
```
#### Explanation
#### Module Definition:

The module is named ospi_flash_test.
It includes all necessary signals for the OSPI interface: ospi_sclk, ospi_io (8-bit bus for the data lines), ospi_cs, reset_n, clk, write_enable, read_enable, erase_enable, data_in, address, and data_out.
#### Instantiating the DUT:

The ospi_flash module (device under test) is instantiated with the relevant ports connected to the testbench signals.
#### Initial Block:

Initializes the signals and sets up the dump file for waveform viewing.
The reset_n signal is deasserted after 10 time units to simulate a reset release.
#### Clock Generation:

A clock signal clk is generated with a period of 10 time units.
The ospi_sclk signal (OSPI serial clock) is generated with a period of 20 time units.

### Conclusion
This documentation provides a comprehensive guide to implementing and simulating a OSPI flash memory interface using Verilog and Cocotb. The OSPI interface supports essential memory operations such as read, write, and erase, and the provided testbench ensures these functionalities are correctly verified. Adjust and expand the simulation code as necessary to meet your specific requirements.
