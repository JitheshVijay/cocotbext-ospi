module ospi_flash #(parameter WIDTH = 8) (
    input wire OSPI_CLK,                 // OSPI serial clock input
    inout wire OSPI_IO0,
    inout wire OSPI_IO1,
    inout wire OSPI_IO2,
    inout wire OSPI_IO3,
    inout wire OSPI_IO4,
    inout wire OSPI_IO5,
    inout wire OSPI_IO6,
    inout wire OSPI_IO7,
    input wire OSPI_CS,                  // Chip select (active low)
    input wire clk,                      // Clock input for internal logic
    input wire reset_n,                  // Active-low reset input
    input wire write_enable,             // Write enable signal
    input wire read_enable,              // Read enable signal
    input wire erase_enable,             // Erase enable signal
    input wire [7:0] data_in,            // Data input for write operation
    input wire [7:0] address,            // Address input for memory access
    output reg [7:0] data_out            // Data output for read operation
);

    // Memory array to store data, 256 bytes in size
    reg [7:0] memory [0:255];
    reg [7:0] data_buffer;  // Buffer to handle bidirectional data lines

    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            data_out <= 8'hFF;  // Initialize data_out to 0xFF on reset
        end else begin
            if (write_enable && !OSPI_CS) begin
                memory[address] <= data_in;    // Write data_in to memory at specified address
            end
            if (read_enable && !OSPI_CS) begin
                data_out <= memory[address];   // Read data from memory at specified address
            end
            if (erase_enable && !OSPI_CS) begin
                memory[address] <= 8'hFF;      // Erase data by writing 0xFF to memory at specified address
            end
        end
    end

    // Assign OSPI data lines based on operation mode
    genvar i;
    generate
        for (i = 0; i < WIDTH; i = i + 1) begin : gen_io
            assign OSPI_IO[i] = (write_enable && !OSPI_CS) ? data_in[i] : 1'bz;
        end
    endgenerate

endmodule

