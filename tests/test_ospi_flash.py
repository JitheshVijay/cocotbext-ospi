import cocotb
from cocotb.triggers import Timer
from cocotbext.ospi.ospi_flash import OspiFlash

@cocotb.test()
async def test_ospi_flash_write_read(dut):
    print("Starting test_ospi_flash_write_read")
    ospi = OspiFlash(dut)
    await ospi.initialize()

    address = 0x01
    data_to_write = 0xA5
    await ospi.write(address, data_to_write)
    await Timer(10, units='ns')

    read_data = await ospi.read(address)
    print(f"Written data: {data_to_write}, Read data: {read_data}")
    assert read_data == data_to_write, f"Data mismatch: {read_data} != {data_to_write}"

@cocotb.test()
async def test_ospi_flash_erase(dut):
    print("Starting test_ospi_flash_erase")
    ospi = OspiFlash(dut)
    await ospi.initialize()

    address = 0x01
    data_to_write = 0x5A
    await ospi.write(address, data_to_write)
    await Timer(10, units='ns')

    await ospi.erase(address)
    await Timer(10, units='ns')

    read_data = await ospi.read(address)
    print(f"Data after erase: {read_data}")
    assert read_data == 0xFF, f"Data after erase mismatch: {read_data} != 0xFF"


