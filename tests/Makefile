# Makefile for running Cocotb tests with Icarus Verilog

# Language and simulator settings
TOPLEVEL_LANG ?= verilog
SIM ?= icarus
WAVES ?= 1

# Time unit and precision
COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

# Name of the top-level module and the test module
DUT      = ospi_flash
TOPLEVEL = ospi_flash_test
MODULE   = test_ospi_flash

# Verilog source files
VERILOG_SOURCES = $(shell pwd)/../verilog/ospi_flash.v 
VERILOG_SOURCES += $(shell pwd)/../verilog/ospi_flash_test.v

# Enable waveform dumping
ifeq ($(SIM), icarus)
	PLUSARGS += -fst

	ifeq ($(WAVES), 1)
		VERILOG_SOURCES += iverilog_dump.v
		COMPILE_ARGS += -s iverilog_dump
	endif
endif

# Set the PYTHONPATH to include the directory containing the OspiFlash module and the tests directory
export PYTHONPATH := $(shell pwd)/..:$(shell pwd):$(PYTHONPATH)
export COCOTB_HDL_TIMEUNIT
export COCOTB_HDL_TIMEPRECISION

# Include the cocotb makefile
include $(shell cocotb-config --makefiles)/Makefile.sim

# Generate the iverilog dump file for waveform output
iverilog_dump.v:
	echo 'module iverilog_dump();' > iverilog_dump.v
	echo 'initial begin' >> iverilog_dump.v
	echo '    $$dumpfile("sim_build/ospi_flash_test.fst");' >> iverilog_dump.v
	echo '    $$dumpvars(0, ospi_flash_test.clk);' >> iverilog_dump.v
	echo '    $$dumpvars(0, ospi_flash_test.OSPI_CS);' >> iverilog_dump.v
	echo '    $$dumpvars(0, ospi_flash_test.OSPI_IO);' >> iverilog_dump.v 
	echo '    $$dumpvars(0, ospi_flash_test.data_in);' >> iverilog_dump.v
	echo '    $$dumpvars(0, ospi_flash_test.address);' >> iverilog_dump.v
	echo 'end' >> iverilog_dump.v
	echo 'endmodule' >> iverilog_dump.v

# Clean target to remove generated files
clean::
	@rm -rf iverilog_dump.v
	@rm -rf dump.fst $(TOPLEVEL).fst
	@rm -rf results.xml
	@rm -rf sim_build

.PHONY: all sim clean



