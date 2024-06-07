# Makefile for OSPI Cocotb Simulation

# Variables
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES = $(wildcard /mnt/d/Manipal/cocotb/ospicocotb/verilog/*.v)
TOPLEVEL = ospi_flash_test
MODULE = ospi_flash

# SIMULATOR can be changed based on the simulator you are using (e.g., icarus, modelsim, questa, vcs)
SIMULATOR ?= icarus

# Targets
all: $(SIMULATOR)

# Running the simulation with Icarus Verilog
icarus: $(TOPLEVEL).vvp
	# Run the compiled Verilog files
	vvp -n $(TOPLEVEL).vvp

# Compile Verilog files with Icarus Verilog
$(TOPLEVEL).vvp: $(VERILOG_SOURCES)
	iverilog -o $(TOPLEVEL).vvp -s $(TOPLEVEL) $(VERILOG_SOURCES)

# Clean up generated files
clean:
	rm -f results.xml *.vvp *.vcd

.PHONY: all clean

