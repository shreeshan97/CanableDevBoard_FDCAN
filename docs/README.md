# CANable 2.5 / Candlelight 2.5 — Project Notes

Live-hardware bring-up notes for **CanableDevBoard FDCAN**, an STM32G431 adapter with
an 8 MHz crystal running ElmüSoft Candlelight 2.5 firmware. An old FYSETC UCAN
adapter is the known-working reference.

## Documents

| Document | Contents |
| --- | --- |
| [BOOT0_Finding.md](BOOT0_Finding.md) | Root cause of spontaneous DFU fallback, ST/Elmue references, option-byte fix, verification |
| [Elmue_Firmware.md](Elmue_Firmware.md) | ElmüSoft firmware behaviour, BOOT0/DFU commands, USB control requests, source references |
| [STM32G431_SWD.md](STM32G431_SWD.md) | OpenOCD/SWD procedures, registers, flashing, app boot, option-byte programming |
| [CanableDevBoard_FDCAN.md](CanableDevBoard_FDCAN.md) | Board identity and USB naming, hardware/wiring/SocketCAN setup, 8 MHz firmware rebuild, build and flash procedures |
| [Testing.md](Testing.md) | Test scripts and results (loopback, adapter↔adapter) |
| [Troubleshooting.md](Troubleshooting.md) | Symptoms, causes, and recovery procedures |

## Datasheets

Local ST reference material in [`datasheets/`](datasheets/):

- `rm0440-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf` — boot modes (Table 5, §2.6), option bytes, FLASH registers
- `DS_stm32g431c6.pdf` — STM32G431 pinout (PB8/BOOT0)
- `pm0214-stm32-cortexm4-mcus-and-mpus-programming-manual-stmicroelectronics.pdf` — Cortex-M4 core/SWD details

## Current status (last verified)

- BOOT0 fix **applied and verified**: `FLASH_OPTR = 0xFBEFFCAA`, CanableDevBoard FDCAN boots the Candlelight app directly (no DFU fallback).
- Root cause of adapter↔adapter failures found: the board has an **8 MHz** crystal, but the supplied firmware was built for **16 MHz**, making the real FDCAN clock 80 MHz instead of the reported 160 MHz.
- Corrected 8 MHz firmware built, flashed, and verified (`PLLCFGR = 0x11102803`), with the USB product string set to `CanableDevBoard FDCAN CAN adapter`.
- Both adapters are `UP` at `500000 bit/s`; `can0` is CanableDevBoard FDCAN, `can1` is the old FYSETC adapter.
- Adapter↔adapter frame transfer **PASS in both directions**; 20/20 alternating iterations passed after the name change, with 0 error frames.
- After the reflash/re-enumeration, `can0` is the CanableDevBoard FDCAN and `can1` is the old FYSETC adapter. Verify names from `ip -d link show` before each test.
