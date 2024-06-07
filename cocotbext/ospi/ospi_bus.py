import cocotb
from cocotb.handle import SimHandle

class OspiBus:
    def __init__(self, clk, cs, io):
        self.clk = clk      # Serial clock signal
        self.cs = cs        # Chip select signal
        self.io = io        # Data bus

    @classmethod
    def from_prefix(cls, entity: SimHandle, prefix: str):
        # Retrieve signals based on prefix
        clk = getattr(entity, f"{prefix}_CLK")
        cs = getattr(entity, f"{prefix}_CS")
        io = getattr(entity, f"{prefix}_IO")
        return cls(clk, cs, io)


