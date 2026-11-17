#!/usr/bin/env python3
import argparse
import threading
import time

import can


def main():
    ap = argparse.ArgumentParser(description="Send/receive a CAN frame between two SocketCAN interfaces")
    ap.add_argument("--tx", default="can0", help="interface to transmit on")
    ap.add_argument("--rx", default="can1", help="interface to receive on")
    ap.add_argument("--id", type=lambda x: int(x, 0), default=0x321, help="CAN arbitration ID (e.g. 0x321)")
    ap.add_argument("--data", default="1122334455667788", help="hex data bytes")
    ap.add_argument("--timeout", type=float, default=2.0, help="receive timeout seconds")
    args = ap.parse_args()

    data = bytes.fromhex(args.data)
    msg = can.Message(arbitration_id=args.id, data=data, is_extended_id=args.id > 0x7FF)

    received = {"errors": 0}

    def recv():
        try:
            with can.interface.Bus(channel=args.rx, interface="socketcan") as bus:
                deadline = time.time() + args.timeout
                while True:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    m = bus.recv(timeout=remaining)
                    if m is None:
                        break
                    if getattr(m, "is_error_frame", False):
                        received["errors"] += 1
                        continue
                    received["msg"] = m
                    break
        except Exception as e:
            received["err"] = e

    t = threading.Thread(target=recv, daemon=True)
    t.start()
    time.sleep(0.2)

    try:
        with can.interface.Bus(channel=args.tx, interface="socketcan") as bus:
            ok = bus.send(msg)
        print(f"TX {args.tx}: id=0x{args.id:X} dlc={len(data)} data={data.hex()} send_ok={ok}")
    except Exception as e:
        print(f"TX {args.tx} failed: {e}")
        raise SystemExit(2)

    t.join(timeout=args.timeout + 1.0)
    print(f"RX {args.rx}: skipped {received['errors']} error frame(s)")
    if "err" in received:
        print(f"RX {args.rx} failed: {received['err']}")
        raise SystemExit(2)

    m = received.get("msg")
    if m is None:
        print(f"RX {args.rx}: TIMEOUT (no frame in {args.timeout}s)")
        raise SystemExit(1)

    print(f"RX {args.rx}: id=0x{m.arbitration_id:X} dlc={m.dlc} data={bytes(m.data).hex()} ext={m.is_extended_id}")
    match = (m.arbitration_id == args.id and bytes(m.data) == data)
    print("MATCH" if match else "MISMATCH")
    raise SystemExit(0 if match else 1)


if __name__ == "__main__":
    main()
