// Macronix MX25UM51345G — 512 Mb 1.8 V Octa Flash.
//
// Modelled from the datasheet (Rev 1.3, 2020-02-05), cross-checked against
// Linux drivers/mtd/spi-nor/macronix.c.
//
// The part boots in ordinary single-lane SPI and is switched into octal by
// writing Configuration Register 2. CR2 is address-mapped: WRCR2 (0x72)
// carries a 4-byte CR2 address, so the same opcode reaches several registers.
//
//   CR2 0x00000000  bit0 SOPI (STR octal), bit1 DOPI (DTR octal); 0 = SPI
//   CR2 0x00000200  DQS configuration
//   CR2 0x00000300  DC[2:0] dummy cycles for array reads
//
// In octal every command is two bytes: the opcode followed by its bitwise
// complement (Linux calls this SPI_NOR_EXT_INVERT). 8READ is EC/13, PP4B is
// 12/ED, WREN is 06/F9. A command whose second byte is not the complement is
// ignored, which is what the real part does and what catches a controller
// that forgot the extension.
//
// Addresses are 4 bytes in both modes for the commands modelled here.
// Register reads that need no dummy cycles in SPI need four in octal --
// RDSR, RDID and RDCR2 all gain an address phase and dummy cycles once the
// part is in OPI, which is a common source of bring-up bugs.
//
// Not modelled: 8D-8D-8D (DTR), DQS, SFDP, security/lock registers,
// suspend/resume, and the full 64 MB array -- MEM_DEPTH is a small window so
// simulations stay fast. See README for the complete list.

