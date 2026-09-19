"""OSPI flash verification for cocotb."""

from pathlib import Path


def verilog_dir() -> Path:
    """Directory holding this package's Verilog models.

    The models ship inside the package, so a testbench can point at them
    without vendoring a copy:

        VERILOG_DIR := $(shell python3 -c \
            "import cocotbext.ospi as o; print(o.verilog_dir())")
        VERILOG_SOURCES = $(VERILOG_DIR)/devices/mx25um51345g.v

    Subdirectories: ``devices/`` for the part models and their generated
    SFDP includes, ``controller/`` for the example controller DUT.
    """
    return Path(__file__).parent / "verilog"


from .ospi_bus import OspiBus
from .ospi_config import OspiConfig, lanes_for_mode
from .ospi_flash import (
    OspiFlash,
    CMD_READ, CMD_DIOR, CMD_QIOR, CMD_OIOR,
    CMD_WREN, CMD_WRDI, CMD_RDSR, CMD_RDID, CMD_PP, CMD_SE,
    STATUS_WIP, STATUS_WEL, READ_LANES,
)
from .ospi_master import OspiMaster
from .sfdp import build_sfdp, build_bfpt, parse_sfdp, SfdpInfo, SfdpError
from .xspi_flash import XspiFlash

__all__ = [
    "OspiBus", "OspiConfig", "OspiFlash", "OspiMaster", "lanes_for_mode",
    "CMD_READ", "CMD_DIOR", "CMD_QIOR", "CMD_OIOR",
    "CMD_WREN", "CMD_WRDI", "CMD_RDSR", "CMD_RDID", "CMD_PP", "CMD_SE",
    "STATUS_WIP", "STATUS_WEL", "READ_LANES",
    "XspiFlash",
    "build_sfdp", "build_bfpt", "parse_sfdp", "SfdpInfo", "SfdpError",
]
