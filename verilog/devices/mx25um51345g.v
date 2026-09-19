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
// 12/ED, WREN is 06/F9.
//
// A command whose second byte is not the complement is rejected here. That
// is a modelling choice, not a documented behaviour -- the datasheet gives
// the extension for every opcode but does not say what silicon does with a
// mismatched one. Rejecting is the useful choice for a model: it turns a
// controller configured for the wrong vendor's extension into an immediate,
// obvious failure instead of undefined behaviour. Do not read the test that
// pins this as a claim about the real part.
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
    inout  wire [7:0] io,
    // Read data strobe. A separate pin, not part of SIO[7:0]: the device
    // toggles it alongside read data so a controller can capture with the
    // data rather than with its own clock, which is what makes high-speed
    // DTR reads timing-closable. Enabled by CR2[0x200].
    output wire       dqs
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
                     OP_8DTRD  = 8'hEE,   // octal DTR read
                     OP_RDSFDP = 8'h5A,
                     OP_RSTEN  = 8'h66,
                     OP_RST    = 8'h99,
                     OP_PP4B   = 8'h12,
                     OP_SE4B   = 8'h21,
                     OP_RDSCUR = 8'h2B,   // read security register
                     OP_WRSCUR = 8'h2F,   // write security register
                     OP_WPSEL  = 8'h68,   // switch to advanced protection
                     OP_WRDPB  = 8'hE1,   // write dynamic protection bit
                     OP_RDDPB  = 8'hE0,   // read dynamic protection bit
                     OP_SUSPEND = 8'hB0,
                     OP_RESUME  = 8'h30;

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

