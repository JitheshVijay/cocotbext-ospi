module clock_generator (
  output reg clk,
  output reg OSPI_CLK
);

initial begin
  clk = 1'b0;
  OSPI_CLK = 1'b0;
  forever #5 clk = ~clk;  
  forever #10 OSPI_CLK = ~OSPI_CLK; 
end

endmodule

module ospi_flash_test;  
  // Signals
  reg OSPI_CLK;
  reg OSPI_CS;
  reg reset_n;
  reg write_enable;
  reg read_enable;
  reg erase_enable;
  wire [7:0] OSPI_IO;
  reg [7:0] data_in;
  reg [23:0] address;
  wire [7:0] data_out;
  wire clk; 
  reg HOLD_N;

  
  // Instantiate clock generator
  clock_generator clk_inst (
    .clk(clk),
    .OSPI_CLK(OSPI_CLK)
  );

  // Instantiate the ospi_flash module
    ospi_flash dut (
        .clk(clk),
        .OSPI_CLK(OSPI_CLK),
        .OSPI_IO(OSPI_IO),
        .OSPI_CS(OSPI_CS),
        .reset_n(reset_n),
        .write_enable(write_enable),
        .read_enable(read_enable),
        .erase_enable(erase_enable),
        .data_in(data_in[7:0]),  
        .address(address),
        .data_out(data_out[7:0]),  
        .HOLD_N(HOLD_N) 
    );

  initial begin
    // Initialize signals
    OSPI_CS = 1;
    reset_n = 0;
    write_enable = 0;
    read_enable = 0;
    erase_enable = 0;
    data_in = 0;
    address = 0;
    HOLD_N = 1;

    // Apply reset
    #10 reset_n = 1;

  end

  initial begin
    $dumpfile("ospi_flash_test.vcd");
    $dumpvars(0, ospi_flash_test);
  end

endmodule