`timescale 1ns/1ps

module mx25um51345g #(
    parameter MEM_DEPTH   = 65536,
    parameter SECTOR_SIZE = 4096,
    parameter PAGE_SIZE   = 256,
    parameter PROGRAM_NS  = 1000,
    parameter ERASE_NS    = 5000
)(
    input  wire       clk,
    input  wire       csb,          // active low chip select
    inout  wire [7:0] io
);

    // ── SPI opcodes ──────────────────────────────────────────────────
    localparam [7:0] OP_RDID   = 8'h9F,
                     OP_RDSR   = 8'h05,
                     OP_WREN   = 8'h06,
                     OP_WRDI   = 8'h04,
                     OP_RDCR2  = 8'h71,
                     OP_WRCR2  = 8'h72,
                     OP_READ4B = 8'h13,   // SPI 4-byte read
                     OP_8READ  = 8'hEC,   // octal STR read
                     OP_PP4B   = 8'h12,
                     OP_SE4B   = 8'h21;

    // CR2 addresses.
    localparam [31:0] CR2_MODE  = 32'h00000000,
                      CR2_DQS   = 32'h00000200,
                      CR2_DUMMY = 32'h00000300;

    // CR2[0x00000000] encodings.
    localparam [7:0] MODE_SPI  = 8'h00,
                     MODE_SOPI = 8'h01,
                     MODE_DOPI = 8'h02;

    localparam [7:0] ID0 = 8'hC2,   // Macronix
                     ID1 = 8'h80,   // MX25UM, 1.8 V octal
                     ID2 = 8'h3A;   // 512 Mb

    // ── protocol phases ──────────────────────────────────────────────
    localparam [2:0] P_CMD   = 3'd0,
                     P_EXT   = 3'd1,
                     P_ADDR  = 3'd2,
                     P_DUMMY = 3'd3,
                     P_WRITE = 3'd4,
                     P_READ  = 3'd5,
                     P_DEAD  = 3'd6;   // malformed: ignore until CS rises

    reg [7:0]  memory [0:MEM_DEPTH-1];

    reg [7:0]  cr2_mode;      // CR2[0x00000000]
    reg [7:0]  cr2_dqs;       // CR2[0x00000200]
    reg [2:0]  cr2_dc;        // CR2[0x00000300], DC[2:0]
    reg        wel, wip;

    reg [2:0]  phase;
    reg [7:0]  shreg;
    integer    bitcount;
    integer    bytecount;      // bytes consumed within the current phase
    integer    dummy_left;
    reg [7:0]  opcode;
    reg [31:0] addr;
    reg [7:0]  outbyte;

    reg [7:0]  pp_data [0:PAGE_SIZE-1];
    integer    pp_count;
    reg [31:0] pp_addr;

    reg [31:0] pending_cr2_addr;

    reg        driving;
    reg [7:0]  dout;
    integer    lanes;

    // Dummy cycles for array reads, from the datasheet's DC table:
    // 000 = 20 (default), then 18, 16, 14, 12, 10, 8, 6.
    wire [5:0] array_dummy = 6'd20 - {cr2_dc, 1'b0};

    wire in_opi = (cr2_mode != MODE_SPI);

    integer i;
    initial begin
        for (i = 0; i < MEM_DEPTH; i = i + 1) memory[i] = 8'hFF;
        cr2_mode  = MODE_SPI;     // parts ship in SPI unless the OTP says otherwise
        cr2_dqs   = 8'h00;
        cr2_dc    = 3'b000;       // 20 dummy cycles
        wel       = 1'b0;
        wip       = 1'b0;
        phase     = P_CMD;
        shreg     = 8'h00;
        bitcount  = 0;
        bytecount = 0;
        pp_count  = 0;
        driving   = 1'b0;
        lanes     = 1;
    end

    // The device answers on io1 in SPI and across all eight lanes in octal.
    assign io[0] = (driving && lanes == 8) ? dout[0] : 1'bz;
    assign io[1] = driving                 ? dout[1] : 1'bz;
    assign io[2] = (driving && lanes == 8) ? dout[2] : 1'bz;
    assign io[3] = (driving && lanes == 8) ? dout[3] : 1'bz;
    assign io[4] = (driving && lanes == 8) ? dout[4] : 1'bz;
    assign io[5] = (driving && lanes == 8) ? dout[5] : 1'bz;
    assign io[6] = (driving && lanes == 8) ? dout[6] : 1'bz;
    assign io[7] = (driving && lanes == 8) ? dout[7] : 1'bz;

    wire [7:0] status = {6'b0, wel, wip};

    // ── per-command shape ────────────────────────────────────────────
    function integer addr_bytes_for;
        input [7:0] op;
        case (op)
            OP_RDCR2, OP_WRCR2, OP_READ4B, OP_8READ,
            OP_PP4B, OP_SE4B: addr_bytes_for = 4;
            // In octal these gain an address phase they do not have in SPI.
            OP_RDSR, OP_RDID: addr_bytes_for = in_opi ? 4 : 0;
            default: addr_bytes_for = 0;
        endcase
    endfunction

    function integer dummy_for;
        input [7:0] op;
        case (op)
            OP_8READ:  dummy_for = array_dummy;
            OP_READ4B: dummy_for = 0;
            // Register reads need four dummy cycles once in OPI.
            OP_RDSR, OP_RDID, OP_RDCR2: dummy_for = in_opi ? 4 : 0;
            default: dummy_for = 0;
        endcase
    endfunction

    function is_read;
        input [7:0] op;
        case (op)
            OP_RDID, OP_RDSR, OP_RDCR2, OP_READ4B, OP_8READ: is_read = 1'b1;
            default: is_read = 1'b0;
        endcase
    endfunction

    // First byte a read command returns.
    task load_first_out;
        begin
            case (opcode)
                OP_RDID:  outbyte = ID0;
                OP_RDSR:  outbyte = status;
                OP_RDCR2: begin
                    case (addr)
                        CR2_MODE:  outbyte = cr2_mode;
                        CR2_DQS:   outbyte = cr2_dqs;
                        CR2_DUMMY: outbyte = {5'b0, cr2_dc};
                        default:   outbyte = 8'h00;
                    endcase
                end
                OP_READ4B, OP_8READ: outbyte = memory[addr % MEM_DEPTH];
                default: outbyte = 8'h00;
            endcase
        end
    endtask

    task advance_out;
        begin
            case (opcode)
                OP_RDID:  outbyte = (bytecount == 1) ? ID1 :
                                    (bytecount == 2) ? ID2 : 8'h00;
                OP_RDSR:  outbyte = status;          // repeats while clocked
                OP_RDCR2: outbyte = outbyte;         // same register repeats
                OP_READ4B, OP_8READ: begin
                    addr = addr + 1;
                    outbyte = memory[addr % MEM_DEPTH];
                end
                default: outbyte = 8'h00;
            endcase
        end
    endtask

    // ── end of a received byte ───────────────────────────────────────
    task got_byte;
        begin
            case (phase)
                P_CMD: begin
                    opcode = shreg;
                    if (in_opi) begin
                        phase = P_EXT;
                    end else begin
                        bytecount = 0;
                        start_body;
                    end
                end

                P_EXT: begin
                    // Octal command extension: the complement of the opcode.
                    if (shreg != ~opcode) begin
                        phase = P_DEAD;
                    end else begin
                        bytecount = 0;
                        start_body;
                    end
                end

                P_ADDR: begin
                    addr = {addr[23:0], shreg};
                    bytecount = bytecount + 1;
                    if (bytecount == addr_bytes_for(opcode)) begin
                        bytecount = 0;
                        after_addr;
                    end
                end

                P_WRITE: begin
                    if (opcode == OP_WRCR2) begin
                        case (addr)
                            CR2_MODE:  cr2_mode = shreg;
                            CR2_DQS:   cr2_dqs  = shreg;
                            CR2_DUMMY: cr2_dc   = shreg[2:0];
                            default: ;
                        endcase
                        phase = P_DEAD;      // one data byte only
                    end else if (opcode == OP_PP4B) begin
                        if (pp_count < PAGE_SIZE) begin
                            pp_data[pp_count] = shreg;
                            pp_count = pp_count + 1;
                        end
                    end
                end

                default: ;   // P_DUMMY / P_READ never land here
            endcase
        end
    endtask

    // Decide what follows the command (and extension) bytes.
    task start_body;
        begin
            case (opcode)
                OP_WREN: begin if (!wip) wel = 1'b1; phase = P_DEAD; end
                OP_WRDI: begin wel = 1'b0; phase = P_DEAD; end
                default: begin
                    addr = 32'h0;
                    if (addr_bytes_for(opcode) > 0) begin
                        phase = P_ADDR;
                    end else begin
                        after_addr;
                    end
                end
            endcase
        end
    endtask

    task after_addr;
        begin
            dummy_left = dummy_for(opcode);
            if (opcode == OP_PP4B) begin
                pp_addr  = addr;
                pp_count = 0;
                phase    = P_WRITE;
            end else if (opcode == OP_SE4B) begin
                phase = P_DEAD;              // acted on when CS rises
            end else if (opcode == OP_WRCR2) begin
                pending_cr2_addr = addr;
                phase = P_WRITE;
            end else if (is_read(opcode)) begin
                load_first_out;
                phase = (dummy_left > 0) ? P_DUMMY : P_READ;
            end else begin
                phase = P_DEAD;
            end
        end
    endtask

    // ── chip select ──────────────────────────────────────────────────
    integer p, base, s;
    always @(posedge csb) begin
        // Commit program and erase when the transaction closes.
        if (opcode == OP_PP4B && wel && !wip && pp_count > 0) begin
            wip = 1'b1;
            wel = 1'b0;
            for (p = 0; p < pp_count; p = p + 1) begin
                // NOR programming clears bits; only an erase sets them.
                base = (pp_addr + p) % MEM_DEPTH;
                memory[base] = memory[base] & pp_data[p];
            end
            #(PROGRAM_NS) wip = 1'b0;
        end else if (opcode == OP_SE4B && wel && !wip) begin
            wip = 1'b1;
            wel = 1'b0;
            base = ((addr % MEM_DEPTH) / SECTOR_SIZE) * SECTOR_SIZE;
            for (s = 0; s < SECTOR_SIZE; s = s + 1)
                if (base + s < MEM_DEPTH) memory[base + s] = 8'hFF;
            #(ERASE_NS) wip = 1'b0;
        end
    end

    always @(csb) begin
        phase     = P_CMD;
        shreg     = 8'h00;
        bitcount  = 0;
        bytecount = 0;
        driving   = 1'b0;
        // The mode in force is latched at the start of each transaction, so
        // a WRCR2 that switches protocol takes effect on the *next* command.
        lanes     = in_opi ? 8 : 1;
        if (!csb) begin
            opcode   = 8'h00;
            pp_count = 0;
        end
    end

    // ── device drives while the clock is low ─────────────────────────
    always @(csb, clk) begin
        if (!csb && !clk && phase == P_READ) begin
            driving = 1'b1;
            dout = outbyte;
            if (lanes == 1) dout[1] = outbyte[7 - bitcount];
        end else if (csb || phase != P_READ) begin
            driving = 1'b0;
        end
    end

    // ── sample the master ────────────────────────────────────────────
    always @(posedge clk) begin
        if (!csb) begin
            if (phase == P_DUMMY) begin
                dummy_left = dummy_left - 1;
                if (dummy_left == 0) phase = P_READ;
            end else if (phase == P_READ) begin
                bitcount = bitcount + lanes;
                if (bitcount >= 8) begin
                    bitcount  = 0;
                    bytecount = bytecount + 1;
                    advance_out;
                end
            end else if (phase != P_DEAD) begin
                if (lanes == 8) shreg = io;
                else            shreg = {shreg[6:0], io[0]};
                bitcount = bitcount + lanes;
                if (bitcount >= 8) begin
                    bitcount = 0;
                    got_byte;
                end
            end
        end
    end

endmodule
