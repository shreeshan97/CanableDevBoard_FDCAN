# BOOT0 Finding — spontaneous DFU fallback

## Symptom

The CanableDevBoard FDCAN repeatedly appeared as an ST DFU device instead of a CAN adapter:

```
Bus 001 Device ...: ID 0483:df11 STMicroelectronics STM Device in DFU Mode
```

Consequently no `can1` SocketCAN interface existed, and adapter↔adapter tests could not run.

## Root cause

PB8 is shared between **FDCAN1_RX** and **BOOT0** on the STM32G431 (LQFP48). With the
stock option bytes `FLASH_OPTR = 0xFFEFFCAA`, `nSWBOOT0 = 1`, so the MCU samples the
**PB8 pin** at reset. When the CAN transceiver drives the idle/recessive bus level high
on PB8, the MCU enters the ST system bootloader (USB DFU) instead of booting the
Candlelight application from main flash.

The previous attempted fix set `FLASH_OPTR = 0xFFEFFCAA` and was described as
"nSWBOOT0=1, nBOOT0=1" — that is in fact the **default** (pin enabled) configuration
and does not disable BOOT0.

## What ST's documentation says

From `datasheets/rm0440-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf`:

- **§2.6 / Table 5 (Boot modes)**: boot space is selected by `BOOT0` (from pin or
  `nBOOT0` option bit, depending on `nSWBOOT0`) and `nBOOT1`.
- **Option byte organization (p.111)**:
  - `nSWBOOT0` `[26]`: `0` = BOOT0 taken from option bit `nBOOT0`; `1` = BOOT0 taken from PB8 pin.
  - `nBOOT0` `[27]`: `1` = boot main flash.
  - `nBOOT1` `[23]`: boot configuration; `BOR_LEV` `[10:8]`; `RDP` `[7:0]`.
- **Option byte loading (p.119)**: option bytes take effect when `OBL_LAUNCH` is set in
  `FLASH_CR` or after a power reset; *"Setting OBL_LAUNCH generates a reset so the
  option byte loading is performed under system reset."*

With `nSWBOOT0 = 0`, `nBOOT0 = 1`, `nBOOT1 = 1`, Table 5 selects **main flash memory**
regardless of the PB8 level.

## Elmue's equivalent fix

ElmüSoft documents the same workaround as the **"Disable pin Boot0"** button in the
HUD ECU Hacker Firmware Programmer, and as firmware commands
(`*Boot0:Off` for SLCAN, `ELM_ReqSetPinStatus` for Candlelight). See
[Elmue_Firmware.md](Elmue_Firmware.md).

Elmue's source (`Firmware/system.c`) states:

```
// OPTR bit 26 nSWBOOT0 == 1 --> pin BOOT0 is enabled
// OPTR bit 26 nSWBOOT0 == 0 --> pin BOOT0 is disabled, bit nBOOT0 defines boot mode
// OPTR bit 27 nBOOT0   == 1 --> boot into main flash memory
// By default the register OPTR has the value 0xFFEFFCXX
// After disabling the pin BOOT0 it will have 0xFBEFFCXX
```

## Values before and after

| Field | Before | After | Meaning |
| --- | --- | --- | --- |
| `FLASH_OPTR` | `0xFFEFFCAA` | **`0xFBEFFCAA`** | only bit 26 changed |
| `nSWBOOT0` `[26]` | 1 | **0** | ignore PB8, use `nBOOT0` bit |
| `nBOOT0` `[27]` | 1 | 1 | boot main flash |
| `nBOOT1` `[23]` | 1 | 1 | boot configuration |
| `BOR_LEV` `[10:8]` | 4 (2.8 V) | 4 | preserved (helps poor USB power) |
| `RDP` `[7:0]` | `0xAA` | `0xAA` | level 0, no read protection |

Option-byte flash after programming:

```
OB0  @ 0x1FFF7800 = 0xFBEFFCAA
nOB0 @ 0x1FFF7804 = 0x04100355   (valid complement)
```

## Applied fix

Reproducible OpenOCD script: [`../scripts/fix_boot0_swd.cfg`](../scripts/fix_boot0_swd.cfg).

Procedure summary (see [STM32G431_SWD.md](STM32G431_SWD.md) for command details):

1. Halt the target via SWD.
2. Unlock FLASH (`KEYR` = `0x45670123`, `0xCDEF89AB`) and option bytes
   (`OPTKEYR` = `0x08192A3B`, `0x4C5D6E7F`).
3. Write `FLASH_OPTR = 0xFBEFFCAA`.
4. Set `FLASH_CR.OPTSTRT` (bit 17) and wait for `FLASH_SR.BSY` to clear.
5. Re-lock, then unlock **both** regions again and set `FLASH_CR.OBL_LAUNCH` (bit 27)
   to reload the option bytes. This generates a system reset.

> **Gotcha:** setting `OBL_LAUNCH` with only FLASH unlocked is silently ignored;
> the `OPTKEYR` unlock sequence is also required. This caused an earlier false
> conclusion that a physical power cycle was mandatory.

## Verification performed

After the reload reset:

```
OPTR = 0xFBEFFCAA        (live FLASH_OPTR register)
OB0  = 0xFBEFFCAA        (option-byte flash)
nOB0 = 0x04100355        (complement)
```

USB enumeration changed from `0483:df11` (DFU) to:

```
Bus 001 Device 019: ID 1d50:606f OpenMoko, Inc. Geschwister Schneider CAN adapter
/sys/bus/usb/devices/1-1.2/product  = CanableDevBoard FDCAN CAN adapter
/sys/bus/usb/devices/1-1.2/serial   = 209D3889594550052
```

`can1` was recreated by `gs_usb`, confirming the app booted from main flash.

## Re-entering DFU after this fix

With the BOOT0 pin disabled, a boot jumper/pin level cannot force DFU. Use the
ElmüSoft "Enter DFU mode" command (DFU_Detach on interface 1, or `*DFU\r` for SLCAN):
the firmware re-enables the BOOT0 pin first and then requests a USB cable reconnect
to generate the required hardware reset.
