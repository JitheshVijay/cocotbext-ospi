module ospi_flash_test;
  parameter WIDTH = 8;
  reg OSPI_CLK;          // OSPI serial clock
  wire [WIDTH-1:0] OSPI_IO;  // OSPI data lines (inout needs to be wire)
  reg OSPI_CS;           // OSPI chip select
  reg reset_n;           // Active-low reset signal
  reg clk;               // Clock signal
  reg write_enable;      // Write enable signal
  reg read_enable;       // Read enable signal
  reg erase_enable;      // Erase enable signal
  reg [WIDTH-1:0] data_in;   // Data input for write operations
  reg [WIDTH-1:0] address;   // Address for memory access
  wire [WIDTH-1:0] data_out; // Data output for read operations

  ospi_flash #(.WIDTH(WIDTH)) dut (
      .OSPI_CLK(OSPI_CLK),
      .OSPI_IO(OSPI_IO),
      .OSPI_CS(OSPI_CS),
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
      $dumpfile("ospi_flash_test.vcd");
      $dumpvars(0, ospi_flash_test);

      // Initialize signals
      OSPI_CLK = 0;
      OSPI_CS = 1;
      reset_n = 0;
      clk = 0;
      write_enable = 0;
      read_enable = 0;
      erase_enable = 0;
      data_in = 0;
      address = 0;

      // Apply reset
      #5 reset_n = 1;

  end

  // Clock generation
  always #5 clk = ~clk;
  always #5 OSPI_CLK = ~OSPI_CLK;

endmodule


endmodule


