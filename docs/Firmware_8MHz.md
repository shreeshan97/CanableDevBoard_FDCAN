# Rebuilding Candlelight 2.5 for CanableDevTestBoard (8 MHz WeAct board)

The board labelled **CanableDevTestBoard** is the WeActStudio STM32G431 adapter
with an 8 MHz HSE crystal.

## Why this was needed

The supplied DFU image
`artifacts/Candlelight2.5 - WeActStudioV2 - STM32G431.dfu` was built from
`Build/Make_G431_Candle_WeActStudioV2`, which sets:

```make
QUARTZ_FREQU = 16000000
```

That is correct for the WeAct **USB2CANFD v2** board described by ElmüSoft, but
the board on this bench has an **8 MHz HSE crystal** (confirmed by reading the
crystal marking). With the 16 MHz build, `system.c` selects `PLLN = 20`, so the
real PLL/FDCAN clock is only **80 MHz** even though the firmware reports
`160 MHz` to `gs_usb`.

Result: bit timings were computed for 160 MHz while the controller ran at
80 MHz. Loopback still passed because TX and RX used the same wrong timing, but
two real nodes could not communicate: the receiver saw bit-stuffing and no-ACK
error frames.

With `QUARTZ_FREQU = 8000000`, `system.c` selects `PLLN = 40`, producing the
intended **160 MHz** PLL/FDCAN clock.

## Corrected artifacts

| File | Description |
| --- | --- |
| `artifacts/Candlelight2.5 - WeActStudioV2 - STM32G431 - 8MHz.bin` | Raw image flashed at `0x08000000` |
| `artifacts/Candlelight2.5 - WeActStudioV2 - STM32G431 - 8MHz.dfu` | DfuSe wrapper for USB DFU flashing |

The original 16 MHz DFU is kept for reference.

## Building

An aarch64-hosted Arm toolchain is required on this machine. One way to obtain
it without a system package install:

```sh
mkdir -p /tmp/opencode/armtool
cd /tmp/opencode/armtool
curl -Lo arm-gnu-toolchain.tar.xz \
  'https://github.com/synthetos/gcc-arm-none-eabi-archive/releases/download/12.2.Rel1/arm-gnu-toolchain-12.2.rel1-linux-aarch64-arm-none-eabi.tar.xz'
tar -xf arm-gnu-toolchain.tar.xz
export PATH=/tmp/opencode/armtool/arm-gnu-toolchain-12.2.rel1-aarch64-arm-none-eabi/bin:$PATH
```

Then override `QUARTZ_FREQU` on the make command line; no source file needs to
be edited:

```sh
cd /tmp/elmue-canable
make -s -f Build/Make_G431_Candle_WeActStudioV2 QUARTZ_FREQU=8000000
```

Output:

```text
Build/STM32G431_Candlelight_WeActStudioV2/Candlelight2.5_WeActStudioV2_STM32G431_0x261001.bin
```

`GCC_Rules.mk` turns the override into `-DHSE_VALUE=8000000`, and `system.c`
already contains the matching `PLLN = 40` branch.

## Flashing over SWD

NRST is not connected, so reset via SWD first; otherwise the STM32G4 flash
algorithm can time out:

```sh
BIN=/tmp/elmue-canable/Build/STM32G431_Candlelight_WeActStudioV2/Candlelight2.5_WeActStudioV2_STM32G431_0x261001.bin

openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c "init; reset halt; flash write_image erase $BIN 0x08000000; \
      verify_image $BIN 0x08000000; shutdown"
```

Start the application with a real SWD reset so USB re-enumerates cleanly:

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; reset run; sleep 200; shutdown'
```

A direct vector jump also boots the app, but after a plain flash the USB
peripheral may need the reset to enumerate reliably.

## Verification

```sh
openocd -f interface/stlink.cfg -f target/stm32g4x.cfg \
  -c 'init; echo "PLLCFGR=0x[mrw 0x4002100C]"; shutdown'
```

Expected:

```text
PLLCFGR = 0x11102803
```

`0x28` in bits `[14:8]` is `PLLN = 40` (8 MHz × 40 = 320 MHz VCO, `/2` = 160 MHz
PLLQ for FDCAN). The old value was `0x11101403` (`PLLN = 20`).

USB should show:

```text
1d50:606f  Candlelight 2.5 - WeAct Studio v2
```

And `ip -d link show <new adapter>` should report:

```text
clock 160000000
```

Note that after re-enumeration the kernel may assign `can0` to the new adapter
and `can1` to the old FYSETC adapter. Always check the `parentdev` in
`ip -d link show` before running tests.
