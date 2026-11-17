# Hardware setup

## Board designation

The new adapter used for this bring-up is labelled **CanableDevTestBoard** in
these notes. It is the WeActStudio STM32G431 board with an 8 MHz crystal,
serial `209D3889594550052`, running ElmüSoft Candlelight 2.5 firmware. The old
FYSETC UCAN adapter remains the known-working reference.

## Inventory

| Device | USB port | USB identity | Interface | Notes |
| --- | --- | --- | --- | --- |
| Old FYSETC UCAN | `1-1.1` | `1d50:606f`, `UCAN USB to CAN adapter`, serial `003500465446571320343032` | `can1` | Known-good reference; clock `48 MHz` |
| CanableDevTestBoard (WeActStudio USB2CANFD v2) | `1-1.2` | `1d50:606f`, `Candlelight 2.5 - WeAct Studio v2`, serial `209D3889594550052` | `can0` | Target board; 8 MHz crystal; corrected firmware gives FDCAN clock `160 MHz` |
| ST-LINK/V2.1 | `1-1.4` | `0483:3752`, serial `00660049370000024E504332` | — | SWD debugger; NRST not connected |
| USB hub | `1-1` | VIA Labs `2109:3431` | — | Both adapters and debugger attach here |

Both CAN adapters share VID/PID `1d50:606f`. Always map them by USB port,
product string, or serial. The names above are from the latest re-enumeration;
the kernel had previously assigned the opposite names. Never assume `can0` is
the old adapter.

## USB topology (last observed)

```text
usb1
└─ 1-1  hub
   ├─ 1-1.1  old FYSETC UCAN  -> gs_usb -> can1
   ├─ 1-1.2  new Candlelight  -> gs_usb -> can0
   └─ 1-1.4  ST-LINK/V2.1     -> OpenOCD
```

Check the live mapping with:

```sh
lsusb
for d in /sys/bus/usb/devices/1-1.*; do
  printf '%s: ' "$d"
  cat "$d/product" 2>/dev/null || echo '(none)'
done
ls -l /sys/class/net/ | grep can
```

## CAN physical wiring

For adapter-to-adapter tests, connect:

```text
old CANH  <---->  new CANH
old CANL  <---->  new CANL
old GND   <---->  new GND
```

Important details:

- A common ground reference is required.
- Do not cross CANH and CANL.
- Keep leads short; twisted pair is preferable.
- Do not involve the ST-Link in the CAN bus wiring.
- The new adapter previously fell into DFU when CAN_RX/PB8 was high at reset.
  The BOOT0 fix now prevents that; see [BOOT0_Finding.md](BOOT0_Finding.md).

## Termination

Target a standard two-node CAN bus:

- one `120 Ω` termination at each physical end of the bus;
- total measured resistance across `CANH` and `CANL` with power off should be
  about `60 Ω` when both terminators are installed;
- about `120 Ω` if only one terminator is installed;
- no termination (high/open resistance) usually causes ACK errors and no
  communication.

If either board has switchable or jumper-selectable termination, verify its
actual state rather than assuming. This was measured as about `60 Ω` during
bring-up, so termination and wiring were correct; the actual failure cause was
the firmware/crystal mismatch described in [Firmware_8MHz.md](Firmware_8MHz.md).

No pull-up or pull-down resistors are needed on `PB8`/`PB9`. The firmware uses
alternate-function push-pull with `GPIO_NOPULL`. On WeActStudioV2, `PB8` is
shared with BOOT0 and already has a board pull-down; the BOOT0 option-byte fix
makes that pin state irrelevant for boot.

## SocketCAN configuration

The host user has `sudo` but the assistant shell does not have passwordless
`sudo`, so the user must run:

```sh
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 loopback off
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 500000 loopback off
sudo ip link set can1 up
```

Notes:

- Use `loopback off` for adapter-to-adapter traffic. Loopback is only for the
  single-adapter smoke test.
- Both adapters must use the same nominal bitrate (`500000` here).
- Do not add `restart-ms` to the new adapter; its `gs_usb` driver rejects it.
- The new adapter supports CAN FD timing ranges, but current tests use classic
  CAN frames.

## Verification commands

```sh
ip -d link show can0
ip -d link show can1
ip -s link show can0
ip -s link show can1
```

Expected after configuration:

- `state UP`
- CAN state `ERROR-ACTIVE`
- bitrate `500000`
- `loopback` off
- no growing RX/TX error counters

Observed driver details:

```text
can0: gs_usb, clock 160000000,
      tseg1 1..256 tseg2 1..128  sjw 1..128  brp 1..512
      CAN FD: dtseg1 1..32 dtseg2 1..16 dsjw 1..16 dbrp 1..32

can1: gs_usb, clock 48000000,
      tseg1 1..16  tseg2 1..8    sjw 1..4    brp 1..1024
```

## Python environment

From the project root:

```sh
.venv/bin/python --version
.venv/bin/pip list | grep -Ei 'python-can|pyusb|pypdf'
```

Installed for bring-up:

- `python-can==4.6.1`
- `pyusb==1.3.1`
- `pypdf` (used to extract text from the local ST PDFs)

See [Testing.md](Testing.md) for the actual scripts and commands.
