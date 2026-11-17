# Testing

## Environment

Tests run from the project root using the local virtual environment:

```sh
cd /home/ssn/data/projects/python-can-canable
.venv/bin/python ...
```

Relevant packages:

- `python-can==4.6.1`
- `pyusb==1.3.1`
- `pypdf` (documentation extraction only)

SocketCAN interfaces must be configured as described in
[Hardware_Setup.md](Hardware_Setup.md).

## Live interface mapping

After the corrected 8 MHz firmware was flashed and the board re-enumerated, the
kernel assigned the names as follows:

| Interface | USB port | Adapter | Reported clock |
| --- | --- | --- | --- |
| `can0` | `1-1.2` | CanableDevTestBoard (new Candlelight 2.5 / WeAct) | `160000000` |
| `can1` | `1-1.1` | old FYSETC UCAN | `48000000` |

This is the reverse of the earlier mapping. Confirm with:

```sh
ip -d link show can0
ip -d link show can1
```

and check the `parentdev` field rather than relying on the interface name.

## Configuration used for the final tests

The user ran:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback off
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 500000 loopback off
sudo ip link set can1 up
```

`restart-ms` was omitted on the new adapter: its `gs_usb` driver rejects it with
`Error: Device doesn't support restart from Bus Off.`

Both links were `UP`, `ERROR-ACTIVE`, bitrate `500000`, loopback off.

## Loopback smoke test — new adapter

`scripts/test_can_loopback.py` temporarily requires SocketCAN loopback mode:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback on
sudo ip link set can0 up

.venv/bin/python scripts/test_can_loopback.py --channel can0 --timeout 2
```

Result:

```text
opening socketcan:can0
bus: socketcan channel 'can0' state: BusState.ACTIVE
sent: ID 123, data 11 22 33 44
recv: ID 123, data 11 22 33 44
OK: loopback frame matched
```

Stats showed 1 TX and 1 RX, zero errors. Loopback was then turned off again.

The old FYSETC adapter had previously passed the same loopback check (as `can0`
before the interface rename), confirming `gs_usb`, SocketCAN, and `python-can`
work independently of the new board.

## Adapter↔adapter test

Script: [`../scripts/test_can_between_adapters.py`](../scripts/test_can_between_adapters.py)

The receiver thread ignores CAN error frames (they are counted and reported as
`skipped`), then compares ID and payload of the first valid data frame.

### new → old

```sh
.venv/bin/python scripts/test_can_between_adapters.py \
  --tx can0 --rx can1 \
  --id 0x321 --data 1122334455667788 --timeout 2
```

Result:

```text
TX can0: id=0x321 dlc=8 data=1122334455667788 send_ok=None
RX can1: skipped 1 error frame(s)
RX can1: id=0x321 dlc=8 data=1122334455667788 ext=False
MATCH
```

### old → new

```sh
.venv/bin/python scripts/test_can_between_adapters.py \
  --tx can1 --rx can0 \
  --id 0x322 --data deadbeef --timeout 2
```

Result:

```text
TX can1: id=0x322 dlc=4 data=deadbeef send_ok=None
RX can0: skipped 0 error frame(s)
RX can0: id=0x322 dlc=4 data=deadbeef ext=False
MATCH
```

### Repeated alternating test

Twenty alternating iterations (ten per direction, unique IDs) all returned
`MATCH`:

```text
passed 20/20 iterations
```

## Earlier failure record (for reference)

Before the 8 MHz firmware rebuild:

| Direction | Frame | Observed result |
| --- | --- | --- |
| old → new | `0x321`, `1122334455667788` | receiver flooded with ~17,500 error frames/s; no data |
| new → old | `0x322`, `deadbeef` | no valid data; sometimes ACK errors |
| 125 kbit/s diagnostic | both | same failure, so not a signal-integrity issue |
| kernel-filtered raw socket | old → new | 0 frames; not a socket-buffer artifact |
| swapped CANH/CANL | both | error flood reduced but still no data |

Error frame decodes from the ElmüSoft status format:

- `id=0x08` — bit-stuffing/protocol error;
- `id=0x20` — no ACK (RX error counter saturated at `0xff`).

SWD sampling of `GPIOB_IDR` showed `PB8`/`PB9` toggling during transmission, so
the signals reached the MCU. Live RCC registers showed `PLLCFGR = 0x11101403`
(`PLLN = 20`), consistent with a 16 MHz assumption. The crystal was later
confirmed to be 8 MHz; see [Firmware_8MHz.md](Firmware_8MHz.md).

## Manual CAN tools

If `can-utils` is installed, a second independent check is:

```sh
candump -t d can0 can1
```

In another shell:

```sh
cansend can0 321#1122334455667788
cansend can1 322#DEADBEEF
```

Each frame should appear on the opposite interface.

## Post-test diagnostics

```sh
ip -s link show can0
ip -s link show can1
ip -d link show can0
ip -d link show can1
```

Look for:

- `ERROR-ACTIVE` state (a few residual errors from earlier failed runs may keep
  the new adapter in `ERROR-WARNING`/`ERROR-PASSIVE` until the link is cycled);
- TX and RX counters increasing as expected;
- RX/TX dropped counters staying at zero;
- bitrate `500000` and loopback off.

## Result summary

| Test | Status | Notes |
| --- | --- | --- |
| Old FYSETC loopback | PASS | `0x123`, `11 22 33 44` |
| New Candlelight loopback at 500 kbit/s | PASS | `0x123`, `11 22 33 44` |
| Elmue firmware flash + SWD verify | PASS | raw image at `0x08000000` |
| BOOT0 fix / direct app boot | PASS | `OPTR = 0xFBEFFCAA`, `1d50:606f` |
| 8 MHz firmware rebuild and flash | PASS | `PLLCFGR = 0x11102803` |
| New → old frame delivery | PASS | `MATCH`, 1 error frame skipped |
| Old → new frame delivery | PASS | `MATCH`, 0 error frames |
| Alternating 20-frame stress | PASS | 20/20 `MATCH` |
