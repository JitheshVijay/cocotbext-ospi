import cocotb
from cocotb.handle import SimHandle

class OspiBus:
    def __init__(self, clk, cs, io0, io1, io2, io3, io4, io5, io6, io7):
        self.clk = clk      # Serial clock signal
        self.cs = cs        # Chip select signal
        self.io0 = io0      # Data line 0
        self.io1 = io1      # Data line 1
        self.io2 = io2      # Data line 2
        self.io3 = io3      # Data line 3
        self.io4 = io4      # Data line 4
        self.io5 = io5      # Data line 5
        self.io6 = io6      # Data line 6
        self.io7 = io7      # Data line 7

    @classmethod
    def from_prefix(cls, entity: SimHandle, prefix: str):
        # Retrieve signals based on prefix
        clk = getattr(entity, f"{prefix}_CLK")
        cs = getattr(entity, f"{prefix}_CS")
        io0 = getattr(entity, f"{prefix}_IO0")
        io1 = getattr(entity, f"{prefix}_IO1")
        io2 = getattr(entity, f"{prefix}_IO2")
        io3 = getattr(entity, f"{prefix}_IO3")
        io4 = getattr(entity, f"{prefix}_IO4")
        io5 = getattr(entity, f"{prefix}_IO5")
        io6 = getattr(entity, f"{prefix}_IO6")
        io7 = getattr(entity, f"{prefix}_IO7")
        return cls(clk, cs, io0, io1, io2, io3, io4, io5, io6, io7)

