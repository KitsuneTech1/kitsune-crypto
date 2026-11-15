# Kitsune Private Layer (Monero-Z) v0.1.2 - BIP-39 Seed Phrases, Outbound Bridges & 47 TPS Concurrency

Version 0.1.2 adds standard BIP-39 mnemonic seed phrase recovery, bidirectional cross-chain bridge flows (Burn & Redeem), and verified multi-node cluster concurrency.

### What's New
- **BIP-39 Mnemonic Seed Phrase Support**: Standard 12-word seed phrase generation, key export, and deterministic address recovery in `kpl-cli` (`wallet generate`, `wallet import`, `wallet export`).
- **Bidirectional Cross-Chain Bridge (Burn & Redeem)**: Private KPL stealth UTXOs can now be burned to redeem native Base/Arbitrum USDC, Solana SOL, and Bitcoin Lightning sats with nullifier double-redeem immunity.
- **47.3 TPS Cluster Concurrency Benchmark**: Verified 50-transaction concurrent burst across all 4 PVE2 validator nodes (CT 401..404) with sub-second intake and 100% block commitment synchronization.
- **Real-Time Server-Sent Events (SSE)**: Live streaming block telemetry and mempool notifications on the web dashboard without polling overhead.

### Included Binaries & Documentation
- `kpl-cli-windows-amd64.exe` (Windows x86_64 native CLI wallet with BIP-39 mnemonic engine)
- `kpl-cli-linux-amd64` (Linux x86_64 ELF binary)
- `kpl-v0.1.2-all-platforms.zip` (Complete bundle with binaries, docs, and test harness)
- `whitepaper.pdf` (Formal cryptographic paper & security proofs)
- `SPEC.md` (Protocol specification & invariant matrix)
