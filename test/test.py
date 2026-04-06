import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

IDLE     = 0b00
WARN     = 0b01
FAULT    = 0b10
SHUTDOWN = 0b11

def pack_inputs(voltage=8, current=0, temp=0, safe_reset=0):
    return ((voltage & 0xF) |
            ((current & 0x3) << 4) |
            ((temp    & 0x1) << 6) |
            ((safe_reset & 0x1) << 7))

def get_state(dut):       return (int(dut.uo_out.value) >> 3) & 0x3
def get_soc(dut):         return (int(dut.uo_out.value) >> 5) & 0x3
def get_fault(dut):       return (int(dut.uo_out.value) >> 0) & 0x1
def get_shutdown(dut):    return (int(dut.uo_out.value) >> 1) & 0x1
def get_thermal(dut):     return (int(dut.uo_out.value) >> 2) & 0x1
def get_overcurrent(dut): return (int(dut.uo_out.value) >> 7) & 0x1

async def do_reset(dut):
    # Clock period in tb.v is 100ns (10 MHz), use same here
    cocotb.start_soon(Clock(dut.clk, 100, unit="ns").start())
    dut.ena.value    = 1
    dut.ui_in.value  = 0
    dut.uio_in.value = 0
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 2)

@cocotb.test()
async def test_01_reset(dut):
    await do_reset(dut)
    assert get_state(dut)       == IDLE, f"Expected IDLE after reset, got {get_state(dut)}"
    assert get_fault(dut)       == 0
    assert get_shutdown(dut)    == 0
    assert get_thermal(dut)     == 0
    assert get_overcurrent(dut) == 0

@cocotb.test()
async def test_02_idle_normal(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=8)
    await ClockCycles(dut.clk, 3)
    assert get_state(dut) == IDLE,   f"Expected IDLE, got {get_state(dut)}"
    assert get_fault(dut) == 0
    assert get_soc(dut)   == 0b10,   f"Expected SOC=2, got {get_soc(dut)}"

@cocotb.test()
async def test_03_idle_to_warn_voltage(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=2)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut)    == WARN,  f"Expected WARN, got {get_state(dut)}"
    assert get_fault(dut)    == 1
    assert get_shutdown(dut) == 0

@cocotb.test()
async def test_04_idle_to_warn_current(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=8, current=1)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut)       == WARN, f"Expected WARN, got {get_state(dut)}"
    assert get_overcurrent(dut) == 0

@cocotb.test()
async def test_05_warn_hysteresis_recovery(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=2)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == WARN

    dut.ui_in.value = pack_inputs(voltage=8)
    for i in range(7):
        await ClockCycles(dut.clk, 1)
        assert get_state(dut) == WARN, f"Should stay in WARN during hysteresis (cycle {i+1})"

    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == IDLE, f"Expected IDLE after hysteresis, got {get_state(dut)}"

@cocotb.test()
async def test_06_direct_idle_to_fault(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=1)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT, f"Expected FAULT, got {get_state(dut)}"
    assert get_fault(dut) == 1
    assert get_soc(dut)   == 0b00

@cocotb.test()
async def test_07_sticky_fault_latch(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=0)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT

    dut.ui_in.value = pack_inputs(voltage=8)
    for i in range(5):
        await ClockCycles(dut.clk, 1)
        assert get_state(dut) == FAULT, f"Fault should be sticky (cycle {i+1})"

@cocotb.test()
async def test_08_fault_cleared_by_safe_reset(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=0)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT

    dut.ui_in.value = pack_inputs(voltage=8, safe_reset=1)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == IDLE,  f"Expected IDLE after safe_reset, got {get_state(dut)}"
    assert get_fault(dut) == 0

@cocotb.test()
async def test_09_overcurrent_fault(dut):
    for level in [2, 3]:
        await do_reset(dut)
        dut.ui_in.value = pack_inputs(voltage=8, current=level)
        await ClockCycles(dut.clk, 1)
        assert get_state(dut)       == FAULT, f"current={level}: expected FAULT, got {get_state(dut)}"
        assert get_overcurrent(dut) == 1

@cocotb.test()
async def test_10_thermal_latch_sticky(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=8, temp=1)
    await ClockCycles(dut.clk, 1)

    dut.ui_in.value = pack_inputs(voltage=8, temp=0)
    await ClockCycles(dut.clk, 1)
    assert get_thermal(dut) == 1, "Thermal latch should stay set after temp goes low"

    dut.ui_in.value = pack_inputs(voltage=8, temp=0, safe_reset=1)
    await ClockCycles(dut.clk, 2)
    assert get_state(dut) == IDLE, f"Expected IDLE after thermal+safe_reset, got {get_state(dut)}"

@cocotb.test()
async def test_11_watchdog_escalation(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=0)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT

    await ClockCycles(dut.clk, 14)
    assert get_state(dut)    == FAULT,    f"Should still be FAULT at cycle 14"
    assert get_shutdown(dut) == 0

    await ClockCycles(dut.clk, 2)
    assert get_state(dut)    == SHUTDOWN, f"Expected SHUTDOWN after watchdog, got {get_state(dut)}"
    assert get_shutdown(dut) == 1

@cocotb.test()
async def test_12_soc_all_levels(dut):
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
        assert get_soc(dut) == expected_soc, f"voltage={voltage}: expected SOC={expected_soc}, got {get_soc(dut)}"

@cocotb.test()
async def test_13_shutdown_recovery(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=0)
    await ClockCycles(dut.clk, 17)
    assert get_state(dut) == SHUTDOWN

    dut.ui_in.value = pack_inputs(voltage=8, safe_reset=1)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut)    == IDLE, f"Expected IDLE after shutdown recovery, got {get_state(dut)}"
    assert get_shutdown(dut) == 0

@cocotb.test()
async def test_14_warn_to_fault_mid_recovery(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=2)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == WARN

    dut.ui_in.value = pack_inputs(voltage=8)
    await ClockCycles(dut.clk, 3)

    dut.ui_in.value = pack_inputs(voltage=0)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT, f"Expected FAULT, got {get_state(dut)}"

@cocotb.test()
async def test_15_overvoltage(dut):
    await do_reset(dut)
    dut.ui_in.value = pack_inputs(voltage=15)
    await ClockCycles(dut.clk, 1)
    assert get_state(dut) == FAULT, f"Expected FAULT on overvoltage, got {get_state(dut)}"
    assert get_soc(dut)   == 0b11
