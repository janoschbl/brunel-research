from brunel import protocol


def test_protocol16_decodes_little_endian_fields():
    raw = bytes.fromhex("02010603031f1f13ff787d0010050401000b006600681208000001")
    decoded = protocol.decode_bus(protocol.parse_structures(raw))
    assert decoded.ok
    assert decoded.line_id == 1
    assert decoded.destination_id == 11
    assert decoded.next_stop_id == 102
    assert decoded.hardware_id == 0x1268
    assert decoded.course == 8


def test_protocol18_line_text_and_version():
    raw = bytes.fromhex("13ff787d001213e121040101803800000000000002010603031f1f0409697669")
    decoded = protocol.decode_bus(protocol.parse_structures(raw))
    assert decoded.ok
    assert decoded.line_text == "8"
    assert decoded.data_version == 3


def test_rejects_short_and_foreign_packets():
    assert protocol.decode_bus(protocol.parse_structures(bytes.fromhex("02010603031f1f"))).result == "no_manufacturer"
    assert protocol.decode_bus(protocol.parse_structures(bytes.fromhex("02010603031f1f06ff787d001005"))).result == "too_short"
    assert protocol.candidate_reason(protocol.parse_structures(bytes.fromhex("0201060303180f"))) is None


def test_vehicle_text_parses_route():
    raw = bytes.fromhex("4e6575656e62656b656e486f6c7467726576656e73747261c39f651d52617468617573706c61747a1d")
    parsed = protocol.vehicle_text(raw)
    assert parsed is not None
    assert parsed.destination == "NeuenbekenHoltgrevenstraße"
    assert parsed.next_stop == "Rathausplatz"


def test_eir_overflow_payload_is_255_bytes():
    payload = protocol.eir_overflow_extended_advertisement(253)
    assert len(payload) == 255
    assert payload[0] == 254
    assert payload[1] == 0x09
    assert payload[2:] == b"\xff" * 253


def test_eir_name_expands_to_506_bytes():
    name = protocol.eir_overflow_name(253)
    assert len(name) == 253
    assert name.decode("utf-8", "replace").count("\ufffd") == 253


def test_pnp_id_bluez_guess():
    raw = bytes([2]) + (0x1D6B).to_bytes(2, "little") + (0x0246).to_bytes(2, "little") + (0x054E).to_bytes(2, "little")
    parsed = protocol.parse_pnp_id(raw)
    assert parsed["bluez_guess"] == "5.78"


def test_bus_advertisement_round_trip():
    raw = protocol.bus_advertisement("12", 5)
    decoded = protocol.decode_bus(protocol.parse_structures(raw))
    assert decoded.ok
    assert decoded.line_text == "12"
    assert decoded.data_version == 5


def test_att_and_l2cap_builders_have_expected_lengths():
    assert protocol.att_mtu_request(517) == bytes.fromhex("020502")
    assert len(protocol.att_prepare_write(0x0010, 0, b"\x01\x02")) == 7
    assert protocol.l2cap_connect(1, 0x0001)[:2] == bytes([0x02, 0x01])
    assert protocol.sdp_service_search()[:5] == bytes([0x02, 0x00, 0x01, 0x00, 0x07])
