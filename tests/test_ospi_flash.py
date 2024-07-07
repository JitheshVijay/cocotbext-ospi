import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotbext.ospi.ospi_flash import OspiFlash

@cocotb.test()
async def test_ospi_flash_fast_read(dut):
    ospi = OspiFlash(dut)
    await ospi.initialize()

    # Fast read data in single mode
    address = 0x01
    await ospi.write(address, [0xA5], mode=0)
    read_data = await ospi.fast_read(address, mode=0)
    assert read_data == [0xA5], f"Fast read data {read_data} does not match written data [0xA5] in single mode"

    # Fast read data in dual mode
    await ospi.write(address, [0xA6], mode=1)
    read_data = await ospi.fast_read(address, mode=1)
    assert read_data == [0xA6], f"Fast read data {read_data} does not match written data [0xA6] in dual mode"

    # Fast read data in quad mode
    await ospi.write(address, [0xA7], mode=2)
    read_data = await ospi.fast_read(address, mode=2)
    assert read_data == [0xA7], f"Fast read data {read_data} does not match written data [0xA7] in quad mode"

    # Fast read data in octal mode
    await ospi.write(address, [0xA8], mode=3)
    read_data = await ospi.fast_read(address, mode=3)
    assert read_data == [0xA8], f"Fast read data {read_data} does not match written data [0xA8] in octal mode"

@cocotb.test()
async def test_ospi_flash_io_operations(dut):
    ospi = OspiFlash(dut)
    await ospi.initialize()

    # I/O operation in single mode
    address = 0x02
    await ospi.write(address, [0xB5], mode=0)
    read_data = await ospi.read(address, mode=0)
    assert read_data == [0xB5], f"Read data {read_data} does not match written data [0xB5] in single mode"

    # I/O operation in dual mode
    await ospi.write(address, [0xB6], mode=1)
    read_data = await ospi.read(address, mode=1)
    assert read_data == [0xB6], f"Read data {read_data} does not match written data [0xB6] in dual mode"

    # I/O operation in quad mode
    await ospi.write(address, [0xB7], mode=2)
    read_data = await ospi.read(address, mode=2)
    assert read_data == [0xB7], f"Read data {read_data} does not match written data [0xB7] in quad mode"

    # I/O operation in octal mode
    await ospi.write(address, [0xB8], mode=3)
    read_data = await ospi.read(address, mode=3)
    assert read_data == [0xB8], f"Read data {read_data} does not match written data [0xB8] in octal mode"

@cocotb.test()
async def test_ospi_flash_hold_operations(dut):
    ospi = OspiFlash(dut)
    await ospi.initialize()

    # Perform hold operation
    address = 0x03
    await ospi.write(address, [0xC5], mode=0)
    await ospi.hold_operation()
    read_data = await ospi.read(address, mode=0)
    assert read_data == [0xC5], f"Read data {read_data} does not match written data [0xC5] after hold operation"

    # Release from hold and perform another operation
    await ospi.release_hold()
    await ospi.write(address, [0xC6], mode=1)
    read_data = await ospi.read(address, mode=1)
    assert read_data == [0xC6], f"Read data {read_data} does not match written data [0xC6] after releasing hold"


