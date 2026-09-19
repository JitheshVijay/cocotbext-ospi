// Micron MT35XU512ABA — 512 Mb 1.8 V Xccela octal NOR flash.
//
// Modelled from Linux drivers/mtd/spi-nor/micron-st.c, which is tested
// against the real part, plus the Xccela/JESD251 conventions it follows.
//
// The part boots in "extended SPI" (single lane) and is switched into octal
// DTR by writing two volatile configuration registers with WRITE VOLATILE
// REGISTER (0x81):
//
//   CFR1V @ 0x01   dummy cycles for array reads (20 for 8D-8D-8D)
//   CFR0V @ 0x00   0xE7 enters octal DTR, 0xFF returns to extended SPI
//
// The command extension repeats the opcode rather than inverting it -- Linux
// calls this SPI_NOR_EXT_REPEAT, and it is the one thing most likely to be
// wrong in a controller ported from a Macronix part.
//
// 8D-8D-8D carries a bit per lane on *both* clock edges, so eight lanes move
// two bytes per clock. That is why an odd-length transfer is impossible in
// this mode; Linux works around it when disabling octal by writing CFR0V and
// CFR1V together as one 2-byte write.
//
// Not modelled: DQS, SFDP, the flag status register, protection registers,
// and the full 64 MB array -- MEM_DEPTH is a small window so simulations
// stay fast.

