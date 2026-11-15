# Monero (XMR) <-> Kitsune Private Layer (KPL) Trustless Atomic Swap Specification
## Cross-Chain Adaptor Signature Protocol (Scriptless Scripts)
**Version:** 1.0.0
**Authors:** Kitsune Cryptographic Fleet & Moo
**Date:** November 2026

---

### 1. Executive Summary

This specification defines the cryptographic construction and state machine for **trustless, peer-to-peer cross-chain atomic swaps** between Monero (XMR) and Kitsune Private Layer (KPL). Traditional cross-chain bridges rely on centralized multisig federations or wrapped-token smart contracts, which represent multi-billion-dollar honeypots for computational adversaries. 

Because both Monero and KPL share the identical **Curve25519 / Ed25519 prime-order group** ($\mathbb{F}_L$, $L = 2^{252} + 27742317777372353535851937790883648493$), swaps are executed via **Scriptless Script Adaptor Signatures**. No on-chain script interpreter is required; atomic execution is enforced purely through discrete logarithm extraction.

---

### 2. Cryptographic Construction

#### 2.1 Group & Hash Parameters
- Base Group: Curve25519 with standard base point $G$.
- Adaptor Secret: $t \xleftarrow{\$} \mathbb{F}_L$, with Adaptor Point $T = t \cdot G$.
- Identity: Party A (holds $X$ XMR, wants $K$ KPL), Party B (holds $K$ KPL, wants $X$ XMR).

#### 2.2 Adaptor Signature Mechanics
An adaptor signature is an incomplete Schnorr/CLSAG signature that can be verified as valid with respect to statement $T$, but requires scalar $t = \log_G(T)$ to be converted into a valid on-chain signature:
1. Prover generates adaptor signature $(\hat{s}, c)$ where:
   $$\hat{s} \cdot G = R + c \cdot P - T$$
2. Upon learning $t$, the verifier completes the signature:
   $$s = \hat{s} + t \pmod L$$
3. Anyone observing both $(\hat{s}, c)$ and valid $(s, c)$ extracts the secret witness:
   $$t = s - \hat{s} \pmod L$$

---

### 3. Protocol Execution Flow

```
   Party A (Holds XMR)                               Party B (Holds KPL)
           |                                                  |
           |---- 1. Exchange Public Keys & Adaptor Point T -->|
           |                                                  |
           |---- 2. Lock XMR in 2-of-2 Multisig ------------->| (Broadcast on Monero)
           |                                                  |
           |<--- 3. Lock KPL in 2-of-2 Multisig --------------| (Broadcast on KPL)
           |                                                  |
           |<--- 4. Send KPL Adaptor Signature (\hat{s}_B) ---|
           |                                                  |
           |==== 5. Party A Claims KPL with Secret t =========| (Broadcast on KPL)
           |     (Reveals scalar t on-chain)                  |
           |                                                  |
           |     6. Party B extracts t = s_A - \hat{s}_B      |
           |<--- 7. Party B Claims XMR using scalar t --------| (Broadcast on Monero)
           |                                                  |
     [SWAP COMPLETED]                                   [SWAP COMPLETED]
```

#### Step-by-Step State Transitions:
1. **Public Key Agreement:** Party A generates $a_1, A_1 = a_1 G$ and secret adaptor scalar $t, T = tG$. Party B generates $b_1, B_1 = b_1 G$.
2. **Monero Lock Transaction:** Party A funds a Monero 2-of-2 stealth address $P_{\text{xmr}} = (A_1 + B_1)$. A refund transaction $TX_{\text{xmr-refund}}$ is pre-signed with locktime $T_{\text{xmr}} = 24 \text{ hours}$.
3. **KPL Lock Transaction:** Party B funds a KPL 2-of-2 address $P_{\text{kpl}} = (A_2 + B_2)$. A refund transaction $TX_{\text{kpl-refund}}$ is pre-signed with shorter locktime $T_{\text{kpl}} = 12 \text{ hours}$.
4. **Adaptor Exchange:** Party B sends an adaptor signature $\hat{s}_B$ for $TX_{\text{kpl-claim}}$ encrypted under statement $T$.
5. **KPL Settlement (Atomic Trigger):** Party A verifies $\hat{s}_B$, unlocks $TX_{\text{kpl-claim}}$ by adding $t$, and broadcasts to the KPL network.
6. **Witness Extraction & Monero Settlement:** Party B inspects the finalized KPL block, reads $s_A$, computes $t = s_A - \hat{s}_B$, uses $t$ to sign $TX_{\text{xmr-claim}}$, and finalizes the Monero withdrawal.

---

### 4. Failure Modes & Invariant Proofs

#### Invariant INV-SWAP-SAFETY (Zero Counterparty Risk)
- **Case 1: Party B aborts before Step 3.** Party A waits for timelock $T_{\text{xmr}}$ and reclaims all XMR. Party B spent zero funds.
- **Case 2: Party A aborts before Step 5.** Party B waits for timelock $T_{\text{kpl}}$ (12h) and reclaims all KPL. Party A then reclaims XMR at 24h. No funds lost.
- **Case 3: Party A claims KPL at Step 5.** Because $T_{\text{kpl}} < T_{\text{xmr}}$ (12h < 24h), Party B has a guaranteed 12-hour window to extract $t$ and claim XMR before the Monero refund lock expires.

#### Invariant INV-SWAP-PRIVACY (Off-Chain Indistinguishability)
- Adaptor signatures produce standard Schnorr and CLSAG ring signatures on both ledgers.
- Third-party blockchain observers cannot distinguish an atomic swap from an ordinary Monero or KPL transfer. No cross-chain transaction IDs or contracts are visible.

---

### 5. Implementation Roadmap

- **`crates/kpl-swap`:** Native Rust library implementing Curve25519 adaptor signature generation and extraction.
- **`kpl-cli swap init` / `kpl-cli swap respond`:** Interactive peer-to-peer CLI swap coordinator over encrypted nostr/libvirt channels.
