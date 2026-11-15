# Multi-Chain Fast Bridge Architecture
## Instant Liquidity Rails for Everyday Assets (USDC, USDT, SOL, BTC Lightning)
**Version:** 1.0.0
**Authors:** Kitsune Cryptographic Fleet & Moo
**Date:** November 2026

---

### 1. Overview & Practical Design Goals

While Monero-KPL atomic swaps provide maximum information-theoretic privacy, everyday users need fast, predictable, low-friction settlement in common assets:
- **EVM Layer-2s (Base, Arbitrum):** Native USDC & USDT deposits settling in 2–3 seconds with gas fees < $0.05.
- **Solana:** SPL-USDC & native SOL swaps completing in sub-2-second slots.
- **Bitcoin Lightning:** Submarine swaps allowing instant micro-deposits from any standard Lightning wallet.
- **Monero (XMR):** Native scriptless atomic swaps for maximal privacy.

---

### 2. Supported Routes & Settlement Speeds

| Route | Primary Assets | Estimated Settlement | Mechanism | Security Guarantee |
|---|---|---|---|---|
| **Base (EVM L2)** | USDC, USDT, ETH | ~3 seconds | Optimistic Relayer & Hashlock Vault | Instant L2 finality with non-custodial HTLC fallback |
| **Arbitrum (EVM L2)** | USDC, USDT, ETH | ~3 seconds | Optimistic Relayer & Hashlock Vault | Low-cost Nitro execution |
| **Solana** | SPL-USDC, SOL | ~2 seconds | SPL Token Lockup Program | High-throughput sub-second slot confirmation |
| **Bitcoin Lightning** | BTC (satoshis) | ~1 second | Submarine Swap (Boltz/Loop style) | Pure cryptographic preimage atomic swap |
| **Monero** | XMR | ~2 minutes | Scriptless Adaptor Signatures | Zero on-chain metadata or trace |

---

### 3. User Experience & Protocol Flow

#### Inbound Deposit (e.g. 50 USDC on Base -> KPL)
1. **Quote Request:** User requests a quote via CLI or web dashboard (`kpl-cli bridge quote base USDC 50`).
2. **Order Creation:** System provides a deposit address or EVM deposit contract handle.
3. **External Transfer:** User sends 50 USDC to the designated Base address.
4. **Instant Stealth Mint:** The bridge detects the transfer within 1 block, constructs a KPL stealth output ($P = H(rA)G + B$) with a blinded Pedersen commitment, and registers the transaction into the next single-slot BFT block.
5. **Ready to Spend:** User receives KPL in their wallet in under 5 seconds with zero transaction graph linkage.

#### Outbound Withdrawal (KPL -> USDC on Base)
1. User generates a private KPL transaction with an embedded EVM withdrawal ticket containing recipient `0x...` address.
2. The KPL validator network verifies the ring signature and key image.
3. The bridge relayer executes an immediate native USDC transfer to the user's `0x...` address on Base.

---

### 4. CLI Usage Examples

```bash
# Get quote for 50 USDC on Base
kpl-cli bridge quote base USDC 50

# Generate deposit order
kpl-cli bridge deposit base USDC 50 <your_kpl_address>

# Check order status
kpl-cli bridge status <order_id>
```

---

### 5. Implementation Status

- **Router Core:** [core/bridge.py](file:///C:/Users/Owner/projects/Kitsune/kitsune-crypto/core/bridge.py)
- **Monero Adaptor Swaps:** [docs/BRIDGE_ATOMIC_SWAP.md](file:///C:/Users/Owner/projects/Kitsune/kitsune-crypto/docs/BRIDGE_ATOMIC_SWAP.md)
- **Web Telemetry Integration:** Accessible directly via `http://127.0.0.1:8792/api/bridge`
