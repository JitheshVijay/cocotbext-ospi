// Controller-under-test: real RTL driving a real flash model.
//
// cocotb pokes only the controller's command interface here -- it never
// touches the flash pins. Whether the bytes come back right depends on the
// controller getting the protocol right, which is the point.

`timescale 1ns/1ps

module xspi_controller_test;

    reg         clk = 1'b0;
    reg         rst_n;

    reg         cmd_valid;
    wire        cmd_ready;
    reg  [7:0]  cmd_opcode;
    reg  [7:0]  cmd_ext;
    reg         cmd_has_ext;
    reg  [31:0] cmd_addr;
    reg  [3:0]  cmd_addr_bytes;
    reg  [7:0]  cmd_dummy;
    reg  [4:0]  cmd_lanes;
    reg  [4:0]  cmd_cmd_lanes;
    reg         cmd_is_read;
    reg  [15:0] cmd_len;

    reg  [7:0]  wdata;
    wire        wdata_next;
    wire [7:0]  rdata;
    wire        rdata_valid;
    wire        busy;
    wire        done;

    wire        sclk;
    wire        csb;
    wire [7:0]  ctrl_io_out;
    wire [7:0]  ctrl_io_oe;
    wire [7:0]  io;
    wire        dqs;

    // The controller's half of the bidirectional bus.
    genvar g;
    generate
        for (g = 0; g < 8; g = g + 1) begin : lane
            assign io[g] = ctrl_io_oe[g] ? ctrl_io_out[g] : 1'bz;
        end
    endgenerate

    xspi_controller #(.CLK_DIV(2)) ctrl (
        .clk            (clk),
        .rst_n          (rst_n),
        .cmd_valid      (cmd_valid),
        .cmd_ready      (cmd_ready),
        .cmd_opcode     (cmd_opcode),
        .cmd_ext        (cmd_ext),
        .cmd_has_ext    (cmd_has_ext),
        .cmd_addr       (cmd_addr),
        .cmd_addr_bytes (cmd_addr_bytes),
        .cmd_dummy      (cmd_dummy),
        .cmd_lanes      (cmd_lanes),
        .cmd_cmd_lanes  (cmd_cmd_lanes),
        .cmd_is_read    (cmd_is_read),
        .cmd_len        (cmd_len),
        .wdata          (wdata),
        .wdata_next     (wdata_next),
        .rdata          (rdata),
        .rdata_valid    (rdata_valid),
        .busy           (busy),
        .done           (done),
        .sclk           (sclk),
        .csb            (csb),
        .io_out         (ctrl_io_out),
        .io_oe          (ctrl_io_oe),
        .io_in          (io)
    );

    mx25um51345g flash (
        .clk (sclk),
        .csb (csb),
        .io  (io),
        .dqs (dqs)
    );

endmodule
