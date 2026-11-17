# Troubleshooting

The target board discussed here is **CanableDevBoard FDCAN**.

## CanableDevBoard FDCAN appears as `0483:df11` DFU instead of a CAN adapter

### Symptoms

```text
Bus 001 Device ...: ID 0483:df11 STMicroelectronics STM Device in DFU Mode
```

No `can1` interface exists.

### Cause

PB8 is shared between `FDCAN1_RX` and BOOT0. With stock option bytes
`nSWBOOT0 = 1`, the MCU samples the pin at reset. A high CAN_RX level sends it
into the ST system bootloader.

### Fix

Run the SWD option-byte fix:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -f scripts/fix_boot0_swd.cfg
```

Then verify:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; echo "OPTR=0x[mrw 0x40022020] OB0=0x[mrw 0x1FFF7800]"; shutdown'
```

Expected:

```text
OPTR = 0xFBEFFCAA
OB0  = 0xFBEFFCAA
```

USB should then show:

```text
1d50:606f  CanableDevBoard FDCAN CAN adapter
```

See [BOOT0_Finding.md](BOOT0_Finding.md) and
[STM32G431_SWD.md](STM32G431_SWD.md).

## `OBL_LAUNCH` appears to do nothing

### Symptom

After programming option bytes:

```text
OB0  = 0xFBEFFCAA
OPTR = 0xFFEFFCAA   (unchanged)
```

### Cause

`OBL_LAUNCH` was written with only the FLASH unlock sequence applied. The
option-byte unlock is also required.

### Fix

Issue both sequences before `OBL_LAUNCH`:

```text
FLASH_KEYR:    0x45670123, 0xCDEF89AB
FLASH_OPTKEYR: 0x08192A3B, 0x4C5D6E7F
FLASH_CR:      0x08000000
```

The reusable script already does this.

## Board still stuck in bootloader after the option-byte write

Use the SWD vector jump to start the application:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; reset halt; \
      set sp [mrw 0x08000000]; set pc [mrw 0x08000004]; \
      reg msp $sp; reg pc $pc; resume; shutdown'
```

If this works but a later power cycle returns to DFU, recheck `OPTR` after a
full reset. It must read `0xFBEFFCAA`.

## USB access denied for Elmue commands

### Symptoms

```text
LIBUSB_ERROR_ACCESS
Access denied (insufficient permissions)
ValueError: The device has no langid (permission issue, ...)
```

### Cause

`1d50:606f` USB nodes are `root:root` and no udev rule is installed. Also,
`gs_usb` owns Candlelight interface 0, so raw USB access requires detaching the
kernel driver.

### Options

- Use SWD, as done here.
- Or install an appropriate udev rule and detach the kernel driver before
  issuing Elmue vendor requests.
- Do not assume the firmware command failed just because `pyusb` cannot open
  the device.

See [Elmue_Firmware.md](Elmue_Firmware.md).

## No CAN interface appears after the app boots

Check:

```sh
lsusb
for d in /sys/bus/usb/devices/1-1.*; do
  printf '%s: ' "$d"
  cat "$d/product" 2>/dev/null || echo '(none)'
done
ls -l /sys/class/net/ | grep can
dmesg | tail -40
```

Expected:

- product string `CanableDevBoard FDCAN CAN adapter`;
- serial `209D3889594550052`;
- `gs_usb` binds `1-1.2:1.0`;
- a CAN interface appears. After the last reflash it was named `can0`, while
  the old FYSETC adapter became `can1`. Always verify with `ip -d link show`
  and the `parentdev` field.

If the product string is missing or USB resets repeatedly, check the USB cable,
hub power, and whether the board is actually in DFU.

## Frames sent but not received between adapters

This was resolved by rebuilding the firmware for the actual **8 MHz** crystal.
See [CanableDevBoard_FDCAN.md](CanableDevBoard_FDCAN.md) and the final results in
[Testing.md](Testing.md).

If it recurs, check in this order:

1. **Firmware/crystal match.** The original DFU was built with
   `QUARTZ_FREQU=16000000`. On an 8 MHz board this gives an 80 MHz FDCAN clock
   while `gs_usb` reports 160 MHz. Loopback still passes, but real traffic
   fails with bit-stuffing (`0x08`) and no-ACK (`0x20`) error frames. Verify
   with:

   ```sh
   openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
     -c 'init; echo "PLLCFGR=0x[mrw 0x4002100C]"; shutdown'
   ```

   Correct value: `0x11102803` (`PLLN = 40`). Old wrong value:
   `0x11101403` (`PLLN = 20`).

2. **Interface names.** After reflashing, the CanableDevBoard FDCAN became `can0` and the
   old FYSETC became `can1`. Confirm with `ip -d link show` and `parentdev`.

3. **Link state.** Both links must be `UP`, `ERROR-ACTIVE`, bitrate `500000`,
   loopback off. Cycle a link down/up to clear residual error-passive state.

4. **Physical layer.** CANH↔CANH, CANL↔CANL, common GND, about `60 Ω` across
   CANH/CANL with power off. These were verified correct during bring-up;
   swapping CANH/CANL reduced the error flood but did not restore data, so
   polarity was not the cause.

5. **Loopback isolation.** Run
   [`scripts/test_can_loopback.py`](../scripts/test_can_loopback.py) on each
   adapter separately. A pass proves the host/driver/controller path works but
   does **not** prove the bitrate is correct: internal loopback uses the same
   wrong timing on both TX and RX and therefore still succeeds.

6. **Error-frame filtering.** The adapter test script now ignores error frames;
   kernel-level filtering was also tested and still showed zero valid frames,
   ruling out socket-buffer flooding.

## Pull resistors on PB8/PB9

No external pull-up or pull-down is required on `PB8` (`FDCAN1_RX`) or `PB9`
(`FDCAN1_TX`). `Firmware/can.c` configures both as `GPIO_MODE_AF_PP` with
`GPIO_NOPULL`; the transceiver drives RXD, and its TXD input normally has an
internal pull-up to recessive. The `120 Ω` termination belongs on CANH/CANL,
not on the MCU pins.

On the CanableDevBoard FDCAN, `PB8` is shared with BOOT0 and the board already
has a hardware pull-down. The option-byte fix makes BOOT0 pin state irrelevant,
so leave that resistor in place and do not add a pull-up there.

## `ip link` returns permission denied

The assistant shell has no passwordless `sudo`. The user must run interface
configuration commands:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback off
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 500000 loopback off
sudo ip link set can1 up
```

Do not use `restart-ms` on the CanableDevBoard FDCAN; its `gs_usb` driver
returns `Error: Device doesn't support restart from Bus Off.`

## NRST is not connected

Do not expect hardware `nSRST` to work. Use:

- `reset halt` via SWD;
- the vector-jump procedure for app boot;
- `OBL_LAUNCH` for option-byte reload.

## Need to enter DFU after BOOT0 has been disabled

A boot jumper will no longer work. Use the ElmüSoft "Enter DFU mode" command:

- Slcan: `*DFU\r`
- Candlelight: `DFU_Detach` on interface 1, then `DFU_GetStatus`

The firmware re-enables the BOOT0 pin first. If feedback is `ResetRequired`,
reconnect the USB cable to perform the needed hardware reset. If raw USB access
is blocked, use SWD or temporarily enable BOOT0 via option bytes with the same
register sequence in reverse.
