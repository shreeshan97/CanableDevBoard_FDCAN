#!/usr/bin/env python3
"""Simple SocketCAN loopback smoke test for can0 (or given channel).

Bring the interface up in loopback mode first, e.g.:
  sudo ip link set can0 down
  sudo ip link set can0 type can bitrate 500000 loopback on
  sudo ip link set can0 up
"""
import argparse
import sys

import can


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--channel", default="can0")
    p.add_argument("--interface", default="socketcan")
    p.add_argument("--timeout", type=float, default=1.0)
    args = p.parse_args()

    msg = can.Message(arbitration_id=0x123, data=[0x11, 0x22, 0x33, 0x44], is_extended_id=False)
    print(f"opening {args.interface}:{args.channel}")
    with can.Bus(interface=args.interface, channel=args.channel, receive_own_messages=True) as bus:
        print("bus:", getattr(bus, "channel_info", args.channel), "state:", getattr(bus, "state", None))
        bus.send(msg)
        print("sent:", msg)
        rx = bus.recv(timeout=args.timeout)
        print("recv:", rx)
        if rx is None:
            print("FAIL: no frame received (is interface up and in loopback mode?)", file=sys.stderr)
            return 2
        if rx.arbitration_id != msg.arbitration_id or bytes(rx.data) != bytes(msg.data):
            print("FAIL: received frame does not match sent frame", file=sys.stderr)
            return 3
        print("OK: loopback frame matched")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
