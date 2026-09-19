// Octal-SPI (OSPI) flash slave model.
//
// A transaction is framed by OSPI_CS (active low) and clocked on the rising
// edge of OSPI_CLK. `mode` selects how many of the eight OSPI_IO lines carry
// data at once, so it sets how many clocks a byte costs:
//
//   mode 0  single  1 lane   8 clocks/byte
//   mode 1  dual    2 lanes  4 clocks/byte
//   mode 2  quad    4 lanes  2 clocks/byte
//   mode 3  octal   8 lanes  1 clock/byte
//
// Bits travel most-significant first on the low `lanes` lines. Every command
// carries a 24-bit address; memory is 256 bytes, so the low byte indexes it.
//
//   write   0x02 | addr[23:0] | data
//   read    0x03 | addr[23:0] | dummy | <data>
//   erase   0x20 | addr[23:0]
//
// The slave drives OSPI_IO only during a read's data phase; the dummy clock
// after the address lets the master release the bus first, so the two never
// contend. Holding HOLD_N low freezes the interface mid-transaction without
// losing state. Memory powers up erased (0xFF).

`timescale 1ns/1ps

module ospi_flash #(
    parameter MEM_DEPTH = 256
)(
    input  wire       OSPI_CLK,
    input  wire       OSPI_CS,    // active low chip select
    inout  wire [7:0] OSPI_IO,
    input  wire       reset_n,
    input  wire       HOLD_N,     // active low; freezes the interface
    input  wire [1:0] mode        // 0 single, 1 dual, 2 quad, 3 octal
);

    localparam [7:0] CMD_WRITE = 8'h02;
    localparam [7:0] CMD_READ  = 8'h03;
    localparam [7:0] CMD_ERASE = 8'h20;

    localparam [2:0] S_CMD   = 3'd0,
                     S_ADDR  = 3'd1,
                     S_WDATA = 3'd2,
                     S_DUMMY = 3'd3,
                     S_RDATA = 3'd4,
                     S_DONE  = 3'd5;

    reg [7:0]  memory [0:MEM_DEPTH-1];
    reg [2:0]  state;
    reg [3:0]  bits;        // bits accumulated into the current byte
    reg [1:0]  addr_byte;   // which of the three address bytes is in flight
    reg [7:0]  cmd, shreg, rdata_sh;
    reg [23:0] addr;

    // Lane count and the mask of active lines for the selected mode.
    wire [3:0] lanes = (mode == 2'd0) ? 4'd1 :
                       (mode == 2'd1) ? 4'd2 :
                       (mode == 2'd2) ? 4'd4 : 4'd8;
    wire [8:0] mask9 = (9'd1 << lanes) - 9'd1;
    wire [7:0] mask  = mask9[7:0];

    // The byte as it stands once this clock's lanes are shifted in.
    wire [7:0] shifted   = (shreg << lanes) | (OSPI_IO & mask);
    wire       byte_done = (bits + lanes == 4'd8);
    wire [7:0] next_addr_lo = shifted;

    integer i;
    initial begin
        for (i = 0; i < MEM_DEPTH; i = i + 1) memory[i] = 8'hFF;
        state     = S_CMD;
        bits      = 4'd0;
        addr_byte = 2'd0;
        shreg     = 8'h00;
    end

    // Only ever drive the bus while returning read data; present the top
    // `lanes` bits of what is left to send.
    assign OSPI_IO = (state == S_RDATA && !OSPI_CS && HOLD_N)
                     ? ((rdata_sh >> (4'd8 - lanes)) & mask)
                     : 8'bzzzzzzzz;

    always @(posedge OSPI_CLK or negedge reset_n or posedge OSPI_CS) begin
        if (!reset_n) begin
            state     <= S_CMD;
            bits      <= 4'd0;
            addr_byte <= 2'd0;
            shreg     <= 8'h00;
        end else if (OSPI_CS) begin
            // Deasserting chip select ends the transaction.
            state     <= S_CMD;
            bits      <= 4'd0;
            addr_byte <= 2'd0;
            shreg     <= 8'h00;
        end else if (!HOLD_N) begin
            // Hold asserted: ignore the clock, keep every register as it is.
            state     <= state;
        end else begin
            shreg <= shifted;
            bits  <= byte_done ? 4'd0 : (bits + lanes);

            case (state)
                S_CMD: if (byte_done) begin
                    cmd   <= shifted;
                    state <= S_ADDR;
                end

                S_ADDR: if (byte_done) begin
                    addr <= {addr[15:0], next_addr_lo};
                    if (addr_byte == 2'd2) begin
                        addr_byte <= 2'd0;
                        case (cmd)
                            CMD_WRITE: state <= S_WDATA;
                            CMD_READ: begin
                                rdata_sh <= memory[next_addr_lo];
                                state    <= S_DUMMY;
                            end
                            CMD_ERASE: begin
                                memory[next_addr_lo] <= 8'hFF;
                                state                <= S_DONE;
                            end
                            default: state <= S_DONE;
                        endcase
                    end else begin
                        addr_byte <= addr_byte + 2'd1;
                    end
                end

                S_WDATA: if (byte_done) begin
                    memory[addr[7:0]] <= shifted;
                    state             <= S_DONE;
                end

                // One turnaround clock; the master releases OSPI_IO here.
                S_DUMMY: begin
                    bits  <= 4'd0;
                    state <= S_RDATA;
                end

                S_RDATA: begin
                    rdata_sh <= rdata_sh << lanes;
                    if (byte_done) state <= S_DONE;
                end

                default: ; // S_DONE: idle until chip select rises
            endcase
        end
    end

endmodule