`timescale 1ns/1ps

module mt35xu512aba #(
    parameter MEM_DEPTH   = 65536,
    parameter SECTOR_SIZE = 4096,
    parameter PAGE_SIZE   = 256,
    parameter PROGRAM_NS  = 1000,
    parameter ERASE_NS    = 5000
)(
    input  wire       clk,
    input  wire       csb,
    inout  wire [7:0] io
);

    localparam [7:0] OP_RDID    = 8'h9F,
                     OP_RDSR    = 8'h05,
                     OP_WREN    = 8'h06,
                     OP_WRDI    = 8'h04,
                     OP_RD_REG  = 8'h85,   // read volatile register
                     OP_WR_REG  = 8'h81,   // write volatile register
                     OP_READ4B  = 8'h13,   // extended-SPI 4-byte read
                     OP_DTR_RD  = 8'hFD,   // octal DTR fast read
                     OP_PP4B    = 8'h12,
                     OP_SE4B    = 8'h21,
                     OP_RDSFDP  = 8'h5A,
                     OP_RSTEN   = 8'h66,
                     OP_RST     = 8'h99;

    localparam [7:0] CFR0V_ADDR = 8'h00,
                     CFR1V_ADDR = 8'h01;

    localparam [7:0] CFR0V_OCTAL_DTR = 8'hE7,
                     CFR0V_EXT_SPI   = 8'hFF;

    localparam [7:0] ID0 = 8'h2C,   // Micron
                     ID1 = 8'h5B,   // MT35XU, 1.8 V octal
                     ID2 = 8'h1A;   // 512 Mb

    localparam [2:0] P_CMD   = 3'd0,
                     P_EXT   = 3'd1,
                     P_ADDR  = 3'd2,
                     P_DUMMY = 3'd3,
                     P_WRITE = 3'd4,
                     P_READ  = 3'd5,
                     P_DEAD  = 3'd6;

    reg [7:0]  memory [0:MEM_DEPTH-1];

`include "mt35xu512aba_sfdp.vh"

    reg [7:0]  cfr0v, cfr1v;
    reg        wel, wip;
    reg        rst_enabled;   // RSTEN must immediately precede RST

    reg [2:0]  phase;
    reg [7:0]  shreg;
    integer    bitcount;
    integer    bytecount;
    integer    dummy_left;
    reg [7:0]  opcode;
    reg [31:0] addr;
    reg [7:0]  outbyte;
    reg [7:0]  reg_addr;

    reg [7:0]  pp_data [0:PAGE_SIZE-1];
    integer    pp_count;
    reg [31:0] pp_addr;

    reg        driving;
    reg [7:0]  dout;
    integer    lanes;
    reg        dtr;

    // Delayed copy of the bus. In DTR the master changes data on the same
    // edges the device samples, so sampling the live net races it; every
    // DDR-capable model does this.
    wire [7:0] io_d;
    assign #1 io_d = io;

    wire octal = (cfr0v == CFR0V_OCTAL_DTR);

    integer i;
    initial begin
        for (i = 0; i < MEM_DEPTH; i = i + 1) memory[i] = 8'hFF;
        cfr0v     = CFR0V_EXT_SPI;   // ships in extended SPI
        cfr1v     = 8'h1F;           // Linux's SPINOR_REG_MT_CFR1V_DEF
        wel       = 1'b0;
        wip       = 1'b0;
        rst_enabled = 1'b0;
        phase     = P_CMD;
        shreg     = 8'h00;
        bitcount  = 0;
        bytecount = 0;
        pp_count  = 0;
        driving   = 1'b0;
        lanes     = 1;
        dtr       = 1'b0;
    end

    // Drive through a 1 ns delay. The master samples on clock edges and the
    // device updates on those same edges, so driving the live value races
    // it -- the master could see this edge's byte or the last one. Every
    // DDR-capable flash model does this.
    wire [7:0] dout_d;
    assign #1 dout_d = dout;
    wire driving_d;
    assign #1 driving_d = driving;

    assign io[0] = (driving_d && lanes == 8) ? dout_d[0] : 1'bz;
    assign io[1] = driving_d                 ? dout_d[1] : 1'bz;
    assign io[2] = (driving_d && lanes == 8) ? dout_d[2] : 1'bz;
    assign io[3] = (driving_d && lanes == 8) ? dout_d[3] : 1'bz;
    assign io[4] = (driving_d && lanes == 8) ? dout_d[4] : 1'bz;
    assign io[5] = (driving_d && lanes == 8) ? dout_d[5] : 1'bz;
    assign io[6] = (driving_d && lanes == 8) ? dout_d[6] : 1'bz;
    assign io[7] = (driving_d && lanes == 8) ? dout_d[7] : 1'bz;

    wire [7:0] status = {6'b0, wel, wip};

    function integer addr_bytes_for;
        input [7:0] op;
        case (op)
            OP_READ4B, OP_DTR_RD, OP_PP4B, OP_SE4B: addr_bytes_for = 4;
            OP_RDSFDP: addr_bytes_for = octal ? 4 : 3;
            // Register access carries an address naming the register.
            OP_RD_REG, OP_WR_REG: addr_bytes_for = 4;
            default: addr_bytes_for = 0;
        endcase
    endfunction

    function integer dummy_for;
        input [7:0] op;
        case (op)
            OP_DTR_RD: dummy_for = cfr1v;          // CFR1V holds the count
            OP_RD_REG: dummy_for = octal ? 8 : 0;  // Linux: rdsr_dummy = 8
            OP_RDSR:   dummy_for = octal ? 8 : 0;
            OP_RDID:   dummy_for = octal ? 8 : 0;
            OP_RDSFDP: dummy_for = octal ? 20 : 8;
            default:   dummy_for = 0;
        endcase
    endfunction

    function is_read;
        input [7:0] op;
        case (op)
            OP_RDID, OP_RDSR, OP_RD_REG, OP_READ4B, OP_DTR_RD,
            OP_RDSFDP: is_read = 1'b1;
            default: is_read = 1'b0;
        endcase
    endfunction

    task load_first_out;
        begin
            case (opcode)
                OP_RDID: outbyte = ID0;
                OP_RDSR: outbyte = status;
                OP_RD_REG: begin
                    case (addr[7:0])
                        CFR0V_ADDR: outbyte = cfr0v;
                        CFR1V_ADDR: outbyte = cfr1v;
                        default:    outbyte = 8'h00;
                    endcase
                end
                OP_READ4B, OP_DTR_RD: outbyte = memory[addr % MEM_DEPTH];
                OP_RDSFDP: outbyte = sfdp[addr % SFDP_BYTES];
                default: outbyte = 8'h00;
            endcase
        end
    endtask

    task advance_out;
        begin
            case (opcode)
                OP_RDID: outbyte = (bytecount == 1) ? ID1 :
                                   (bytecount == 2) ? ID2 : 8'h00;
                OP_RDSR: outbyte = status;
                OP_RD_REG: outbyte = outbyte;
                OP_READ4B, OP_DTR_RD: begin
                    addr = addr + 1;
                    outbyte = memory[addr % MEM_DEPTH];
                end
                OP_RDSFDP: begin
                    addr = addr + 1;
                    outbyte = sfdp[addr % SFDP_BYTES];
                end
                default: outbyte = 8'h00;
            endcase
        end
    endtask

    task start_body;
        begin
            case (opcode)
                OP_WREN: begin if (!wip) wel = 1'b1; phase = P_DEAD; end
                OP_RSTEN: begin rst_enabled = 1'b1; phase = P_DEAD; end
                OP_RST: begin
                    // Only honoured directly after RSTEN, as the part
                    // requires; any other command in between cancels it.
                    if (rst_enabled) begin
                        cfr0v = CFR0V_EXT_SPI;
                        wel = 1'b0;
                    end
                    rst_enabled = 1'b0;
                    phase = P_DEAD;
                end
                OP_WRDI: begin wel = 1'b0; phase = P_DEAD; end
                default: begin
                    rst_enabled = 1'b0;
                    addr = 32'h0;
                    if (addr_bytes_for(opcode) > 0) phase = P_ADDR;
                    else                            after_addr;
                end
            endcase
        end
    endtask

    task after_addr;
        begin
            dummy_left = dummy_for(opcode);
            if (opcode == OP_PP4B) begin
                pp_addr = addr; pp_count = 0; phase = P_WRITE;
            end else if (opcode == OP_SE4B) begin
                phase = P_DEAD;
            end else if (opcode == OP_WR_REG) begin
                reg_addr = addr[7:0];
                phase = P_WRITE;
            end else if (is_read(opcode)) begin
                load_first_out;
                phase = (dummy_left > 0) ? P_DUMMY : P_READ;
            end else begin
                phase = P_DEAD;
            end
        end
    endtask

    task got_byte;
        begin
            case (phase)
                P_CMD: begin
                    opcode = shreg;
                    if (octal) phase = P_EXT;
                    else begin bytecount = 0; start_body; end
                end

                P_EXT: begin
                    // Micron repeats the opcode rather than inverting it.
                    if (shreg != opcode) phase = P_DEAD;
                    else begin bytecount = 0; start_body; end
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
                    if (opcode == OP_WR_REG) begin
                        case (reg_addr)
                            CFR0V_ADDR: cfr0v = shreg;
                            CFR1V_ADDR: cfr1v = shreg;
                            default: ;
                        endcase
                        // Consecutive registers: a 2-byte write lands in the
                        // next one, which is how Linux leaves octal DTR.
                        reg_addr = reg_addr + 1;
                    end else if (opcode == OP_PP4B) begin
                        if (pp_count < PAGE_SIZE) begin
                            pp_data[pp_count] = shreg;
                            pp_count = pp_count + 1;
                        end
                    end
                end

                default: ;
            endcase
        end
    endtask

    integer p, base, s;
    always @(posedge csb) begin
        if (opcode == OP_PP4B && wel && !wip && pp_count > 0) begin
            wip = 1'b1; wel = 1'b0;
            for (p = 0; p < pp_count; p = p + 1) begin
                base = (pp_addr + p) % MEM_DEPTH;
                memory[base] = memory[base] & pp_data[p];
            end
            #(PROGRAM_NS) wip = 1'b0;
        end else if (opcode == OP_SE4B && wel && !wip) begin
            wip = 1'b1; wel = 1'b0;
            base = ((addr % MEM_DEPTH) / SECTOR_SIZE) * SECTOR_SIZE;
            for (s = 0; s < SECTOR_SIZE; s = s + 1)
                if (base + s < MEM_DEPTH) memory[base + s] = 8'hFF;
            #(ERASE_NS) wip = 1'b0;
        end
    end

    always @(csb) begin
        phase = P_CMD; shreg = 8'h00; bitcount = 0; bytecount = 0;
        driving = 1'b0;
        // The protocol in force is latched per transaction, so the WRCFR
        // that switches modes takes effect from the next command.
        lanes = octal ? 8 : 1;
        dtr   = octal;
        if (!csb) begin opcode = 8'h00; pp_count = 0; end
    end

    // ── shifting, on one or both edges ───────────────────────────────
    task sample_edge;
        begin
            if (phase == P_DUMMY) begin
                // Dummy cycles are quoted in clocks, so only count rising.
                if (clk) begin
                    dummy_left = dummy_left - 1;
                    if (dummy_left == 0) phase = P_READ;
                end
            end else if (phase == P_READ) begin
                bitcount = bitcount + lanes;
                if (bitcount >= 8) begin
                    bitcount = 0;
                    bytecount = bytecount + 1;
                    advance_out;
                end
            end else if (phase != P_DEAD) begin
                if (lanes == 8) shreg = dtr ? io_d : io;
                else            shreg = {shreg[6:0], io[0]};
                bitcount = bitcount + lanes;
                if (bitcount >= 8) begin
                    bitcount = 0;
                    got_byte;
                end
            end
        end
    endtask

    always @(clk) begin
        if (!csb) begin
            if (dtr)        sample_edge;   // both edges
            else if (clk)   sample_edge;   // rising only
        end
    end

    // ── driving ──────────────────────────────────────────────────────
    // Combinational: phase can change on the same edge the master is
    // about to sample, so a block sensitive only to clk and csb would
    // not re-evaluate until the next edge and the bus would read as
    // released for the first byte.
    always @(*) begin
        if (!csb && phase == P_READ && (dtr || !clk)) begin
            driving = 1'b1;
            dout = outbyte;
            if (lanes == 1) dout[1] = outbyte[7 - bitcount];
        end else if (csb || phase != P_READ) begin
            driving = 1'b0;
        end
    end

endmodule
