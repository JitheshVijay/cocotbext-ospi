// Top level for the cocotb testbench.
//
// cocotb acts as the OSPI master. It cannot drive an inout net directly, so
// the master's side of OSPI_IO is split into a value (io_out) and an output
// enable (io_oe); releasing io_oe hands the bus to the flash for read data.

`timescale 1ns/1ps

module ospi_flash_test;

    reg        OSPI_CLK = 1'b0;
    reg        OSPI_CS  = 1'b1;   // active low, starts deasserted
    reg        reset_n  = 1'b0;
    reg        HOLD_N   = 1'b1;   // active low, starts released
    reg [1:0]  mode     = 2'd0;
    reg [7:0]  io_out   = 8'h00;
    reg        io_oe    = 1'b0;

    wire [7:0] OSPI_IO;

    assign OSPI_IO = io_oe ? io_out : 8'bzzzzzzzz;

    ospi_flash dut (
        .OSPI_CLK (OSPI_CLK),
        .OSPI_CS  (OSPI_CS),
        .OSPI_IO  (OSPI_IO),
        .reset_n  (reset_n),
        .HOLD_N   (HOLD_N),
        .mode     (mode)
    );

endmodule
