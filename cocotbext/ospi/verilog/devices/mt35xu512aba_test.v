// cocotb top level for the MT35XU512ABA model.
//
// csb is deliberately uninitialised: the model frames on chip-select edges
// and an initialiser here would race cocotb's first write at time 0.

`timescale 1ns/1ps

module mt35xu512aba_test;

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

    // A single-lane transaction is ~1.1 us, so the default 1 us program
    // window closes before a second command can collide with it. Widen it
    // so "issue a command while busy" is actually testable; it only affects
    // how long simulated time runs, not behaviour.
    mt35xu512aba #(
        .PROGRAM_NS (20000),
        .ERASE_NS   (40000)
    ) dut (
        .clk (clk),
        .csb (csb),
        .io  (io)
    );

endmodule
