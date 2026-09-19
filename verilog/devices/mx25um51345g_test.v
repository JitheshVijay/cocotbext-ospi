// cocotb top level for the MX25UM51345G model.
//
// csb is deliberately uninitialised: the model frames on chip-select edges
// and an initialiser here would race cocotb's first write at time 0.

`timescale 1ns/1ps

module mx25um51345g_test;

    reg       csb;
    reg       clk = 1'b0;
    reg       HOLD_N = 1'b1;   // unused by this part; kept for OspiBus
    reg [7:0] io_out;
    reg [7:0] io_oe;

    wire [7:0] io;

    genvar g;
    generate
        for (g = 0; g < 8; g = g + 1) begin : lane
            assign io[g] = io_oe[g] ? io_out[g] : 1'bz;
        end
    endgenerate

    mx25um51345g dut (
        .clk (clk),
        .csb (csb),
        .io  (io)
    );

endmodule
