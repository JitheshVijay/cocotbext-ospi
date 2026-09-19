"""Configuration for an OSPI transfer."""

# mode -> number of OSPI_IO lines carrying data at once
LANES_FOR_MODE = {0: 1, 1: 2, 2: 4, 3: 8}

MODE_NAMES = {0: "single", 1: "dual", 2: "quad", 3: "octal"}


def lanes_for_mode(mode: int) -> int:
    """Data lines active in ``mode``."""
    try:
        return LANES_FOR_MODE[mode]
    except KeyError:
        raise ValueError(
            f"Unsupported mode {mode!r}; expected 0 (single), 1 (dual), "
            f"2 (quad) or 3 (octal)"
        ) from None


class OspiConfig:
    def __init__(self, mode=0, word_width=8, sclk_freq=1e6, cpol=False,
                 cpha=False, cs_active_low=True):
        self.mode = mode
        self.word_width = word_width
        self.sclk_freq = sclk_freq
        self.cpol = cpol
        self.cpha = cpha
        self.cs_active_low = cs_active_low

    @property
    def lanes(self) -> int:
        return lanes_for_mode(self.mode)

    def __str__(self):
        return (f"OspiConfig(mode={self.mode} ({MODE_NAMES[self.mode]}), "
                f"lanes={self.lanes}, word_width={self.word_width}, "
                f"sclk_freq={self.sclk_freq}, cs_active_low={self.cs_active_low})")
