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
    output reg [7:0] data_out,           // Data output for read operation
    input wire HOLD_N                    // Hold signal (active low)
);

    // Memory array to store data, 256 bytes in size
    reg [7:0] memory [0:255];
    reg hold_active;        // Flag to indicate hold state

    always @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            data_out <= 8'hFF;  // Initialize data_out to 0xFF on reset
            hold_active <= 1'b0; // Initialize hold state to inactive
        end else begin
            if (!HOLD_N) begin
                hold_active <= 1'b1; // Enter hold state when HOLD_N is low
            end else begin
                hold_active <= 1'b0; // Exit hold state when HOLD_N is high
            end
            
            if (!hold_active) begin
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
    end

    // Assign OSPI data lines based on operation mode
    assign OSPI_IO0 = (write_enable && !OSPI_CS && !hold_active) ? data_in[0] : 1'bz;
    assign OSPI_IO1 = (write_enable && !OSPI_CS && !hold_active) ? data_in[1] : 1'bz;
    assign OSPI_IO2 = (write_enable && !OSPI_CS && !hold_active) ? data_in[2] : 1'bz;
    assign OSPI_IO3 = (write_enable && !OSPI_CS && !hold_active) ? data_in[3] : 1'bz;
    assign OSPI_IO4 = (write_enable && !OSPI_CS && !hold_active) ? data_in[4] : 1'bz;
    assign OSPI_IO5 = (write_enable && !OSPI_CS && !hold_active) ? data_in[5] : 1'bz;
    assign OSPI_IO6 = (write_enable && !OSPI_CS && !hold_active) ? data_in[6] : 1'bz;
    assign OSPI_IO7 = (write_enable && !OSPI_CS && !hold_active) ? data_in[7] : 1'bz;

endmodule
