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
// A mismatched extension is rejected here. That is a modelling choice rather
// than a documented behaviour: the sources say what a controller must send,
// not what silicon does when it sends the wrong thing. Rejecting makes a
// misconfigured controller fail immediately instead of unpredictably.
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
                     OP_RST     = 8'h99,
                     OP_RDFSR   = 8'h70,   // read flag status register
                     OP_CLFSR   = 8'h50;   // clear flag status register

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
    reg        was_rst_enabled;

    // Flag Status Register. Bit polarity is the trap here: READY is 1 when
    // the part is *idle*, the opposite of the Status Register's WIP. And
    // unlike WIP, the error bits latch -- they say whether the last
    // operation actually worked, which WIP alone can never tell you.
    //   bit7 READY (0 = busy)  bit5 E_ERR  bit4 P_ERR  bit1 PT_ERR
    reg        fsr_e_err, fsr_p_err, fsr_pt_err;

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

    // A program or erase in flight, held as remaining nanoseconds. The work
    // is launched on the chip-select edge and done by a timer. A blocking
    // delay in that block would sit inside the always and miss every later
    // chip-select edge, so the part would ignore commands while busy
    // instead of reporting an error for them.
    reg        op_active;
    reg        op_is_erase;
    integer    op_remaining;
    reg [31:0] op_addr;
    reg [7:0]  op_data [0:PAGE_SIZE-1];
    integer    op_len;

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
        was_rst_enabled = 1'b0;
        fsr_e_err  = 1'b0;
        fsr_p_err  = 1'b0;
        fsr_pt_err = 1'b0;
        op_active  = 1'b0;
        op_is_erase = 1'b0;
        op_remaining = 0;
        op_len     = 0;
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
    wire [7:0] flag_status = {~wip, 1'b0, fsr_e_err, fsr_p_err,
                              2'b0, fsr_pt_err, 1'b0};

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
            // Linux reads FSR with the same shape as RDSR in DTR.
            OP_RDFSR:  dummy_for = octal ? 8 : 0;
            OP_RDSFDP: dummy_for = octal ? 20 : 8;
            default:   dummy_for = 0;
        endcase
    endfunction

    function is_read;
        input [7:0] op;
        case (op)
            OP_RDID, OP_RDSR, OP_RD_REG, OP_READ4B, OP_DTR_RD,
            OP_RDSFDP, OP_RDFSR: is_read = 1'b1;
            default: is_read = 1'b0;
        endcase
    endfunction

    task load_first_out;
        begin
            case (opcode)
                OP_RDID: outbyte = ID0;
                OP_RDSR: outbyte = status;
                OP_RDFSR: outbyte = flag_status;
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
                OP_RDFSR: outbyte = flag_status;
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
            // RSTEN arms a reset for the *next* command only. Anything else
            // clears the arming, so a stray RST cannot reset the part
            // mid-operation.
            was_rst_enabled = rst_enabled;
            rst_enabled = (opcode == OP_RSTEN);
            case (opcode)
                OP_WREN: begin if (!wip) wel = 1'b1; phase = P_DEAD; end
                OP_CLFSR: begin
                    // The error bits latch until explicitly cleared -- that
                    // is the whole point of them.
                    fsr_e_err = 1'b0; fsr_p_err = 1'b0; fsr_pt_err = 1'b0;
                    phase = P_DEAD;
                end
                OP_RSTEN: phase = P_DEAD;
                OP_RST: begin
                    if (was_rst_enabled) begin
                        cfr0v = CFR0V_EXT_SPI;
                        wel = 1'b0;
                        fsr_e_err = 1'b0; fsr_p_err = 1'b0; fsr_pt_err = 1'b0;
                    end
                    phase = P_DEAD;
                end
                OP_WRDI: begin wel = 1'b0; phase = P_DEAD; end
                default: begin
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
        // A program or erase issued while the part is still busy does not
        // happen -- and latches an error, which is how a controller that
        // failed to poll finds out. WIP alone would just read busy, and the
        // lost write would look like success once it cleared.
        if (wip && (opcode == OP_PP4B || opcode == OP_SE4B)) begin
            if (opcode == OP_PP4B) fsr_p_err = 1'b1;
            else                   fsr_e_err = 1'b1;
        end else if (opcode == OP_PP4B && wel && !wip && pp_count > 0) begin
            wip = 1'b1; wel = 1'b0;
            op_addr = pp_addr; op_len = pp_count;
            for (p = 0; p < pp_count; p = p + 1) op_data[p] = pp_data[p];
            op_active = 1'b1; op_is_erase = 1'b0;
            op_remaining = PROGRAM_NS;
        end else if (opcode == OP_SE4B && wel && !wip) begin
            wip = 1'b1; wel = 1'b0;
            op_addr = addr;
            op_active = 1'b1; op_is_erase = 1'b1;
            op_remaining = ERASE_NS;
        end
    end

    // The operation's own clock, so the model stays responsive while busy.
    always begin
        #1;
        if (op_active && op_remaining > 0) begin
            op_remaining = op_remaining - 1;
            if (op_remaining == 0) begin
                if (op_is_erase) begin
                    base = ((op_addr % MEM_DEPTH) / SECTOR_SIZE) * SECTOR_SIZE;
                    for (s = 0; s < SECTOR_SIZE; s = s + 1)
                        if (base + s < MEM_DEPTH) memory[base + s] = 8'hFF;
                end else begin
                    for (p = 0; p < op_len; p = p + 1) begin
                        // NOR programming clears bits; only an erase sets them.
                        base = (op_addr + p) % MEM_DEPTH;
                        memory[base] = memory[base] & op_data[p];
                    end
                end
                op_active = 1'b0;
                wip = 1'b0;
            end
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
