#!/usr/bin/env python3
# send one extended advertising set over raw hci, btmgmt rejects over 31 bytes

from __future__ import annotations

import argparse
import socket
import struct
import time

AF_BLUETOOTH = 31
BTPROTO_HCI = 1
HCI_COMMAND_PKT = 0x01
HCI_EVENT_PKT = 0x04
EVT_CMD_COMPLETE = 0x0E
EVT_CMD_STATUS = 0x0F

OGF_LE = 0x08
OCF_SET_EXT_ADV_PARAMS = 0x0036
OCF_SET_EXT_ADV_DATA = 0x0037
OCF_SET_EXT_ADV_ENABLE = 0x0039


def opcode(ogf: int, ocf: int) -> int:
    return (ogf << 10) | ocf


def command(sock: socket.socket, ocf: int, params: bytes) -> int:
    code = opcode(OGF_LE, ocf)
    packet = bytes([HCI_COMMAND_PKT]) + struct.pack("<HB", code, len(params)) + params
    sock.send(packet)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        sock.settimeout(max(0.05, deadline - time.monotonic()))
        try:
            event = sock.recv(1024)
        except TimeoutError:
            break
        if len(event) < 3 or event[0] != HCI_EVENT_PKT:
            continue
        if event[1] == EVT_CMD_COMPLETE and len(event) >= 7:
            got = struct.unpack_from("<H", event, 4)[0]
            if got == code:
                return event[6]
        if event[1] == EVT_CMD_STATUS and len(event) >= 7:
            got = struct.unpack_from("<H", event, 4)[0]
            if got == code:
                return event[6]
    return 0xFF


def params(handle: int = 1) -> bytes:
    return (
        bytes([handle])
        + struct.pack("<H", 0x0000)
        + (0x0801).to_bytes(3, "little")
        + (0x0802).to_bytes(3, "little")
        + bytes([0x07, 0x00, 0x00])
        + b"\x00" * 6
        + bytes([0x00, 0x7F, 0x01, 0x00, 0x01, 0x00, 0x00])
    )


def set_data(sock: socket.socket, handle: int, data: bytes) -> int:
    first = data[:251]
    status = command(sock, OCF_SET_EXT_ADV_DATA, bytes([handle, 0x01, 0x01, len(first)]) + first)
    if status or len(data) <= 251:
        return status
    rest = data[251:]
    return command(sock, OCF_SET_EXT_ADV_DATA, bytes([handle, 0x03, 0x01, len(rest)]) + rest)


def enable(sock: socket.socket, handle: int, on: bool) -> int:
    return command(sock, OCF_SET_EXT_ADV_ENABLE, bytes([1 if on else 0, 1, handle, 0, 0, 0]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--name-len", type=int, default=250)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--service", action="store_true", help="prepend the 0x1f1f service UUID")
    args = parser.parse_args()

    if not 1 <= args.name_len <= 253:
        raise SystemExit("name length must be 1..253")

    payload = bytes([args.name_len + 1, 0x09]) + b"\xff" * args.name_len
    if args.service:
        payload = bytes([0x02, 0x01, 0x06, 0x03, 0x03, 0x1F, 0x1F]) + payload
    print(f"payload {len(payload)} bytes, name {args.name_len}")

    sock = socket.socket(AF_BLUETOOTH, socket.SOCK_RAW, BTPROTO_HCI)
    sock.bind((args.index,))
    sock.setsockopt(socket.SOL_HCI, socket.HCI_FILTER, struct.pack("<IIIH2x", 1 << 4, 0xFFFFFFFF, 0xFFFFFFFF, 0))

    status = command(sock, OCF_SET_EXT_ADV_PARAMS, params(1))
    print(f"set params status 0x{status:02x}")
    if status:
        return

    status = set_data(sock, 1, payload)
    print(f"set data status 0x{status:02x}")
    if status:
        return

    status = enable(sock, 1, True)
    print(f"enable status 0x{status:02x}")
    if status:
        return

    print("advertising. Ctrl-C to stop.")
    try:
        if args.seconds <= 0:
            while True:
                time.sleep(1)
        else:
            time.sleep(args.seconds)
    finally:
        enable(sock, 1, False)
        sock.close()


if __name__ == "__main__":
    main()