`include "mx25um51345g_sfdp.vh"

    reg [7:0]  cr2_mode;      // CR2[0x00000000]
    reg [7:0]  cr2_dqs;       // CR2[0x00000200]
    reg [2:0]  cr2_dc;        // CR2[0x00000300], DC[2:0]
    reg        wel, wip;
    reg        rst_enabled;   // RSTEN must immediately precede RST
    reg        was_rst_enabled;

    // Security register (RDSCUR). Datasheet Table 5:
    //   bit7 WPSEL  bit6 E_FAIL  bit5 P_FAIL  bit4 reserved
    //   bit3 ESB    bit2 PSB     bit1 LDSO    bit0 secured-OTP indicator
    reg        wpsel;         // 0 = BP protection, 1 = advanced sector protection
    reg        e_fail, p_fail;
    reg        esb, psb;      // erase / program suspended
    reg        ldso;

    // Dynamic protection bits, one per sector. Volatile, and only consulted
    // once WPSEL has switched the part to advanced sector protection.
    reg        dpb [0:(MEM_DEPTH/SECTOR_SIZE)-1];

    // A program or erase in flight. Held as remaining nanoseconds so a
    // suspend can genuinely pause it rather than the operation completing
    // instantly and suspend becoming a no-op.
    reg        op_active;
    reg        op_is_erase;
    integer    op_remaining;
    reg [31:0] op_addr;
    reg [7:0]  op_data [0:PAGE_SIZE-1];
    integer    op_len;

    reg [2:0]  phase;
    reg [7:0]  shreg;
    integer    bitcount;
    integer    bytecount;      // bytes consumed within the current phase
    integer    dummy_left;
    reg [7:0]  opcode;
    reg [31:0] addr;
    reg [7:0]  outbyte;


    reg [31:0] pending_cr2_addr;

    reg        driving;
    reg [7:0]  dout;
    integer    lanes;
    reg        dtr;

    // Delayed copy of the bus. In DTR the master changes data on the same
    // edges the device samples, so sampling the live net races it.
    wire [7:0] io_d;
    assign #1 io_d = io;

    // Dummy cycles for array reads, from the datasheet's DC table:
    // 000 = 20 (default), then 18, 16, 14, 12, 10, 8, 6.
    wire [5:0] array_dummy = 6'd20 - {cr2_dc, 1'b0};

    wire in_opi = (cr2_mode != MODE_SPI);
    wire in_dopi = (cr2_mode == MODE_DOPI);

    integer i;
    initial begin
        for (i = 0; i < MEM_DEPTH; i = i + 1) memory[i] = 8'hFF;
        cr2_mode  = MODE_SPI;     // parts ship in SPI unless the OTP says otherwise
        cr2_dqs   = 8'h00;
        cr2_dc    = 3'b000;       // 20 dummy cycles
        wel       = 1'b0;
        wip       = 1'b0;
        rst_enabled = 1'b0;
        was_rst_enabled = 1'b0;
        wpsel     = 1'b0;
        e_fail    = 1'b0;
        p_fail    = 1'b0;
        esb       = 1'b0;
        psb       = 1'b0;
        ldso      = 1'b0;
        op_active = 1'b0;
        op_is_erase = 1'b0;
        op_remaining = 0;
        op_len    = 0;
        for (i = 0; i < MEM_DEPTH/SECTOR_SIZE; i = i + 1) dpb[i] = 1'b0;
        phase     = P_CMD;
        shreg     = 8'h00;
        bitcount  = 0;
        bytecount = 0;
        driving   = 1'b0;
        lanes     = 1;
        dtr       = 1'b0;
    end

    // The device answers on io1 in SPI and across all eight lanes in octal.
    // DQS toggles only while the device is actually returning read data.
    // It is free-running there and parked low otherwise, so a controller can
    // gate on it. DOS (CR2[0x200] bit 1) enables it in STR; in DTR it is
    // always on. DQSPRC adds a pre-cycle, modelled as an extra leading
    // toggle so a controller can train on it before data arrives.
    wire dqs_enabled = in_dopi || (in_opi && cr2_dqs[1]);
    reg  dqs_r;
    assign #1 dqs = dqs_r;

    always @(*) begin
        if (!csb && dqs_enabled && phase == P_READ) dqs_r = clk;
        else                                       dqs_r = 1'b0;
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
    wire [7:0] security = {wpsel, e_fail, p_fail, 1'b0, esb, psb, ldso, 1'b0};
    wire       suspended = esb | psb;

    // Datasheet Table 7, "Acceptable Commands During Suspend". Notably PP
    // and SE are absent: this part cannot program during an erase suspend.
    function allowed_while_suspended;
        input [7:0] op;
        case (op)
            OP_READ4B, OP_8READ, OP_8DTRD, OP_RDSFDP, OP_RDID,
            OP_WREN, OP_WRDI, OP_RESUME, OP_RDDPB,
            OP_RDCR2, OP_WRCR2, OP_RDSR, OP_RDSCUR,
            OP_RSTEN, OP_RST: allowed_while_suspended = 1'b1;
            default: allowed_while_suspended = 1'b0;
        endcase
    endfunction

    // A sector is protected only in advanced mode, and only if its DPB is set.
    function sector_protected;
        input [31:0] a;
        sector_protected = wpsel && dpb[(a % MEM_DEPTH) / SECTOR_SIZE];
    endfunction

    // ── per-command shape ────────────────────────────────────────────
    function integer addr_bytes_for;
        input [7:0] op;
        case (op)
            OP_RDCR2, OP_WRCR2, OP_READ4B, OP_8READ, OP_8DTRD,
            OP_PP4B, OP_SE4B, OP_WRDPB, OP_RDDPB: addr_bytes_for = 4;
            // In OPI even a register read takes an address phase.
            OP_RDSCUR: addr_bytes_for = in_opi ? 4 : 0;
            // RDSFDP takes 3 address bytes in SPI and 4 in OPI.
            OP_RDSFDP: addr_bytes_for = in_opi ? 4 : 3;
            // In octal these gain an address phase they do not have in SPI.
            OP_RDSR, OP_RDID: addr_bytes_for = in_opi ? 4 : 0;
            default: addr_bytes_for = 0;
        endcase
    endfunction

    function integer dummy_for;
        input [7:0] op;
        case (op)
            OP_8READ, OP_8DTRD: dummy_for = array_dummy;
            OP_READ4B: dummy_for = 0;
            // 8 dummy cycles in SPI, 20 in OPI, per the command tables.
            OP_RDSFDP: dummy_for = in_opi ? 20 : 8;
            // Register reads need four dummy cycles once in OPI.
            OP_RDSR, OP_RDID, OP_RDCR2, OP_RDSCUR,
            OP_RDDPB: dummy_for = in_opi ? 4 : 0;
            default: dummy_for = 0;
        endcase
    endfunction

    function is_read;
        input [7:0] op;
        case (op)
            OP_RDID, OP_RDSR, OP_RDCR2, OP_READ4B, OP_8READ,
            OP_8DTRD, OP_RDSFDP, OP_RDSCUR, OP_RDDPB: is_read = 1'b1;
            default: is_read = 1'b0;
        endcase
    endfunction

    // First byte a read command returns.
    task load_first_out;
        begin
            case (opcode)
                OP_RDID:  outbyte = ID0;
                OP_RDSR:  outbyte = status;
                OP_RDSCUR: outbyte = security;
                OP_RDDPB: outbyte = dpb[(addr % MEM_DEPTH) / SECTOR_SIZE] ? 8'hFF : 8'h00;
                OP_RDCR2: begin
                    case (addr)
                        CR2_MODE:  outbyte = cr2_mode;
                        CR2_DQS:   outbyte = cr2_dqs;
                        CR2_DUMMY: outbyte = {5'b0, cr2_dc};
                        default:   outbyte = 8'h00;
                    endcase
                end
                OP_READ4B, OP_8READ, OP_8DTRD: outbyte = memory[addr % MEM_DEPTH];
                OP_RDSFDP: outbyte = sfdp[addr % SFDP_BYTES];
                default: outbyte = 8'h00;
            endcase
        end
    endtask

    task advance_out;
        begin
            case (opcode)
                OP_RDID:  outbyte = (bytecount == 1) ? ID1 :
                                    (bytecount == 2) ? ID2 : 8'h00;
                OP_RDSR:  outbyte = status;
                OP_RDSCUR: outbyte = security;
                OP_RDDPB: outbyte = dpb[(addr % MEM_DEPTH) / SECTOR_SIZE] ? 8'hFF : 8'h00;          // repeats while clocked
                OP_RDCR2: outbyte = outbyte;         // same register repeats
                OP_READ4B, OP_8READ, OP_8DTRD: begin
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
                        if (op_len < PAGE_SIZE) begin
                            op_data[op_len] = shreg;
                            op_len = op_len + 1;
                        end
                    end else if (opcode == OP_WRSCUR) begin
                        // Only LDSO is customer-writable, and it is one-way.
                        if (shreg[1]) ldso = 1'b1;
                        phase = P_DEAD;
                    end else if (opcode == OP_WRDPB) begin
                        dpb[(addr % MEM_DEPTH) / SECTOR_SIZE] = (shreg != 8'h00);
                        phase = P_DEAD;
                    end
                end

                default: ;   // P_DUMMY / P_READ never land here
            endcase
        end
    endtask

    // Decide what follows the command (and extension) bytes.
    task start_body;
        begin
            // RSTEN arms a reset for the *next* command only. Anything else
            // clears the arming, so a stray RST cannot reset the part
            // mid-operation.
            was_rst_enabled = rst_enabled;
            rst_enabled = (opcode == OP_RSTEN);
            // Datasheet Table 7 lists what a suspended part accepts. Anything
            // else is rejected -- a controller that programs during an erase
            // suspend on this part gets nothing, which is the bug this catches.
            if (suspended && !allowed_while_suspended(opcode)) begin
                phase = P_DEAD;
            end else
            case (opcode)
                OP_WREN: begin if (!wip) wel = 1'b1; phase = P_DEAD; end
                OP_WPSEL: begin
                    // One-way: advanced sector protection cannot be undone.
                    if (wel) begin wpsel = 1'b1; wel = 1'b0; end
                    phase = P_DEAD;
                end
                OP_SUSPEND: begin
                    if (op_active && wip) begin
                        if (op_is_erase) esb = 1'b1; else psb = 1'b1;
                        wip = 1'b0;   // the part becomes ready for other work
                    end
                    phase = P_DEAD;
                end
                OP_RESUME: begin
                    if (suspended) begin
                        // Resume re-arms WEL and WIP, per section 10-29.
                        esb = 1'b0; psb = 1'b0;
                        wip = 1'b1; wel = 1'b1;
                    end
                    phase = P_DEAD;
                end
                OP_RSTEN: phase = P_DEAD;
                OP_RST: begin
                    if (was_rst_enabled) begin
                        cr2_mode = MODE_SPI;
                        wel = 1'b0;
                        esb = 1'b0; psb = 1'b0;
                        e_fail = 1'b0; p_fail = 1'b0;
                        op_active = 1'b0; op_remaining = 0;
                        wip = 1'b0;
                    end
                    phase = P_DEAD;
                end
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
            // Datasheet note 5: in DTR OPI the starting address must be even
            // (A0 = 0). An odd address is rejected rather than quietly
            // returning the wrong byte.
            if (in_dopi && addr[0] &&
                (opcode == OP_8DTRD || opcode == OP_PP4B)) begin
                phase = P_DEAD;
            end else
            if (opcode == OP_PP4B) begin
                op_addr = addr;
                op_len  = 0;
                phase   = P_WRITE;
            end else if (opcode == OP_SE4B) begin
                phase = P_DEAD;              // acted on when CS rises
            end else if (opcode == OP_WRCR2 || opcode == OP_WRSCUR ||
                         opcode == OP_WRDPB) begin
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

    // Launch a program or erase when the transaction closes. The work is not
    // done here -- it is handed to the timer below so that a suspend can
    // actually pause it. Committing immediately would make suspend a no-op
    // and hide the bugs it exists to expose.
    always @(posedge csb) begin
        if (opcode == OP_PP4B && wel && !wip && !suspended && op_len > 0) begin
            if (sector_protected(op_addr)) begin
                // A protected region reports failure rather than silently
                // doing nothing: P_FAIL is how a controller finds out.
                p_fail = 1'b1;
                wel    = 1'b0;
            end else begin
                wip = 1'b1; wel = 1'b0;
                op_active = 1'b1; op_is_erase = 1'b0;
                op_remaining = PROGRAM_NS;
            end
        end else if (opcode == OP_SE4B && wel && !wip && !suspended) begin
            if (sector_protected(addr)) begin
                e_fail = 1'b1;
                wel    = 1'b0;
            end else begin
                op_addr = addr;
                wip = 1'b1; wel = 1'b0;
                op_active = 1'b1; op_is_erase = 1'b1;
                op_remaining = ERASE_NS;
            end
        end
    end

    // The operation's own clock. Ticks only while the part is neither
    // suspended nor idle, so ESB/PSB genuinely hold the work off.
    always begin
        #1;
        if (op_active && !suspended && op_remaining > 0) begin
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
        phase     = P_CMD;
        shreg     = 8'h00;
        bitcount  = 0;
        bytecount = 0;
        driving   = 1'b0;
        // The mode in force is latched at the start of each transaction, so
        // a WRCR2 that switches protocol takes effect on the *next* command.
        lanes     = in_opi ? 8 : 1;
        dtr       = in_dopi;
        if (!csb) opcode = 8'h00;
    end

    // ── device drives while the clock is low ─────────────────────────
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
                    bitcount  = 0;
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
            if (dtr)      sample_edge;   // both edges in DOPI
            else if (clk) sample_edge;   // rising only otherwise
        end
    end

endmodule
