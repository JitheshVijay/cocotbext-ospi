module ospi_flash(
    input wire clk,
    input wire OSPI_CLK,
    inout wire [7:0] OSPI_IO,
    input wire OSPI_CS,
    input wire reset_n,
    input wire write_enable,
    input wire read_enable,
    input wire erase_enable,
    input wire [7:0] data_in,
    input wire [23:0] address,
    output reg [7:0] data_out,
    input wire HOLD_N,
    input wire [1:0] mode 
);

    // Memory array to store data, 256 bytes in size
    reg [7:0] memory [0:255];
    reg hold_active; // Flag to indicate hold state

    // Bidirectional data handling based on mode
    reg [7:0] ospi_io_out; // Internal register to drive OSPI_IO

    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            data_out <= 8'hFF; // Initialize data_out to 0xFF on reset
            hold_active <= 1'b0; // Initialize hold state to inactive
        end else begin
            if (!HOLD_N) begin
                hold_active <= 1'b1; // Enter hold state when HOLD_N is low
            end else begin
                hold_active <= 1'b0; // Exit hold state when HOLD_N is high
            end

            if (!hold_active) begin
                if (write_enable && !OSPI_CS) begin
                    memory[address] <= data_in; // Write data_in to memory at specified address
                end
                if (read_enable && !OSPI_CS) begin
                    data_out <= memory[address]; // Read data from memory at specified address
                end
                if (erase_enable && !OSPI_CS) begin
                    memory[address] <= 8'hFF; // Erase data by writing 0xFF to memory at specified address
                end
            end
        end
    end

    always @(*) begin
        if (!hold_active && read_enable && !OSPI_CS) begin
            case (mode)
                2'b00: begin // Mode 0: All bits pass through OSPI_IO[0]
                    ospi_io_out = memory[address];
                end

                2'b01: begin // Mode 1: First 4 bits to OSPI_IO[0], last 4 bits to OSPI_IO[1]
                    ospi_io_out[7:4] = memory[address][3:0]; // Swap nibbles
                    ospi_io_out[3:0] = memory[address][7:4];
                end

                2'b10: begin // Mode 2: 2 bits on each OSPI_IO line
                    ospi_io_out[7:6] = memory[address][1:0]; // Swap bit pairs
                    ospi_io_out[5:4] = memory[address][3:2];
                    ospi_io_out[3:2] = memory[address][5:4];
                    ospi_io_out[1:0] = memory[address][7:6];
                end

                2'b11: begin // Mode 3: Each bit on separate OSPI_IO line
                    ospi_io_out = {memory[address][0], memory[address][1], memory[address][2], memory[address][3], memory[address][4], memory[address][5], memory[address][6], memory[address][7]};
                end

                default: begin
                    ospi_io_out = 8'bz;
                end
            endcase
        end else begin
            ospi_io_out = 8'bz;
        end
    end

    // Assign the internal output to the bidirectional bus
    assign OSPI_IO = (OSPI_CS || hold_active) ? 8'bz : ospi_io_out;

endmodule
