class OspiConfig:
    def __init__(self, word_width, sclk_freq, cpol, cpha, cs_active_low, bus_width='octal'):
        self.word_width = word_width  # Data width in bits
        self.sclk_freq = sclk_freq    # Serial clock frequency
        self.cpol = cpol              # Clock polarity
        self.cpha = cpha              # Clock phase
        self.cs_active_low = cs_active_low  # Chip select active low flag
        self.bus_width = bus_width    # Bus width: 'single', 'dual', 'quad', 'octal'

    def __str__(self):
        return (f'OspiConfig(word_width={self.word_width}, sclk_freq={self.sclk_freq}, '
                f'cpol={self.cpol}, cpha={self.cpha}, cs_active_low={self.cs_active_low}, '
                f'bus_width={self.bus_width})')
