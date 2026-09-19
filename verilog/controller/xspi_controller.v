// A minimal but real xSPI flash controller.
//
// Everything else in this project points a driver at a flash model. This
// inverts that: it is RTL under test, driving a flash model, with cocotb
// poking its command interface. That is what the extension ultimately
// exists to support -- verifying somebody's controller, not our own driver.
//
// One command per handshake. The caller presents an opcode, an address, how
// many address bytes and dummy cycles it takes, the lane width, and whether
// it reads or writes; the controller runs the phases and raises done.
// Nothing here is specific to any one flash, so the same controller drives a
// single-lane SPI part and an octal one.
//
// How wide the command phase is depends on the protocol, and this is where
// controllers go wrong. In a 1-4-4 style read -- a quad read issued to a
// part still in ordinary SPI -- the leading 1 means the opcode goes out on
// one lane and only the address and data widen. In 8-8-8, the part has been
// switched into octal wholesale and the opcode is eight lanes too. So the
// command phase gets its own lane count rather than being assumed either
// way.
//
// Timing is SPI mode 0: sclk idles low, data changes while it is low, and
// the device samples on the rising edge. Read data is sampled on the rising
// edge too, where the device has held it stable since the previous falling
// edge.
//
// Single transfer rate only. DTR needs data presented on both edges and two
// sample points per period; the counters below step once per sclk period, so
// that is a real change rather than a parameter.

