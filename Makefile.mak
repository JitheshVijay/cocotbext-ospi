# Makefile for OSPI Cocotb Simulation

# Variables
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES = D:/Manipal/cocotb/ospicocotb/verilog/ospi_flash.v D:/Manipal/cocotb/ospicocotb/verilog/ospi_flash_test.v
TOPLEVEL = ospi_flash_test
MODULE = ospi_flash  # Name of the Python module without .py extension

# SIMULATOR can be changed based on the simulator you are using (e.g., icarus, modelsim, questa, vcs)
SIMULATOR ?= icarus

# Targets
all: $(SIMULATOR)

# Running the simulation with Icarus Verilog
icarus: $(TOPLEVEL).vvp
	# Run the compiled Verilog files with cocotb
	pytest -v $(MODULE).py

# Compile Verilog files with Icarus Verilog
$(TOPLEVEL).vvp: $(VERILOG_SOURCES)
	iverilog -o $(TOPLEVEL).vvp -s $(TOPLEVEL) $(VERILOG_SOURCES)

# Clean up generated files
clean:
	rm -f results.xml *.vvp *.vcd

.PHONY: all clean
