# Third-party reference model

`spiflash.v` is **not** part of this project. It comes from
[PicoSoC](https://github.com/YosysHQ/picorv32) by Claire Xenia Wolf and is
used under the ISC licence reproduced at the top of the file.

It is here so `test_interop.py` can drive a flash model this project did not
write. Tests that only exercise our own `verilog/ospi_flash.v` prove the
driver and the model agree with each other; driving somebody else's model is
what shows the driver speaks real SPI flash protocol.

It is a four-lane part, so it covers the single, dual and quad paths. No
comparable open-source octal model exists, so the eight-lane path is covered
only by our own model.

`firmware.hex` is generated known content that `spiflash.v` loads with
`$readmemh`.