`timescale 1ns/1ps

module xspi_controller #(
    parameter CLK_DIV = 2          // clk cycles per sclk half period
)(
    input  wire        clk,
    input  wire        rst_n,

    // ── command interface ────────────────────────────────────────────
    input  wire        cmd_valid,
    output wire        cmd_ready,
    input  wire [7:0]  cmd_opcode,
    input  wire [7:0]  cmd_ext,       // second command byte, octal parts
    input  wire        cmd_has_ext,
    input  wire [31:0] cmd_addr,
    input  wire [3:0]  cmd_addr_bytes,
    input  wire [7:0]  cmd_dummy,     // dummy cycles between address and data
    input  wire [4:0]  cmd_lanes,     // address and data lanes
    input  wire [4:0]  cmd_cmd_lanes, // opcode and extension lanes
    input  wire        cmd_is_read,
    input  wire [15:0] cmd_len,       // data bytes

    // ── data ─────────────────────────────────────────────────────────
    input  wire [7:0]  wdata,
    output reg         wdata_next,    // pulses when the next byte is consumed
    output reg  [7:0]  rdata,
    output reg         rdata_valid,

    output wire        busy,
    output reg         done,

    // ── flash pins ───────────────────────────────────────────────────
    output reg         sclk,
    output reg         csb,
    output wire [7:0]  io_out,
    output wire [7:0]  io_oe,
    input  wire [7:0]  io_in
);

    localparam [3:0] S_IDLE  = 4'd0,
                     S_CMD   = 4'd1,
                     S_EXT   = 4'd2,
                     S_ADDR  = 4'd3,
                     S_DUMMY = 4'd4,
                     S_WRITE = 4'd5,
                     S_READ  = 4'd6,
                     S_END   = 4'd7;

    reg [3:0]  state;
    reg [7:0]  ext_r;
    reg [31:0] addr_r;
    reg [3:0]  addr_left;
    reg [7:0]  dummy_left;
    reg [4:0]  lanes_r, cmd_lanes_r;
    reg        is_read_r, has_ext_r;
    reg [15:0] bytes_left;

    reg [7:0]  shift_out;
    reg [7:0]  shift_in;
    reg [3:0]  bits_left;

    reg [15:0] div_cnt;
    reg        tick;

    assign busy      = (state != S_IDLE);
    assign cmd_ready = (state == S_IDLE);

    wire [4:0] lanes_now = (state == S_CMD || state == S_EXT)
                           ? cmd_lanes_r : lanes_r;

    wire driving = (state == S_CMD) || (state == S_EXT) ||
                   (state == S_ADDR) || (state == S_WRITE);

    // The bus always shows the top `lanes_now` bits of the shift register,
    // so there is one place data is presented rather than an assignment in
    // every branch.
    reg [7:0] slice;
    always @(*) begin
        case (lanes_now)
            5'd1: slice = {7'b0, shift_out[7]};
            5'd2: slice = {6'b0, shift_out[7:6]};
            5'd4: slice = {4'b0, shift_out[7:4]};
            5'd8: slice = shift_out;
            default: slice = {7'b0, shift_out[7]};
        endcase
    end

    reg [7:0] oe_mask;
    always @(*) begin
        case (lanes_now)
            5'd1: oe_mask = 8'h01;
            5'd2: oe_mask = 8'h03;
            5'd4: oe_mask = 8'h0F;
            5'd8: oe_mask = 8'hFF;
            default: oe_mask = 8'h01;
        endcase
    end

    assign io_out = slice;
    assign io_oe  = driving ? oe_mask : 8'h00;

    // ── sclk generation ──────────────────────────────────────────────
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            div_cnt <= 0;
            tick    <= 1'b0;
        end else if (state == S_IDLE) begin
            div_cnt <= 0;
            tick    <= 1'b0;
        end else if (div_cnt == CLK_DIV - 1) begin
            div_cnt <= 0;
            tick    <= 1'b1;
        end else begin
            div_cnt <= div_cnt + 1;
            tick    <= 1'b0;
        end
    end

    wire going_high = tick && !sclk;
    wire going_low  = tick && sclk;

    // ── main sequencer ───────────────────────────────────────────────
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            sclk        <= 1'b0;
            csb         <= 1'b1;
            rdata       <= 8'h00;
            rdata_valid <= 1'b0;
            wdata_next  <= 1'b0;
            done        <= 1'b0;
            shift_out   <= 8'h00;
            bits_left   <= 0;
        end else begin
            rdata_valid <= 1'b0;
            wdata_next  <= 1'b0;
            done        <= 1'b0;

            if (state == S_IDLE) begin
                sclk <= 1'b0;
                csb  <= 1'b1;
                if (cmd_valid) begin
                    ext_r      <= cmd_ext;
                    has_ext_r  <= cmd_has_ext;
                    addr_r     <= cmd_addr;
                    addr_left  <= cmd_addr_bytes;
                    dummy_left <= cmd_dummy;
                    lanes_r     <= cmd_lanes;
                    cmd_lanes_r <= cmd_cmd_lanes;
                    is_read_r  <= cmd_is_read;
                    bytes_left <= cmd_len;
                    shift_out  <= cmd_opcode;
                    bits_left  <= 8;
                    csb        <= 1'b0;
                    state      <= S_CMD;
                end
            end else if (state == S_END) begin
                csb   <= 1'b1;
                sclk  <= 1'b0;
                done  <= 1'b1;
                state <= S_IDLE;
            end else if (going_high) begin
                sclk <= 1'b1;
                if (state == S_READ) begin
                    // Sample where the device has held data stable.
                    case (lanes_r)
                        5'd1: shift_in <= {shift_in[6:0], io_in[1]};
                        5'd2: shift_in <= {shift_in[5:0], io_in[1:0]};
                        5'd4: shift_in <= {shift_in[3:0], io_in[3:0]};
                        5'd8: shift_in <= io_in;
                        default: shift_in <= {shift_in[6:0], io_in[1]};
                    endcase
                    bits_left <= bits_left - lanes_r;
                end
            end else if (going_low) begin
                sclk <= 1'b0;
                case (state)
                    S_CMD, S_EXT, S_ADDR, S_WRITE: begin
                        if (bits_left > lanes_now) begin
                            shift_out <= shift_out << lanes_now;
                            bits_left <= bits_left - lanes_now;
                        end else begin
                            next_output_phase;
                        end
                    end

                    S_DUMMY: begin
                        dummy_left <= dummy_left - 1;
                        if (dummy_left == 1) begin
                            bits_left <= 8;
                            state     <= S_READ;
                        end
                    end

                    S_READ: begin
                        if (bits_left == 0) begin
                            rdata       <= shift_in;
                            rdata_valid <= 1'b1;
                            if (bytes_left == 1) begin
                                state <= S_END;
                            end else begin
                                bytes_left <= bytes_left - 1;
                                bits_left  <= 8;
                            end
                        end
                    end

                    default: state <= S_END;
                endcase
            end
        end
    end

    // What follows the byte that just finished going out.
    task next_output_phase;
        begin
            case (state)
                S_CMD: begin
                    if (has_ext_r) begin
                        shift_out <= ext_r;
                        bits_left <= 8;
                        state     <= S_EXT;
                    end else after_command;
                end
                S_EXT: after_command;
                S_ADDR: begin
                    if (addr_left == 1) after_address;
                    else begin
                        addr_left <= addr_left - 1;
                        shift_out <= addr_r[23:16];
                        addr_r    <= {addr_r[23:0], 8'h00};
                        bits_left <= 8;
                    end
                end
                S_WRITE: begin
                    if (bytes_left == 1) state <= S_END;
                    else begin
                        bytes_left <= bytes_left - 1;
                        shift_out  <= wdata;
                        wdata_next <= 1'b1;
                        bits_left  <= 8;
                    end
                end
                default: state <= S_END;
            endcase
        end
    endtask

    task after_command;
        begin
            if (addr_left != 0) begin
                shift_out <= addr_r[31:24];
                addr_r    <= {addr_r[23:0], 8'h00};
                bits_left <= 8;
                state     <= S_ADDR;
            end else after_address;
        end
    endtask

    task after_address;
        begin
            if (is_read_r) begin
                if (dummy_left != 0) state <= S_DUMMY;
                else begin
                    bits_left <= 8;
                    state     <= S_READ;
                end
            end else if (bytes_left != 0) begin
                shift_out  <= wdata;
                wdata_next <= 1'b1;
                bits_left  <= 8;
                state      <= S_WRITE;
            end else state <= S_END;
        end
    endtask

endmodule
