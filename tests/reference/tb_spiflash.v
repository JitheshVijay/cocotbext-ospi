// Interop top level: cocotbext-ospi driving an independent flash model.
//
// The DUT is spiflash.v from PicoSoC (Claire Xenia Wolf, ISC licence) -- a
// model this project did not write. It is a four-lane part, so it exercises
// the single, dual and quad paths of the driver. There is no comparable
// open-source octal model, so the eight-lane path is covered only by our own
// model; the README says so rather than implying otherwise.
//
// The bus is declared eight bits wide to match OspiBus, with the upper four
// lanes left unconnected.

`timescale 1ns/1ps

module tb_spiflash;

    reg       csb;
    reg       clk    = 1'b0;
    reg       HOLD_N = 1'b1;
    reg [7:0] io_out;
    reg [7:0] io_oe;

    wire [7:0] io;

    genvar g;
    generate
        for (g = 0; g < 8; g = g + 1) begin : lane
            assign io[g] = io_oe[g] ? io_out[g] : 1'bz;
        end
    endgenerate

    spiflash flash (
        .csb (csb),
        .clk (clk),
        .io0 (io[0]),
        .io1 (io[1]),
        .io2 (io[2]),
        .io3 (io[3])
    );

endmodule
