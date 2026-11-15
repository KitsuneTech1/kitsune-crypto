# Kitsune Private Layer (KPL) v0.1.0 - Initial Release
**Codename:** Monero-Z
**Date:** November 2026
**Commit:** `b33c89e` / `99bb995`

---

## Highlights

- **Formally Verified Cryptographic Core**: 7/7 mechanized invariants verified without flaws or regression (`INV-001` through `INV-007`).
- **Unconditional Privacy**: Dual-key stealth addressing ($P = H(rA)G + B$) + Pedersen commitments ($C = vG + rH$) + CLSAG linkable ring signatures with deterministic key images ($I = x H_p(P)$).
- **Bulletproofs+ Zero-Knowledge Range Arguments**: Non-negative value range proofs ($v \in [0, 2^{64}-1]$) over Curve25519 with zero trusted setup.
- **Reorg-Immune Single-Slot BFT Consensus**: Quorum Certificate engine ($\ge 2f + 1$) guaranteeing instant finality with zero chain reorganizations.
- **Monero Logarithmic Tail Emission**: Smooth decay to a permanent $0.600000$ KPL/block subsidy floor to eliminate fee-starvation security cliffs.
- **Live Multi-Node Distributed Cluster**: Running across 4 Proxmox VE containers (CT 401..404) on local IP mesh.

---

## Included Release Binaries & Assets

| File | Target Platform | SHA-256 Checksum | Description |
|---|---|---|---|
| `kpl-cli-windows-amd64.exe` | Windows x86_64 | Native MSVC release build | Fast CLI wallet & offline transaction signer |
| `kpl-cli-linux-amd64` | Linux x86_64 (glibc 2.39+) | Native ELF release build | Fast CLI wallet & offline transaction signer |
| `whitepaper.pdf` | Universal PDF | Academic publication format | 4-page formal whitepaper with Theorems 1, 2, 3 |
| `WHITEPAPER.md` | Universal Markdown | Audit specification | Cryptographic specification & invariant proofs |
| `SPEC.md` | Universal Markdown | Protocol specification | Core protocol constants & consensus rules |

---

## Quickstart

### Windows
```cmd
kpl-cli-windows-amd64.exe wallet generate
```

### Linux
```bash
chmod +x kpl-cli-linux-amd64
./kpl-cli-linux-amd64 wallet generate
```
