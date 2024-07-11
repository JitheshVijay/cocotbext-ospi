module ospi_flash_test;
  parameter WIDTH = 8;
  reg OSPI_CLK;              // OSPI serial clock
  reg OSPI_CS;               // OSPI chip select
  reg reset_n;               // Active-low reset signal
  reg clk;                   // Clock signal
  reg [WIDTH-1:0] address;   // Address for memory access

  // Instantiate the ospi_flash module
  ospi_flash #(.WIDTH(WIDTH)) dut (
      .OSPI_CLK(OSPI_CLK),
      .OSPI_CS(OSPI_CS),
      .reset_n(reset_n),
      .address(address)
  );

  initial begin
      $dumpfile("ospi_flash_test.vcd");
      $dumpvars(0, ospi_flash_test);

      // Initialize signals
      OSPI_CLK = 0;
      OSPI_CS = 1;
      reset_n = 0;
      clk = 0;
      address = 0;

      // Apply reset
      #5 reset_n = 1;
      #10 reset_n = 0;
      #5 reset_n = 1;

      // End simulation
      #100 $finish;
  end

  // Clock generation
  always #5 clk = ~clk;
  always #5 OSPI_CLK = ~OSPI_CLK;

endmodule

