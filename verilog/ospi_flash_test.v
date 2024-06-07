module ospi_flash_test;
  reg OSPI_CLK;       // OSPI serial clock
  wire [7:0] OSPI_IO;   // OSPI data lines (inout needs to be wire)
  reg OSPI_DS;        // OSPI data strobe
  reg OSPI_CS0_b;      // OSPI chip select 0
  reg OSPI_CS1_b;      // OSPI chip select 1
  reg OSPI_RST_b;      // OSPI reset
  reg reset_n;        // Active-low reset signal
  reg clk;            // Clock signal
  reg write_enable;   // Write enable signal
  reg read_enable;    // Read enable signal
  reg erase_enable;   // Erase enable signal
  reg [7:0] data_in;   // Data input for memory operations
  reg [7:0] address;   // Address input for memory operations
  wire [7:0] data_out; // Data output from memory operations

  // Tri-state buffer for inout port OSPI_IO
  assign OSPI_IO = (write_enable || erase_enable) ? data_in : 8'bz;

  ospi_flash dut (
    .OSPI_CLK(OSPI_CLK),
    .OSPI_IO(OSPI_IO),
    .OSPI_DS(OSPI_DS),
    .OSPI_CS0_b(OSPI_CS0_b),
    .OSPI_CS1_b(OSPI_CS1_b),
    .OSPI_RST_b(OSPI_RST_b),
    .clk(clk),
    .reset_n(reset_n),
    .write_enable(write_enable),
    .read_enable(read_enable),
    .erase_enable(erase_enable),
    .data_in(data_in),
    .address(address),
    .data_out(data_out)
  );

  initial begin
    // Initial values
    OSPI_CLK = 0;
    OSPI_DS = 0;
    OSPI_CS0_b = 1;
    OSPI_CS1_b = 1;
    OSPI_RST_b = 0;
    clk = 0;
    reset_n = 0;
    write_enable = 0;
    read_enable = 0;
    erase_enable = 0;
    data_in = 0;
    address = 0;

    // Reset sequence
    #10 reset_n = 1;
    OSPI_RST_b = 1;

    // Test sequence example
    #20 write_enable = 1;
    data_in = 8'hA5;
    address = 8'h00;
    #10 write_enable = 0;

    #20 read_enable = 1;
    address = 8'h00;
    #10 read_enable = 0;

    // Wait some time and finish
    #100 $finish;
  end

  always #5 clk = ~clk;

  // Generate OSPI clock
  always #10 OSPI_CLK = ~OSPI_CLK;

  // Display values during simulation
  always @(posedge clk) begin
    if (write_enable) $display("Writing data: %h to address: %h", data_in, address);
    if (read_enable) $display("Reading data: %h from address: %h", data_out, address);
  end

endmodule
