import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

IDLE     = 0b00
WARN     = 0b01
FAULT    = 0b10
SHUTDOWN = 0b11

def pack_inputs(voltage=8, current=0, temp=0, safe_reset=0):
    return ((voltage & 0xF) |
            ((current & 0x3) << 4) |
            ((temp & 0x1) << 6) |
            ((safe_reset & 0x1) << 7))

def get_state(dut):      return (int(dut.uo_out.value) >> 3) & 0x3
def get_soc(dut):        return (int(dut.uo_out.value) >> 5) & 0x3
def get_fault(dut):      return (int(dut.uo_out.value) >> 0) & 0x1
def get_shutdown(dut):   return (int(dut.uo_out.value) >> 1) & 0x1
def get_thermal(dut):    return (int(dut.uo_out.value) >> 2) & 0x1
def get_overcurrent(dut):return (int(dut.uo_out.value) >> 7) & 0x1

async def do_reset(dut):
    dut.ena.value    = 1
    dut.ui_in.value  = 0
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

@cocotb.test()
async def test_01_reset(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    assert get_state(dut)      == IDLE
    assert get_fault(dut)      == 0
    assert get_shutdown(dut)   == 0
    assert get_thermal(dut)    == 0
    assert get_overcurrent(dut)== 0

@cocotb.test()
async def test_02_idle_normal(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 3)

    assert get_state(dut) == IDLE
    assert get_fault(dut) == 0
    assert get_soc(dut)   == 0b10

@cocotb.test()
async def test_03_idle_to_warn_voltage(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=2, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut)    == WARN
    assert get_fault(dut)    == 1
    assert get_shutdown(dut) == 0

@cocotb.test()
async def test_04_idle_to_warn_current(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=8, current=1, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut)      == WARN
    assert get_overcurrent(dut)== 0

@cocotb.test()
async def test_05_warn_hysteresis_recovery(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=2, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == WARN

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=0)

    for _ in range(7):
        await ClockCycles(dut.clk, 1)
        assert get_state(dut) == WARN

    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == IDLE

@cocotb.test()
async def test_06_direct_idle_to_fault(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=1, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut) == FAULT
    assert get_fault(dut) == 1
    assert get_soc(dut)   == 0b00

@cocotb.test()
async def test_07_sticky_fault_latch(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=0, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=0)

    for _ in range(5):
        await ClockCycles(dut.clk, 1)
        assert get_state(dut) == FAULT

@cocotb.test()
async def test_08_fault_cleared_by_safe_reset(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=0, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=1)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut) == IDLE
    assert get_fault(dut) == 0

@cocotb.test()
async def test_09_overcurrent_fault(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    for level in [2, 3]:
        await do_reset(dut)
        dut.ui_in.value = pack_inputs(voltage=8, current=level, temp=0, safe_reset=0)
        await ClockCycles(dut.clk, 1)

        assert get_state(dut)      == FAULT
        assert get_overcurrent(dut)== 1

@cocotb.test()
async def test_10_thermal_latch_sticky(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=1, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)
    assert get_thermal(dut) == 1

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=1)
    await ClockCycles(dut.clk, 2)
    assert get_state(dut) == IDLE

@cocotb.test()
async def test_11_watchdog_escalation(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=0, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    await ClockCycles(dut.clk, 14)
    assert get_state(dut)    == FAULT
    assert get_shutdown(dut) == 0

    await ClockCycles(dut.clk, 2)
    assert get_state(dut)    == SHUTDOWN
    assert get_shutdown(dut) == 1

@cocotb.test()
async def test_12_soc_all_levels(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    test_cases = [
        (0,  0b00),
        (1,  0b00),
        (2,  0b01),
        (4,  0b01),
        (5,  0b10),
        (10, 0b10),
        (11, 0b11),
        (15, 0b11),
    ]

    for voltage, expected_soc in test_cases:
        await do_reset(dut)
        dut.ui_in.value = pack_inputs(voltage=voltage)
        await ClockCycles(dut.clk, 1)
        assert get_soc(dut) == expected_soc

@cocotb.test()
async def test_13_shutdown_recovery(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=0, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 17)

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=1)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut)    == IDLE
    assert get_shutdown(dut) == 0

@cocotb.test()
async def test_14_warn_to_fault_mid_recovery(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)

    dut.ui_in.value = pack_inputs(voltage=2, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    dut.ui_in.value = pack_inputs(voltage=8, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 3)

    dut.ui_in.value = pack_inputs(voltage=0, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut) == FAULT

@cocotb.test()
async def test_15_overvoltage(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=15, current=0, temp=0, safe_reset=0)
    await ClockCycles(dut.clk, 1)

    assert get_state(dut) == FAULT
    assert get_soc(dut)   == 0b11
