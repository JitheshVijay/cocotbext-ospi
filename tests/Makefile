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
TOPLEVEL = $(DUT)
MODULE   = test_ospi_flash

# Verilog source files
VERILOG_SOURCES = $(shell pwd)/../verilog/ospi_flash.v $(shell pwd)/../verilog/ospi_flash_test.v

# Enable waveform dumping
ifeq ($(SIM), icarus)
	PLUSARGS += -fst

	ifeq ($(WAVES), 1)
		VERILOG_SOURCES += iverilog_dump.v
		COMPILE_ARGS += -s iverilog_dump
	endif
endif

# Include the cocotb makefile
include $(shell cocotb-config --makefiles)/Makefile.sim

# Generate the iverilog dump file for waveform output
iverilog_dump.v:
	echo 'module iverilog_dump();' > $@
	echo 'initial begin' >> $@
	echo '    $$dumpfile("$(TOPLEVEL).fst");' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL));' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_CLK);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_CS);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO0);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO1);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO2);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO3);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO4);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO5);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO6);' >> $@
	echo '    $$dumpvars(0, $(TOPLEVEL).OSPI_IO7);' >> $@
	echo 'end' >> $@
	echo 'endmodule' >> $@

# Clean target to remove generated files
clean::
	@rm -rf iverilog_dump.v
	@rm -rf dump.fst $(TOPLEVEL).fst
	@rm -rf results.xml
	@rm -rf sim_build

.PHONY: all sim clean
