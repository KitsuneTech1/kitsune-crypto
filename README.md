# Kitsune Private Layer (KPL)
> **Formally Verified Privacy Ledger with Fast Multi-Chain Liquidity**

[![CI](https://github.com/KitsuneTech1/kitsune-crypto/actions/workflows/ci.yml/badge.svg)](https://github.com/KitsuneTech1/kitsune-crypto/actions/workflows/ci.yml)
[![Invariants](https://img.shields.io/badge/Invariants-7%2F7%20Verified-brightgreen.svg)]()
[![BFT Consensus](https://img.shields.io/badge/Finality-Single--Slot%20BFT-blue.svg)]()
[![Multi-Chain](https://img.shields.io/badge/Bridges-Base%20%7C%20Arbitrum%20%7C%20Solana%20%7C%20Lightning%20%7C%20XMR-purple.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

Kitsune Private Layer (**KPL**, codename **Monero-Z**) is a high-assurance Layer-1 privacy-preserving blockchain protocol engineered with compile-time mathematical invariants. KPL blends Curve25519 stealth addressing, Pedersen commitments, Compact Linkable Spontaneous Anonymous Group (CLSAG) ring signatures, zero-knowledge Bulletproofs+ range arguments, and deterministic single-slot Byzantine Fault Tolerant (BFT) consensus with perpetual tail emission.

---

## 1. Quick Cross-Chain Rails (Everyday Liquidity)

KPL provides fast, low-friction settlement rails for common everyday assets alongside native privacy features:

| Chain | Assets | Settlement Time | Architecture |
|---|---|---|---|
| **Base (EVM L2)** | USDC, USDT, ETH | ~3 seconds | Optimistic Relayer & Hashlock Vault |
| **Arbitrum (EVM L2)** | USDC, USDT, ETH | ~3 seconds | Low-gas Nitro Vault |
| **Solana** | SPL-USDC, SOL | ~2 seconds | Sub-second SPL Token Lockup |
| **Bitcoin Lightning** | BTC (satoshis) | ~1 second | Submarine Swap (instant off-chain) |
| **Monero** | XMR | ~2 minutes | Scriptless Adaptor Signatures |

For technical details, see the [Multi-Chain Fast Bridge Specification](docs/FAST_BRIDGES.md) and [Monero Atomic Swap Specification](docs/BRIDGE_ATOMIC_SWAP.md).

---

## 2. Core Invariants

Every state transition is verified against 7 mechanized invariants:

| Invariant | Formulation | Guarantee |
|---|---|---|
| **INV-001: Stealth Address Unlinkability** | $P = H(rA)G + B$ | Real receiver recovers spend key $x = H(aR) + b$; third parties cannot link $P$ to recipient. |
| **INV-002: Zero-Inflation Homomorphism** | $\sum C_{in} - \sum C_{out} - f \cdot G = r_{\Delta} H$ | Commitments preserve value; token minting is bounded strictly by consensus emission. |
| **INV-003: CLSAG Ring Anonymity** | $L_i = \alpha G + c_i P_i, R_i = \alpha H_p(P_i) + c_i I$ | Real signer is mathematically indistinguishable from $N-1$ decoys. |
| **INV-004: Key Image Double-Spend Immunity** | $I = x \cdot H_p(P)$ | Deterministic key image prevents duplicate spends across all blocks. |
| **INV-005: Bulletproofs+ Soundness** | Proof $\pi_{bp} \implies v \in [0, 2^{64}-1]$ | Zero trusted setup; non-negative range enforcement prevents overflow attacks. |
| **INV-006: Single-Slot BFT Finality** | Quorum $\ge 2f + 1$ with $f < n/3$ | Zero reorgs; forks are mathematically impossible. |
| **INV-007: Logarithmic Tail Emission** | $R(h) = \max\left(\frac{M - A(h-1)}{2^{19}}, 0.6\right)$ | Eliminates fee-starvation cliffs with a perpetual $0.6$ KPL/block reward floor. |

---

## 3. Binaries & CLI Wallet Usage

Precompiled binaries for Windows and Linux are available under [Releases](https://github.com/KitsuneTech1/kitsune-crypto/releases/tag/v0.1.0).

### Generating a Stealth Address
```bash
# Windows
kpl-cli.exe wallet generate

# Linux
./kpl-cli-linux-amd64 wallet generate
```

### Checking Live Validator Node Status
```bash
kpl-cli.exe status --node 192.168.1.201:9200
```

### Fast Multi-Chain Bridge Quotes & Deposits
```bash
# Get quote for 100 USDC on Base
kpl-cli.exe bridge quote base USDC 100

# Initiate deposit for 2 SOL on Solana
kpl-cli.exe bridge deposit solana SOL 2.0 <your_kpl_recipient_address>
```

### Broadcasting a Private Transaction
```bash
kpl-cli.exe tx submit <recipient_kpl_addr> <amount_atomic> <fee_atomic> --node 192.168.1.201:9200
```

---

## 4. One-Command Self-Hosting (Docker Compose)

Spin up a local node and telemetry dashboard with Docker:
```bash
docker compose up -d
```
Access the explorer at `http://localhost:8792`.

---

## 5. Formal Verification Suite

Run the mechanized invariant verification harness locally:
```bash
python -m verifier.invariants
```

---

## 5. Telemetry & Explorer

Launch the local web dashboard:
```bash
python dashboard/server.py
```
Open [http://127.0.0.1:8792](http://127.0.0.1:8792) to view live block height streaming, active mempool feed, and invariant verification status.

---

## 6. Documentation & Academic Papers

- [docs/whitepaper.pdf](docs/whitepaper.pdf): 4-page formal specification with Theorems 1, 2, and 3
- [docs/FAST_BRIDGES.md](docs/FAST_BRIDGES.md): Fast everyday multi-chain bridge guide
- [docs/BRIDGE_ATOMIC_SWAP.md](docs/BRIDGE_ATOMIC_SWAP.md): Monero scriptless atomic swap protocol

---

## 7. License

Open source under the [MIT License](LICENSE).
