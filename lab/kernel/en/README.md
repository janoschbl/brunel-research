# Kernel matrix

[English](README.md) · [Deutsch](../de/README.md)

The module kernel is unknown. The BlueZ version does not determine it. Fingerprint
the kernel before choosing a kernel CVE.

## Fingerprint order

1. Read `/proc/version` and `/etc/os-release` if a shell exists.
2. If no shell, use the GATT and L2CAP behaviour as a coarse signal only.
3. Record the exact build string, not just the major version.

## Matrix

| Kernel | L2CAP UAF candidates | Notes |
|---|---|---|
| 5.10 LTS | CVE-2022-42896, CVE-2022-42895 | check the stable backport |
| 5.15 LTS | CVE-2022-42896, CVE-2024-36013 | check the stable backport |
| 6.1 LTS | CVE-2024-41062, CVE-2024-49950 | check the stable backport |
| 6.6 LTS | CVE-2026-98107, CVE-2026-98457 | check the stable backport |
| 6.12+ | mostly DoS | verify each fix |

## QEMU

Use a distro kernel matching the matrix, not the host kernel. Attach a virtual
controller with `btvirt` or `vhci` inside the guest. Run the same bench with
`--transport hci-socket:0`.

A negative L2CAP result only means the path did not crash that build. It is not
a non-vulnerability proof.
