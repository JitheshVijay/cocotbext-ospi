# Makefile for running Cocotb tests with Icarus Verilog

# Language and simulator settings
TOPLEVEL_LANG ?= verilog
SIM ?= icarus

# Name of the module to be tested
MODULE := test_ospi_flash

# Verilog source files
VERILOG_SOURCES = $(shell pwd)/verilog/ospi_flash.v $(shell pwd)/verilog/ospi_flash_test.v

# Top-level module name
TOPLEVEL := ospi_flash

# Enable VCD dumping
export COCOTB_REDUCED_LOG_FMT=1
export WAVES=1

# Paths to Cocotb makefiles
COCOTB_MAKEFILES := $(shell cocotb-config --makefiles)
COCOTB_VPI ?= $(shell cocotb-config --lib)

# Default target to run the simulation
all: sim

# Simulation target
sim:
	$(MAKE) -C $(COCOTB_MAKEFILES) SIM=$(SIM) TOPLEVEL=$(TOPLEVEL) MODULE=$(MODULE) \
	    TOPLEVEL_LANG=$(TOPLEVEL_LANG) VERILOG_SOURCES="$(VERILOG_SOURCES)"

# Clean target to remove generated files
clean:
	rm -f sim_build/* waves.vcd

.PHONY: all sim clean
