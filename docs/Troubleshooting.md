# Troubleshooting

## New board appears as `0483:df11` DFU instead of a CAN adapter

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
1d50:606f  Candlelight 2.5 - WeAct Studio v2
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

## No `can1` interface after the app boots

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

- product string `Candlelight 2.5 - WeAct Studio v2`;
- serial `209D3889594550052`;
- `gs_usb` binds `1-1.2:1.0`;
- `can1` appears.

If the product string is missing or USB resets repeatedly, check the USB cable,
hub power, and whether the board is actually in DFU.

## Frames sent but not received between adapters

Work through the physical layer first:

1. Confirm both links are up:

   ```sh
   ip -d link show can0
   ip -d link show can1
   ```

   Expected `state UP`, `ERROR-ACTIVE`, bitrate `500000`, loopback off.

2. Confirm wiring:

   ```text
   CANH <-> CANH
   CANL <-> CANL
   GND  <-> GND
   ```

3. Confirm termination: about `60 Ω` across CANH/CANL with power off if two
   `120 Ω` terminators are installed.

4. Watch both interfaces:

   ```sh
   candump -t d can0 can1
   ```

5. Check error counters:

   ```sh
   ip -s link show can0
   ip -s link show can1
   ```

   Rising TX errors on the sender usually mean no ACK from the other node —
   wiring, termination, bitrate mismatch, or the receiver being offline.

6. Isolate with the known-good adapter:

   ```sh
   sudo ip link set can0 down
   sudo ip link set can0 type can bitrate 500000 loopback on
   sudo ip link set can0 up
   .venv/bin/python scripts/test_can_loopback.py --channel can0
   ```

   If this passes, `python-can`, SocketCAN, and the old adapter are fine.

7. Retest both directions with
   [`scripts/test_can_between_adapters.py`](../scripts/test_can_between_adapters.py).

This is the current open issue; the BOOT0 problem is already resolved.

## `ip link` returns permission denied

The assistant shell has no passwordless `sudo`. The user must run interface
configuration commands:

```sh
sudo ip link set can0 down
sudo ip link set can1 down
sudo ip link set can0 type can bitrate 500000 loopback off restart-ms 100
sudo ip link set can1 type can bitrate 500000 restart-ms 100
sudo ip link set can0 up
sudo ip link set can1 up
```

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
