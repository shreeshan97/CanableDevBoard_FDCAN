# CanableDevBoard FDCAN — Project Notes

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

These PDFs total about 43 MB and are kept for offline reference. A sparse checkout can
omit `docs/datasheets/` if repository size is a concern.

## Current status

The canonical status summary is [../README.md#current-status](../README.md#current-status).
It was re-verified on live hardware on 2026-11-18; test results are in [Testing.md](Testing.md).

Interface names can swap after re-enumeration. Always verify `can0`/`can1` with
`ip -d link show` and the `parentdev` field before testing.
