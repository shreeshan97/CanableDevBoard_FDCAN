# ElmüSoft Candlelight 2.5 firmware

## Scope

Target firmware for the new adapter is the ElmüSoft Candlelight 2.5 image in
[`../artifacts/Candlelight2.5 - WeActStudioV2 - STM32G431.dfu`](../artifacts/Candlelight2.5%20-%20WeActStudioV2%20-%20STM32G431.dfu).
It is a combined Slcan + Candlelight codebase with ElmüSoft extensions, not just the
stock `gs_usb` candle firmware.

Reference material:

- Elmue firmware update / developer manual: <https://netcult.ch/elmue/CANable%20Firmware%20Update/>
- GitHub mirror used during bring-up: <https://github.com/Elmue/CANable-2.5-firmware-Slcan-and-Candlelight>
- Temporary local clone used for source inspection: `/tmp/elmue-canable` (not committed)

## Observed identity

| State | USB ID | Product / serial | Notes |
| --- | --- | --- | --- |
| DFU bootloader | `0483:df11` | `STM32 STLink`-style DFU string, serial `209D38895945` | ST system bootloader; alts for internal flash, option bytes, OTP |
| Candlelight app | `1d50:606f` | `Candlelight 2.5 - WeAct Studio v2`, serial `209D3889594550052`, bcdDevice `26.10` | Interface 0 = Candlelight/`gs_usb` → `can1`; interface 1 = DFU |

> The old FYSETC adapter is also `1d50:606f`. Identify adapters by USB port,
> product string, and serial — not by VID/PID alone.

## Firmware flashing notes

- The DFU image was flashed to the new board's ST bootloader at `0483:df11`.
- A raw binary was extracted from the DfuSe artifact to `/tmp/fw.bin`
  (`37438` bytes, load address `0x08000000`) for deterministic SWD programming.
- OpenOCD SWD `program ... verify` succeeded.
- After the BOOT0 fix, the board boots straight into the Candlelight app; the
  SWD vector-jump workaround is no longer needed.

See [STM32G431_SWD.md](STM32G431_SWD.md) for the exact OpenOCD procedures.

## BOOT0 behavior in this firmware

Elmue's manual calls the shared BOOT0/CAN_RX pin a **hardware misdesign** on
LQFP48 STM32G4 devices: PB8 is both `FDCAN1_RX` and `BOOT0`. A high CAN receive
level at power-on can put the MCU into the ST bootloader (`0483:df11`) instead
of the application.

Elmue's workaround is the **"Disable pin Boot0"** function. In the firmware
source this is:

```c
// Firmware/system.c
OPT_BOOT0_Enable  = 2, // Pin BOOT0 defines what is booted (flash or bootloader)
OPT_BOOT0_Disable = 3, // Always boot into flash memory
```

`system_set_option_bytes(OPT_BOOT0_Disable)` writes the STM32G4 option bytes so
that `nSWBOOT0 = 0`, `nBOOT0 = 1`, and `nBOOT1 = 1`. The source documents the
transition:

```text
Default OPTR:               0xFFEFFCXX   (BOOT0 pin active)
After "Disable pin BOOT0":  0xFBEFFCXX   (BOOT0 pin ignored)
```

Our SWD procedure produces exactly `0xFBEFFCAA`, preserving `BOR_LEV=4` and
`RDP=0xAA`. Details and ST references are in [BOOT0_Finding.md](BOOT0_Finding.md).

### Important consequence

After BOOT0 is disabled, a boot jumper or pin level no longer forces DFU. To
update firmware again, use Elmue's **"Enter DFU mode"** command. The firmware
re-enables the BOOT0 pin first, then asks for a USB cable reconnect to perform
the required hardware reset.

Elmue's source notes that its own `HAL_FLASH_OB_Launch()` call does not activate
the new option bytes in that code path; a hardware reset is used instead. In our
direct SWD path, setting `OBL_LAUNCH` with both flash and option-byte unlocks did
reload the option bytes successfully.

## Slcan commands

