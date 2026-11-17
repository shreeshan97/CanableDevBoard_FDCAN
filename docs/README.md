# CANable 2.5 / Candlelight 2.5 — Project Notes

Live-hardware bring-up notes for the WeActStudio USB2CANFD v2 (STM32G431) adapter
running ElmüSoft Candlelight 2.5 firmware, with an old FYSETC UCAN adapter as the
known-working reference.

## Documents

| Document | Contents |
| --- | --- |
| [BOOT0_Finding.md](BOOT0_Finding.md) | Root cause of spontaneous DFU fallback, ST/Elmue references, option-byte fix, verification |
| [Elmue_Firmware.md](Elmue_Firmware.md) | ElmüSoft firmware behaviour, BOOT0/DFU commands, USB control requests, source references |
| [STM32G431_SWD.md](STM32G431_SWD.md) | OpenOCD/SWD procedures, registers, flashing, app boot, option-byte programming |
| [Hardware_Setup.md](Hardware_Setup.md) | Adapters, USB topology, CAN wiring/termination, SocketCAN configuration |
| [Testing.md](Testing.md) | Test scripts and results (loopback, adapter↔adapter) |
| [Troubleshooting.md](Troubleshooting.md) | Symptoms, causes, and recovery procedures |

## Datasheets

Local ST reference material in [`datasheets/`](datasheets/):

- `rm0440-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf` — boot modes (Table 5, §2.6), option bytes, FLASH registers
- `DS_stm32g431c6.pdf` — STM32G431 pinout (PB8/BOOT0)
- `pm0214-stm32-cortexm4-mcus-and-mpus-programming-manual-stmicroelectronics.pdf` — Cortex-M4 core/SWD details

## Current status (last verified)

- BOOT0 fix **applied and verified**: `FLASH_OPTR = 0xFBEFFCAA`, new adapter boots the Candlelight app directly (no DFU fallback).
- Both adapters enumerate: `can0` (old FYSETC) and `can1` (new Candlelight).
- Both SocketCAN interfaces currently **DOWN/STOPPED** — bring them up before testing.
- Adapter↔adapter CAN frame transfer remains **unverified** (suspected physical-layer wiring/termination issue).
