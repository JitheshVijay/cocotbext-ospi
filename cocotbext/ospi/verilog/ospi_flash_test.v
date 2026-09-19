// Top level for the cocotb testbench.
//
// cocotb cannot drive an inout net directly, so the master's half of the bus
// is split into a value (io_out) and a per-lane output enable (io_oe).
// Per-lane matters: in single-lane mode the master drives io0 while the
// device answers on io1, so one bus-wide enable would collide.
//
// csb is deliberately uninitialised -- the model frames on chip-select
// edges, and an initialiser here would race cocotb's first write at time 0.

`timescale 1ns/1ps

module ospi_flash_test;

    reg       csb;
    reg       clk    = 1'b0;
    reg       HOLD_N = 1'b1;   // active low, starts released
    reg [7:0] io_out;
    reg [7:0] io_oe;

    wire [7:0] io;

    genvar g;
    generate
        for (g = 0; g < 8; g = g + 1) begin : lane
            assign io[g] = io_oe[g] ? io_out[g] : 1'bz;
        end
    endgenerate

    ospi_flash dut (
        .clk    (clk),
        .csb    (csb),
        .io     (io),
        .HOLD_N (HOLD_N)
    );

endmodule