The flashed variant is currently Candlelight/`gs_usb`, so these SLCAN commands
are documentation only for this setup. Elmue's Slcan firmware supports:

| Command | State | Response / effect |
| --- | --- | --- |
| `*Boot0:Off\r` | closed | Disable pin BOOT0 in option bytes |
| `*Boot0:?\r` | open or closed | `+1\r` if enabled, `+0\r` if disabled |
| `*DFU\r` | open or closed | Re-enable BOOT0 and enter DFU; if feedback is `FBK_ResetRequired`, reconnect the USB cable |

## Candlelight vendor requests

ElmüSoft's Candlelight protocol keeps standard `gs_usb` requests for CAN I/O and
adds vendor requests for board information, filtering, pin control, and flash
access. From `SampleApplication Python/Source/Candlelight_def.py`:

| Request | Value | Direction / payload |
| --- | --- | --- |
| `GS_ReqSetDeviceMode` | `2` | OUT `kDeviceMode`; set `ELM_DevFlagProtocolElmue` first |
| `ELM_ReqGetBoardInfo` | `20` | IN `kBoardInfo` |
| `ELM_ReqSetFilter` | `21` | OUT `kFilter` |
| `ELM_ReqGetLastError` | `22` | IN `uint8_t` feedback code |
| `ELM_ReqSetBusLoadReport` | `23` | OUT interval byte |
| `ELM_ReqSetPinStatus` | `24` | OUT `kPinStatus` |
| `ELM_ReqGetPinStatus` | `25` | IN 2-byte status; `wValue = PinID` |
| `ELM_ReqReadFlash` | `26` | IN user flash segment |
| `ELM_ReqWriteFlash` | `27` | OUT user flash segment |

The ElmüSoft protocol flag is:

```python
ELM_DevFlagProtocolElmue = 0x04000  # bit 14
```

Pin values for the BOOT0 operation:

```python
ePinOperation.Disable = 5
ePinID.BOOT0          = 1

class kPinStatus(Structure):
    Operation: uint16   # ePinOperation
    PinID:     uint16   # ePinID
    Reserved1: uint32
    Reserved2: uint32   # 12 bytes total
```

The Python sample calls:

```python
k_PinStatus.Operation = ePinOperation.Disable
k_PinStatus.PinID     = ePinID.BOOT0
CtrlTransfer(OUT, ELM_ReqSetPinStatus, channel, k_PinStatus)
```

Details from the sample implementation:

- Vendor requests target the Candlelight interface (`wIndex = 0` here).
- `bRequestType` is interface recipient + vendor + IN/OUT direction.
- After every vendor request, the host issues `ELM_ReqGetLastError` and checks
  for `eFeedback.Success`.
- `ELM_ReqGetPinStatus` puts the pin ID in `SETUP.wValue` because an IN control
  transfer cannot otherwise carry a parameter.

## Why we used SWD instead of the USB command

Raw USB access to `1d50:606f` failed in this environment:

```text
LIBUSB_ERROR_ACCESS / Access denied (insufficient permissions)
```

The USB device nodes are `root:root` and no udev rule is installed. Also,
`gs_usb` owns interface 0, so a raw-USB tool must detach the kernel driver.
Either a suitable udev rule/root access or the SWD path is required. We used
SWD to write the same option-byte value that the Elmue command would write.

## Useful source files in the Elmue tree

- `Firmware/system.c` — option-byte read/program logic and BOOT0 comments
- `Firmware/Slcan/control.c` — `*Boot0:Off`, `*Boot0:?`, `*DFU` parsing
- `Firmware/Candlelight/control.c` — `ELM_ReqSetPinStatus` / `ELM_ReqGetPinStatus`
- `Firmware/dfu.c`, `Firmware/Candlelight/usb_class.c` — DFU detach behavior
- `SampleApplication Python/Source/Candlelight_def.py` — request and enum definitions
- `SampleApplication Python/Source/Candlelight.py` — `DisableBootPin()`, `EnterDfuMode()`
