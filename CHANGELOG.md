# Changelog

## 0.2.0

First public release.

OSPI flash verification for cocotb, including real device models built from
datasheets: single, dual, quad and octal I/O, at single and double transfer
rate.

- `XspiFlash` — driven by a `DeviceProfile` describing an actual part, so
  adding a device is a table rather than a fork.
- **Macronix MX25UM51345G** (1S-1S-1S, 8S-8S-8S, 8D-8D-8D) — CR2 mode
  switching, inverted command extension, configurable dummy cycles, security
  register, advanced sector protection, program/erase suspend, DQS.
- **Micron MT35XU512ABA** (1S-1S-1S, 8D-8D-8D) — CFR0V/CFR1V mode switching,
  repeated command extension, flag status register.
- SFDP: BFPT, xSPI Profile 1.0 (JESD251) and the 4-byte Address Instruction
  Table, built and parsed. `configure_from_sfdp()` sets the driver up from
  what a part advertises rather than from its profile.
- `xspi_controller` — an example controller as DUT, so the RTL is under test
  rather than the driver.
- The models ship inside the package; `verilog_dir()` locates them.
- Requires cocotb 2.0+.

Five test suites: a generic model, interop against
[PicoSoC's `spiflash.v`](https://github.com/YosysHQ/picorv32) which this
project did not write, the two device models, and the controller.

Where a behaviour is a modelling choice rather than something a datasheet
documents, the model and its tests say so — rejecting a mismatched command
extension, and DQS after the end of a burst, are both marked.

Earlier revisions of this code existed but were never usable: the RTL,
driver and tests disagreed with each other and nothing had run. 0.2.0 is the
first version that works.


## Releasing

Two stages, so a release can be rehearsed before it is permanent:

1. `git tag v0.2.0 && git push --tags` — builds, runs the gates, publishes
   to [TestPyPI](https://test.pypi.org). Nothing reaches the real index.
2. Check the TestPyPI page renders and the package installs from it.
3. Create a GitHub Release for that tag — publishes to PyPI.

Both stages authenticate with Trusted Publishing, so no API token exists.
Register a publisher on each index first; the workflow header lists the
exact fields.

A version number can never be reused on either index.
