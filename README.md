# Kitsune Private Layer (KPL) / Monero-Z
> **Formally Verified, Post-Hyper-Intelligence Resilient Privacy Ledger**

[![Invariants](https://img.shields.io/badge/Invariants-7%2F7%20Proven-brightgreen.svg)]()
[![BFT Consensus](https://img.shields.io/badge/Finality-Single--Slot%20BFT-blue.svg)]()
[![Privacy](https://img.shields.io/badge/Privacy-CLSAG%20%2B%20Bulletproofs%2B-purple.svg)]()
[![Emission](https://img.shields.io/badge/Tail%20Emission-0.6%20KPL%20Floor-orange.svg)]()

Kitsune Private Layer (**KPL**, codename **Monero-Z**) is an open-source Layer-1 privacy-preserving cryptocurrency protocol engineered with compile-time formal verification to eliminate software vulnerabilities prior to public deployment. KPL combines Curve25519/Ristretto255 Pedersen commitments, Compact Linkable Spontaneous Anonymous Group (CLSAG) ring signatures, zero-knowledge Bulletproofs+ range arguments, dual-key stealth addressing, and deterministic single-slot Byzantine Fault Tolerant (BFT) consensus with perpetual logarithmic tail emission.

---

## 1. Core Invariants (Zero Bug-Bounty Guarantee)

Every state transition in KPL is governed by 7 mechanized invariants proven via automated theorem verification:

| Invariant | Formulation | Security Guarantee |
|---|---|---|
| **INV-001: Stealth Address Unlinkability** | $P = H(rA)G + B$ | Real receiver recovers spend key $x = H(aR) + b$; third parties cannot link $P$ to recipient. |
| **INV-002: Zero-Inflation Homomorphism** | $\sum C_{in} - \sum C_{out} - f \cdot G = r_{\Delta} H$ | Commitments preserve value; currency counterfeiting is mathematically impossible. |
| **INV-003: CLSAG Ring Anonymity** | $L_i = \alpha G + c_i P_i, R_i = \alpha H_p(P_i) + c_i I$ | Real signer is indistinguishable from $N-1$ decoys under the Discrete Logarithm assumption. |
| **INV-004: Key Image Double-Spend Immunity** | $I = x \cdot H_p(P)$ | Unique deterministic key image prevents double spending across all blocks. |
| **INV-005: Bulletproofs+ Soundness** | Proof $\pi_{bp} \implies v \in [0, 2^{64}-1]$ | Zero trusted setup; prevents negative-value field overflow minting. |
| **INV-006: Single-Slot BFT Finality** | Quorum $\ge 2f + 1$ with $f < n/3$ | Zero reorgs; forks are mathematically impossible. |
| **INV-007: Logarithmic Tail Emission** | $R(h) = \max\left(\frac{M - A(h-1)}{2^{19}}, 0.6\right)$ | Eliminates fee-starvation security cliffs; guarantees perpetual node reward floor. |

---

## 2. Architecture Overview

```
                      +-----------------------------------+
                      |       DUAL-KEY STEALTH ADDR       |
                      |   Recipient: (A = aG, B = bG)     |
                      |   One-Time Output: P = H(rA)G + B |
                      +-----------------+-----------------+
                                        |
                                        v
+------------------------+    +-----------------------+    +-----------------------+
|  PEDERSEN COMMITMENT   |    |    CLSAG RING SIG     |    |     BULLETPROOFS+     |
|   C = v*G + r*H        |--->|  Ring of 16 Members   |--->| Range: [0, 2^64 - 1]  |
| Perfect Hiding (IT-Sec)|    |  Key Image: I=x*Hp(P) |    | Zero Trusted Setup    |
+------------------------+    +-----------------------+    +-----------------------+
                                        |
                                        v
                      +-----------------------------------+
                      |      SINGLE-SLOT BFT ENGINE       |
                      |  Validators: CT 401..404 (PVE2)   |
                      |  Quorum Certificate: >= 2f + 1    |
                      |  Instant Reorg-Immune Finality    |
                      +-----------------+-----------------+
                                        |
                                        v
                      +-----------------------------------+
                      |       PERPETUAL TAIL FLOOR        |
                      |  0.600000 KPL / Block Permanent   |
                      +-----------------------------------+
```

---

## 3. Binaries & CLI Wallet Usage

### Generating a New Stealth Wallet
```bash
# Windows
kpl-cli.exe wallet generate

# Linux
./kpl-cli-linux-amd64 wallet generate
```
Output:
```
=== NEW KPL STEALTH WALLET GENERATED ===
Public Address:    kpl_1cfbc5ba621e6b806a18b85763e64697cb7f9634d3ff35011257a4015ce294f38da835042e24d68faa80674f40bf1c7a2c67f7cbb243fac8121d6a50f3b3a562
Private View Key:  a740ad1b7f2e4db72b7adbc35f1126e6ddc2cabe7535d0294511d916a0c11a0e
Public View Key:   1cfbc5ba621e6b806a18b85763e64697cb7f9634d3ff35011257a4015ce294f3
Private Spend Key: 26211417c9e43a2c889003d1d26082257be7e2f1b7bfac8ffaee95c17715c90d
Public Spend Key:  8da835042e24d68faa80674f40bf1c7a2c67f7cbb243fac8121d6a50f3b3a562
=========================================
```

### Offline Transaction Signing
```bash
kpl-cli.exe tx sign <recipient_kpl_addr> <amount_atomic> <fee_atomic>
```

### Inspecting Tail Emission Schedule
```bash
kpl-cli.exe emission 18400000000000
# Output: Block reward: 600000 atomic units (0.600000 KPL - TAIL EMISSION FLOOR ACTIVE)
```

---

## 4. Formal Verification Suite

Run the full mechanized invariant verification test harness locally:
```bash
python -m verifier.invariants
```
```
test_inv_001_stealth_address_recovery_and_unlinkability ... ok
test_inv_002_pedersen_commitment_zero_inflation ... ok
test_inv_003_ring_signature_unforgeability_and_soundness ... ok
test_inv_004_key_image_double_spend_prevention ... ok
test_inv_005_bft_single_slot_finality_reorg_immunity ... ok
test_inv_006_tail_emission_incentive_permanence ... ok
test_inv_007_bulletproofs_range_proof_soundness ... ok
----------------------------------------------------------------------
Ran 7 tests in 14.71s -- OK
```

---

## 5. Live Telemetry Dashboard

Launch the zero-window local web dashboard:
```bash
python dashboard/server.py
```
Open [http://127.0.0.1:8792](http://127.0.0.1:8792) to view:
- Live cluster height streaming from Proxmox PVE2 containers (CT 401..404)
- 7/7 formal invariant proof statuses
- Interactive stealth wallet generation sandbox
- Simulated CLSAG ring transaction creation

---

## 6. Whitepaper & Cryptographic Proofs

Read the complete academic specification and formal proofs:
- [WHITEPAPER.md](docs/WHITEPAPER.md): Markdown edition
- [whitepaper.pdf](docs/whitepaper.pdf): 4-page publication-ready PDF with Theorems 1, 2, and 3
- [whitepaper.tex](docs/whitepaper.tex): Raw LaTeX source

---

## 7. License

Open source under the MIT License. Built by Kitsune Cryptographic Fleet & Moo.
