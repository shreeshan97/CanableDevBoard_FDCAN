# CanableDevBoard FDCAN

**CanableDevBoard FDCAN** is the name used throughout this project for the target CAN
adapter: an STM32G431 board with an **8 MHz HSE crystal**, serial
`209D3889594550052`, running ElmüSoft Candlelight 2.5 firmware. The old FYSETC
UCAN adapter remains the known-working reference.

> Although its pin map matches the upstream WeActStudio USB2CANFD v2
> configuration, this is **different hardware** (8 MHz crystal, not 16 MHz).
> It is not referred to as a WeActStudio board in these notes.

## Identity and USB naming

The firmware reports this product string over USB:

```text
CanableDevBoard FDCAN CAN adapter
```

as stored in sysfs and shown by `lsusb -v`:

```sh
cat /sys/bus/usb/devices/1-1.2/product
# CanableDevBoard FDCAN CAN adapter

lsusb -v -d 1d50:606f | grep -E 'iManufacturer|iProduct|iSerial'
```

Manufacturer remains `ElmueSoft (netcult.ch/elmue)`, reflecting the firmware
provenance.

Plain `lsusb` still prints:

```text
Bus 001 Device ...: ID 1d50:606f OpenMoko, Inc. Geschwister Schneider CAN adapter
```

That text comes from the **host USB ID database** for VID `1d50` / PID `606f`,
not from the device. It is expected and harmless. Both CAN adapters share this
VID/PID, so always identify them by USB port, sysfs `product`, or serial.

| Field | CanableDevBoard FDCAN | Old FYSETC UCAN |
| --- | --- | --- |
| USB port | `1-1.2` | `1-1.1` |
| VID:PID | `1d50:606f` | `1d50:606f` |
| sysfs `product` | `CanableDevBoard FDCAN CAN adapter` | `UCAN USB to CAN adapter` |
| sysfs `manufacturer` | `ElmueSoft (netcult.ch/elmue)` | `FYSETC` |
| serial | `209D3889594550052` | `003500465446571320343032` |
| bcdDevice | `2610` | `0000` |
| reported clock | `160 MHz` | `48 MHz` |
| SocketCAN interface | `can0` (latest) | `can1` (latest) |

## USB topology (last observed)

```text
usb1
└─ 1-1  hub (VIA Labs 2109:3431)
   ├─ 1-1.1  old FYSETC UCAN   -> gs_usb -> can1
   ├─ 1-1.2  CanableDevBoard FDCAN   -> gs_usb -> can0
   └─ 1-1.4  ST-LINK/V2.1      -> OpenOCD
```

Interface names are assigned at enumeration and have swapped before. Check the
live mapping rather than assuming:

```sh
lsusb
for d in /sys/bus/usb/devices/1-1.*; do
  printf '%s: ' "$d"
  cat "$d/product" 2>/dev/null || echo '(none)'
done
ls -l /sys/class/net/ | grep can
ip -d link show can0
ip -d link show can1
```

## CAN physical wiring

```text
old CANH  <---->  CanableDevBoard FDCAN CANH
old CANL  <---->  CanableDevBoard FDCAN CANL
old GND   <---->  CanableDevBoard FDCAN GND
```

- A common ground reference is required.
- Do not cross CANH and CANL.
- Keep leads short; twisted pair is preferable.
- Do not involve the ST-Link in the CAN bus wiring.
- PB8 is shared with BOOT0. The option-byte fix prevents accidental DFU; see
  [BOOT0_Finding.md](BOOT0_Finding.md).

## Termination

Standard two-node CAN bus: one `120 Ω` terminator at each end, about `60 Ω`
across CANH/CANL with power off. This was measured during bring-up, so wiring
and termination were correct.

No external pull-up or pull-down is needed on `PB8` (`FDCAN1_RX`) or `PB9`
(`FDCAN1_TX`): the firmware uses alternate-function push-pull with `GPIO_NOPULL`.
The board already has a PB8 pull-down; the BOOT0 option-byte fix makes that pin
state irrelevant for boot.

## SocketCAN configuration

The assistant shell has no passwordless `sudo`; the user must run:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback off
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 500000 loopback off
sudo ip link set can1 up
```

- Use `loopback off` for adapter-to-adapter traffic.
- Both adapters use the same nominal bitrate (`500000`).
- Do not add `restart-ms` to CanableDevBoard FDCAN; its `gs_usb` driver rejects it.
- CAN FD timing ranges are advertised, but current tests use classic CAN.

Expected after configuration: `state UP`, CAN state `ERROR-ACTIVE`, bitrate
`500000`, no growing error counters. Driver details:

```text
can0 (CanableDevBoard FDCAN): gs_usb, clock 160000000,
      tseg1 1..256 tseg2 1..128  sjw 1..128  brp 1..512
      CAN FD: dtseg1 1..32 dtseg2 1..16 dsjw 1..16 dbrp 1..32

