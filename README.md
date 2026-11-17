# CanableDevBoard_FDCAN

Live-hardware bring-up, firmware, and validation notes for **CanableDevBoard FDCAN** — an
STM32G431 CAN adapter with an **8 MHz HSE crystal** running ElmüSoft Candlelight 2.5
firmware. An old FYSETC UCAN adapter is used as the known-working reference.

This repository contains the complete local record of the bring-up: board identity,
BOOT0 investigation, corrected firmware, SWD procedures, SocketCAN setup, and
adapter-to-adapter test results. It is not a Python driver package; the driver/plugin work
is tracked separately.

## Current status

- CanableDevBoard FDCAN boots the Candlelight application directly. The BOOT0 pin is
  disabled at option-byte level: `FLASH_OPTR = 0xFBEFFCAA`.
- The original 16 MHz firmware was incorrect for this 8 MHz board. A corrected 8 MHz
  build is committed and flashed; it produces the intended `160 MHz` FDCAN clock
  (`PLLCFGR = 0x11102803`).
- The USB product string is `CanableDevBoard FDCAN CAN adapter`.
- Both adapters were `UP` at `500000 bit/s` during final validation:
  - `can0` = CanableDevBoard FDCAN (`1-1.2`)
  - `can1` = old FYSETC UCAN (`1-1.1`)
- Adapter-to-adapter frame transfer passed in both directions with 0 error frames,
  including 20/20 alternating iterations.

## Board identity

| Field | CanableDevBoard FDCAN | Old FYSETC UCAN |
| --- | --- | --- |
| USB port | `1-1.2` | `1-1.1` |
| VID:PID | `1d50:606f` | `1d50:606f` |
| sysfs `product` | `CanableDevBoard FDCAN CAN adapter` | `UCAN USB to CAN adapter` |
| sysfs `manufacturer` | `ElmueSoft (netcult.ch/elmue)` | `FYSETC` |
| Serial | `209D3889594550052` | `003500465446571320343032` |
| Reported clock | `160 MHz` | `48 MHz` |
| SocketCAN interface | `can0` | `can1` |

Plain `lsusb` still prints `OpenMoko, Inc. Geschwister Schneider CAN adapter` for both
adapters because that name comes from the host USB ID database for `1d50:606f`, not from
the devices. Use sysfs `product` or serial to identify them.

## Repository contents

```text
docs/        Bring-up notes, firmware/SWD procedures, tests, troubleshooting
artifacts/   Corrected 8 MHz firmware and original 16 MHz reference image
firmware/    Reproducible Elmü firmware patch and CanableDevBoard_FDCAN make target
scripts/     SocketCAN loopback and adapter-to-adapter test scripts
```

Start with [docs/README.md](docs/README.md). The main board note is
[docs/CanableDevBoard_FDCAN.md](docs/CanableDevBoard_FDCAN.md).

## Quick start

From the repository root:

```sh
.venv/bin/python --version
.venv/bin/pip list | grep -Ei 'python-can|pyusb'
```

Configure both SocketCAN interfaces:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback off
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 500000 loopback off
sudo ip link set can1 up
```

Verify the live mapping before testing — interface names have swapped after reflashing:

```sh
ls -l /sys/class/net | grep can
ip -d link show can0
ip -d link show can1
```

Run adapter-to-adapter tests:

```sh
.venv/bin/python scripts/test_can_between_adapters.py \
  --tx can0 --rx can1 --id 0x321 --data 1122334455667788 --timeout 2

.venv/bin/python scripts/test_can_between_adapters.py \
  --tx can1 --rx can0 --id 0x322 --data deadbeef --timeout 2
```

## Firmware

The committed firmware was rebuilt from the ElmüSoft Candlelight 2.5 source with:

- dedicated `CanableDevBoard_FDCAN` board definition
- `QUARTZ_FREQU = 8000000`
- USB product string `CanableDevBoard FDCAN CAN adapter`

Artifacts:

| File | Description |
| --- | --- |
| `artifacts/CanableDevBoard-FDCAN-8MHz.bin` | Raw image flashed at `0x08000000` |
| `artifacts/CanableDevBoard-FDCAN-8MHz.dfu` | DfuSe wrapper for USB DFU flashing |
| `artifacts/Candlelight2.5-upstream-16MHz-reference.dfu` | Original upstream 16 MHz image, kept for reference |

Reproducible build inputs:

- `firmware/canable_devboard_fdcan.patch`
- `firmware/Make_G431_Candle_CanableDevBoard_FDCAN`

See [docs/CanableDevBoard_FDCAN.md](docs/CanableDevBoard_FDCAN.md) for toolchain setup,
build commands, SWD flashing, and register verification.

## Important notes

- NRST is not connected; OpenOCD must issue an SWD reset before flashing and before
  starting the application.
- BOOT0 is permanently disabled via option bytes; see
  [docs/BOOT0_Finding.md](docs/BOOT0_Finding.md) and
  [docs/STM32G431_SWD.md](docs/STM32G431_SWD.md).
- Do not add `restart-ms` to CanableDevBoard FDCAN; its `gs_usb` driver rejects it.
- No external pull-up/pull-down is required on `PB8`/`PB9`; firmware uses
  alternate-function push-pull with `GPIO_NOPULL`.
- Always identify adapters by USB port, sysfs `product`, or serial — never by VID/PID
  alone.
