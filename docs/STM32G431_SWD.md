# STM32G431 SWD / OpenOCD procedures

## Debug setup

| Item | Observed value |
| --- | --- |
| Debug probe | ST-LINK/V2.1 (`STLINK V2J45M30`) |
| Probe USB | `0483:3752`, serial `00660049370000024E504332` |
| Target | STM32G431 on WeActStudio USB2CANFD v2 |
| SWD DPIDR | `0x2ba01477` |
| Target voltage | about `3.27 V` |
| SWD clock | requested `2000 kHz`, used `1800 kHz` |
| OpenOCD | `0.12.0+dev-snapshot (2026-02-16-16:07)` |
| NRST | **not connected** |

Because NRST is unavailable, use SWD/core resets and vector jumps instead of
asserting a hardware reset line.

## Basic connect and halt

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; reset halt; shutdown'
```

Before the BOOT0 fix, `reset halt` typically landed in the ST system bootloader
around `pc = 0x1fff4b14`, `msp = 0x20002cf0`, confirming DFU/bootloader mode.

## Flash the firmware

The Elmue DfuSe artifact is:

```text
artifacts/Candlelight2.5 - WeActStudioV2 - STM32G431.dfu
```

For SWD programming, a raw binary was extracted from that artifact:

```text
/tmp/fw.bin
size  = 37438 bytes
load  = 0x08000000
```

Reproducible program-and-verify command:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; reset halt; program /tmp/fw.bin 0x08000000 verify; shutdown'
```

This has already been done successfully on the live board. Keep the original
artifact as the source of truth; `/tmp/fw.bin` is a temporary extraction.

## Boot the application by SWD vector jump

Used before the BOOT0 fix when the MCU stayed in the system bootloader. It reads
the initial stack pointer and reset vector from flash and resumes there:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; reset halt; \
      set sp [mrw 0x08000000]; set pc [mrw 0x08000004]; \
      reg msp $sp; reg pc $pc; resume; shutdown'
```

After this command the board re-enumerated as:

```text
1d50:606f  Candlelight 2.5 - WeAct Studio v2
serial 209D3889594550052
```

and `can1` appeared. This workaround should no longer be needed now that the
BOOT0 option byte is fixed.

## FLASH / option-byte registers

| Register | Address | Purpose |
| --- | --- | --- |
| `FLASH_KEYR` | `0x40022008` | FLASH unlock key register |
| `FLASH_OPTKEYR` | `0x4002200C` | Option-byte unlock key register |
| `FLASH_SR` | `0x40022010` | Status, including `BSY` |
| `FLASH_CR` | `0x40022014` | Control, including `OPTSTRT`, `OBL_LAUNCH`, `LOCK`, `OPTLOCK` |
| `FLASH_OPTR` | `0x40022020` | Live option-byte view |
| `OB0` | `0x1FFF7800` | Option-byte flash word |
| `nOB0` | `0x1FFF7804` | Complement of `OB0` |

Keys and bits:

```text
FLASH_KEY1     = 0x45670123
FLASH_KEY2     = 0xCDEF89AB
FLASH_OPTKEY1  = 0x08192A3B
FLASH_OPTKEY2  = 0x4C5D6E7F

FLASH_SR.BSY         bit 16
FLASH_CR.OPTSTRT     bit 17
FLASH_CR.OBL_LAUNCH  bit 27
FLASH_CR.OPTLOCK     bit 30
FLASH_CR.LOCK        bit 31

FLASH_OPTR.nBOOT1    bit 23
FLASH_OPTR.nSWBOOT0  bit 26
FLASH_OPTR.nBOOT0    bit 27
```

Useful read command:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; echo "OPTR=0x[mrw 0x40022020]"; \
      echo "OB0=0x[mrw 0x1FFF7800] nOB0=0x[mrw 0x1FFF7804]"; \
      echo "CR=0x[mrw 0x40022014] SR=0x[mrw 0x40022010]"; shutdown'
```

Expected final values after the fix:

```text
OPTR = 0xFBEFFCAA
OB0  = 0xFBEFFCAA
nOB0 = 0x04100355
CR   = 0xC0000000   (FLASH + option bytes locked)
SR   = 0x00000000
```

## Permanently disable BOOT0

Reusable script: [`../scripts/fix_boot0_swd.cfg`](../scripts/fix_boot0_swd.cfg)

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -f scripts/fix_boot0_swd.cfg
```

What it does:

1. Halt the target.
2. Unlock FLASH with `KEYR`.
3. Unlock option bytes with `OPTKEYR`.
4. Write `FLASH_OPTR = 0xFBEFFCAA`.
5. Set `FLASH_CR.OPTSTRT` and wait for `FLASH_SR.BSY` to clear.
6. Lock both regions.
7. Unlock both regions again and set `FLASH_CR.OBL_LAUNCH`.
8. Let the resulting system reset reload the option bytes.

### Critical gotcha

`OBL_LAUNCH` is silently ignored unless **both** `FLASH_KEYR` and
`FLASH_OPTKEYR` unlock sequences are issued first. An earlier attempt with only
FLASH unlocked left `OB0 = 0xFBEFFCAA` but `OPTR = 0xFFEFFCAA`; re-issuing
`OBL_LAUNCH` with both unlocks made `OPTR` change to `0xFBEFFCAA` immediately.

After `OBL_LAUNCH`, OpenOCD may briefly report `Could not read register 'pc'`
because the target resets. Wait a few seconds and reconnect; USB should show
`1d50:606f` rather than `0483:df11`.

## Reset and loading semantics

ST RM0440 (`docs/datasheets/rm0440-...pdf`) says:

- Option bytes take effect when `OBL_LAUNCH` is set or after a power reset.
- *"Setting OBL_LAUNCH generates a reset so the option byte loading is performed under system reset."*

Elmue's firmware comments that in its own update path a hardware reset is still
needed for the new pin state to matter. Both statements are consistent with what
we observed: the option bytes must be **loaded**, and the resulting reset makes
the new boot configuration effective.

## Safety

- Do not interrupt power or SWD while option bytes are being programmed.
- Only clear `nSWBOOT0`; preserve `BOR_LEV=4` and `RDP=0xAA`.
- The old FYSETC adapter has no connection to SWD and must not be modified.
- With BOOT0 disabled, use the Elmue "Enter DFU mode" command for future
  firmware updates; see [Elmue_Firmware.md](Elmue_Firmware.md).
