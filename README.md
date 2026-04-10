

![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)
# Medical Device Battery Monitoring and Safety Controller

## Objective : Safety-Critical Power Management
This project implements a high-reliability digital Battery Management System (BMS) specifically engineered for **life-critical medical devices** such as pacemakers, insulin pumps, and portable life-support monitors. 

Unlike standard power controllers, this system prioritizes **fail-safe operation** and strict safety compliance. A central design pillar is the **"Sticky Fault Latch"** mechanism: a safety feature that prevents automatic recovery after a critical error. If a hazard like overheating or overcurrent occurs, the system locks into a fault state that must be explicitly cleared by a human operator, ensuring the device is inspected before resuming patient care.

## Core Features
*   **Deterministic Logic:** Built as a pure hardware controller to ensure predictable behavior under all fault conditions.
*   **Safety Compliance:** The architecture aligns with **IEC 60601-1** standards, focusing on controlled fault handling and the prevention of unsafe automatic restarts.
*   **Intelligent Monitoring:** Real-time analysis of voltage, current, and thermal telemetry across 15 distinct safety scenarios.
*   **Resilient Design:** Integrated hysteresis-based recovery to filter signal noise and a watchdog timer to prevent unattended system failures.

---

## Hardware Interface
The controller is designed for the Tiny Tapeout platform (Module: `tt_um_AnjaniKad_medical_bms`), utilizing a 10MHz clock to process 8-bit digital inputs and drive 8-bit safety status outputs.

### System Inputs (8-Bit Bus)
| Signal | Bit(s) | Function |
| :--- | :---: | :--- |
| **Voltage** | 0-3 | 4-bit digitized battery voltage (0–15 scale) |
| **Current** | 4-5 | 2-bit load current level monitoring |
| **Temp Flag** | 6 | External sensor input for over-temperature detection |
| **Safe Reset** | 7 | Manual human-triggered signal to clear latched faults |

### System Outputs (8-Bit Bus)
| Signal | Bit(s) | Function |
| :--- | :---: | :--- |
| **General Fault** | 0 | Master indicator that the system is in an unsafe state |
| **Shutdown** | 1 | Hardware-level trigger to disable the medical device |
| **Thermal Alarm**| 2 | "Sticky" flag indicating a past or current thermal violation |
| **FSM State** | 3-4 | Real-time reporting of the current Safety State |
| **SOC** | 5-6 | 2-bit Battery State-of-Charge (Critical to Full) |
| **Overcurrent** | 7 | Dedicated indicator for critical current breaches |

---

## Internal Architecture & Functional Blocks
The system is partitioned into seven specialized logic modules that operate in parallel for maximum reliability:

1.  **Voltage & SOC Engine:** Categorizes battery voltage into five safety regions and provides 4-level State-of-Charge telemetry.
2.  **Current Monitor:** Provides microsecond-response detection for current surges, bypassing warnings to trigger immediate fault states if thresholds are breached.
3.  **Thermal Guard:** A specialized safety latch that captures overheating events. It remains active even if the temperature returns to normal until a manual reset is provided.
4.  **Hysteresis Counter:** A safety-debounce block that requires **8 consecutive safe clock cycles** before allowing the system to transition from a Warning state back to Idle.
5.  **Watchdog Timer:** Monitors fault duration; if a critical error persists for **16 cycles**, the system automatically escalates to a full hardware **SHUTDOWN**.
6.  **Safety Finite State Machine (FSM):** The central logic core managing transitions between **IDLE, WARN, FAULT, and SHUTDOWN** states based on a prioritized safety matrix.

---

## Resource Utilization & Gate Count
The design is highly optimized for ASIC manufacturing, maximizing safety logic while maintaining a compact hardware footprint. 

| Functional Block | Estimated Gate Count |
| :--- | :--- |
| **Voltage & SOC Logic** | ~135 Gates |
| **Safety FSM** | ~95 Gates |
| **Watchdog Timer (4-bit)** | ~55 Gates |
| **Hysteresis Counter (3-bit)** | ~45 Gates |
| **Thermal & Current Logic** | ~30 Gates |
| **Interface & Glue Logic** | ~90 Gates |
| **Total Complexity** | **~450–550 Gates** |

---

## Verification & Testing
The controller has been rigorously validated through both Verilog and Python (Cocotb) testbenches. The verification suite covers 15 critical scenarios, including:
*   **Recovery Validation:** Ensuring the 8-cycle hysteresis prevents "state chatter" from noisy sensors.
*   **Sticky Latch Testing:** Confirming that thermal and current faults cannot be cleared without a manual reset.
*   **Escalation Logic:** Verifying the watchdog timer successfully triggers a shutdown during persistent failures.
*   **Telemetry Accuracy:** Validating State-of-Charge reporting across all 16 voltage levels.

