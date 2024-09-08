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
    input wire HOLD_N


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


    // OSPI_IO Assignment (for bidirectional data handling)
    assign OSPI_IO = (!hold_active && read_enable && !OSPI_CS) ? memory[address] : 8'bz;

endmodule