can1 (old FYSETC):      gs_usb, clock 48000000,
      tseg1 1..16  tseg2 1..8    sjw 1..4    brp 1..1024
```

## Python environment

From the project root:

```sh
.venv/bin/python --version
.venv/bin/pip list | grep -Ei 'python-can|pyusb|pypdf'
```

Installed for bring-up: `python-can==4.6.1`, `pyusb==1.3.1`, `pypdf`.

See [Testing.md](Testing.md) for scripts and results.

## Firmware: why the 8 MHz build was needed

The supplied upstream DFU
(`artifacts/Candlelight2.5-upstream-16MHz-reference.dfu`) was built with
`QUARTZ_FREQU = 16000000`, which is correct for the 16 MHz upstream board but
**not** for CanableDevBoard FDCAN's 8 MHz crystal. With that image, `system.c` selects
`PLLN = 20`, so the real FDCAN clock was **80 MHz** while the firmware reported
`160 MHz` to `gs_usb`.

Bit timings were therefore computed for 160 MHz while the controller ran at
80 MHz. Loopback still passed (TX and RX used the same wrong timing), but two
real nodes could not communicate: bit-stuffing and no-ACK error frames. With
`QUARTZ_FREQU = 8000000`, `system.c` selects `PLLN = 40`, producing the intended
160 MHz FDCAN clock.

### Artifacts

| File | Description |
| --- | --- |
| `artifacts/CanableDevBoard-FDCAN-8MHz.bin` | Raw image flashed at `0x08000000` |
| `artifacts/CanableDevBoard-FDCAN-8MHz.dfu` | DfuSe wrapper for USB DFU flashing |
| `artifacts/Candlelight2.5-upstream-16MHz-reference.dfu` | Original upstream 16 MHz image, kept for reference |

### Building

An aarch64-hosted Arm toolchain is needed on this machine:

```sh
mkdir -p /tmp/opencode/armtool
cd /tmp/opencode/armtool
curl -Lo arm-gnu-toolchain.tar.xz \
  'https://github.com/synthetos/gcc-arm-none-eabi-archive/releases/download/12.2.Rel1/arm-gnu-toolchain-12.2.rel1-linux-aarch64-arm-none-eabi.tar.xz'
tar -xf arm-gnu-toolchain.tar.xz
export PATH=/tmp/opencode/armtool/arm-gnu-toolchain-12.2.rel1-aarch64-arm-none-eabi/bin:$PATH
```

Clone the upstream Elmü firmware, then apply the project patch and add the
board-specific make target:

```sh
REPO_ROOT="$(git rev-parse --show-toplevel)"

git clone https://github.com/Elmue/CANable-2.5-firmware-Slcan-and-Candlelight /tmp/elmue-canable
cd /tmp/elmue-canable
git apply "$REPO_ROOT/firmware/canable_devboard_fdcan.patch"
cp "$REPO_ROOT/firmware/Make_G431_Candle_CanableDevBoard_FDCAN" Build/
make -s -f Build/Make_G431_Candle_CanableDevBoard_FDCAN
```

The patch adds a `CanableDevBoard_FDCAN` board definition (8 MHz, matching pin map)
and overrides the USB product string to `CanableDevBoard FDCAN CAN adapter`. The make
target sets `QUARTZ_FREQU = 8000000`; no command-line override is needed.

Output:

```text
Build/STM32G431_Candlelight_CanableDevBoard_FDCAN/Candlelight2.5_CanableDevBoard_FDCAN_STM32G431_0x261001.bin
```

### Flashing over SWD

NRST is not connected, so reset via SWD first or the STM32G4 flash algorithm
can time out:

```sh
REPO_ROOT="$(git rev-parse --show-toplevel)"
BIN="$REPO_ROOT/artifacts/CanableDevBoard-FDCAN-8MHz.bin"

openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c "init; reset halt; flash write_image erase $BIN 0x08000000; \
      verify_image $BIN 0x08000000; shutdown"
```

Start the application with a real SWD reset so USB re-enumerates cleanly:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; reset run; sleep 200; shutdown'
```

### Verification

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; echo "PLLCFGR=0x[mrw 0x4002100C]"; echo "OPTR=0x[mrw 0x40022020]"; shutdown'
```

Expected:

```text
PLLCFGR = 0x11102803   # PLLN = 40, 8 MHz x 40 / 2 = 160 MHz
OPTR    = 0xFBEFFCAA   # BOOT0 pin disabled
```

USB should show `product = CanableDevBoard FDCAN CAN adapter`, and
`ip -d link show can0` should report `clock 160000000`.
