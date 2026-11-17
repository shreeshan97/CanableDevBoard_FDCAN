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

## Preflight checklist

- `can0` = old FYSETC adapter, still working.
- `can1` = new ElmüSoft Candlelight adapter.
- Both interfaces `UP`, classic CAN `500000 bit/s`.
- `loopback off` for adapter-to-adapter tests.
- CANH↔CANH, CANL↔CANL, common GND.
- Correct termination.
- BOOT0 fix applied (`OPTR = 0xFBEFFCAA`).

## Loopback smoke test — old adapter

`scripts/test_can_loopback.py` temporarily requires SocketCAN loopback mode.
Bring `can0` up in loopback mode first:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback on
sudo ip link set can0 up

.venv/bin/python scripts/test_can_loopback.py --channel can0
```

Result already obtained:

```text
PASS — ID 0x123, data 11 22 33 44
```

This confirms the old FYSETC adapter, `gs_usb`, SocketCAN, and `python-can` are
working together.

Restore normal mode before adapter-to-adapter tests:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback off restart-ms 100
sudo ip link set can0 up
```

## Adapter↔adapter test

Script: [`../scripts/test_can_between_adapters.py`](../scripts/test_can_between_adapters.py)

It starts a receiver thread on `--rx`, waits briefly, sends one frame on `--tx`,
then compares ID and payload.

### old → new

```sh
.venv/bin/python scripts/test_can_between_adapters.py \
  --tx can0 --rx can1 \
  --id 0x321 --data 1122334455667788 --timeout 2
```

### new → old

```sh
.venv/bin/python scripts/test_can_between_adapters.py \
  --tx can1 --rx can0 \
  --id 0x322 --data deadbeef --timeout 2
```

Expected output on success:

```text
TX can0: id=0x321 dlc=8 data=1122334455667788 send_ok=True
RX can1: id=0x321 dlc=8 data=1122334455667788 ext=False
MATCH
```

### Current recorded result

Before the interfaces were brought up cleanly after the BOOT0 fix, the result was:

| Direction | Frame | Result |
| --- | --- | --- |
| `can0 -> can1` | `0x321`, `1122334455667788` | **FAIL** — no matching frame received |
| `can1 -> can0` | `0x322`, `deadbeef` | **FAIL** — no matching frame received |
| bidirectional attempt | both | **FAIL** |

These tests have **not yet been rerun** after:

- the successful BOOT0 fix and direct app boot, and
- both interfaces being configured `UP` at `500000` with loopback off.

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

You should see each frame on the opposite interface only (unless `candump` is
also showing local echo behavior).

## Post-test diagnostics

```sh
ip -s link show can0
ip -s link show can1
ip -d link show can0
ip -d link show can1
```

Look for:

- `ERROR-ACTIVE` state;
- TX and RX counters increasing as expected;
- RX/TX dropped counters staying at zero;
- `berr-counter tx 0 rx 0` on the new adapter;
- bitrate `500000` and loopback off.

## Result summary

| Test | Status | Notes |
| --- | --- | --- |
| Old FYSETC loopback on `can0` | PASS | `0x123`, `11 22 33 44` |
| Elmue firmware flash + SWD verify | PASS | raw image at `0x08000000` |
| New board boots Candlelight app after BOOT0 fix | PASS | `1d50:606f`, product string correct |
| `can1` created by `gs_usb` | PASS | clock `160 MHz` |
| `can0 -> can1` frame delivery | PENDING | previously FAIL; retest required |
| `can1 -> can0` frame delivery | PENDING | previously FAIL; retest required |
