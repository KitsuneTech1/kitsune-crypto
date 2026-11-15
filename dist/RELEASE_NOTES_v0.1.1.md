# Kitsune Private Layer (Monero-Z) v0.1.1 - Fast Multi-Chain Liquidity & Settlement

Version 0.1.1 introduces direct multi-chain liquidity bridges, live cross-chain settlement tracking, and automated devnet escrow tooling.

### Highlights
- **Direct Solana Devnet Escrow Lockup (`kpl-cli bridge solana-lock`)**: Lock SOL on Solana Devnet and atomically receive blinded KPL stealth UTXOs directly from the command line.
- **Base Sepolia (EVM L2) Escrow Verification**: Verified 3-second optimistic settlement for ERC-20 (USDC) deposits via event log parsing.
- **Live Settlement Progress Tracker**: Real-time 3-step progress bar on the web dashboard (Order -> Chain Proof -> KPL Mint).
- **Cryptographic Receipt Export**: Verifiable, download-ready `receipt.json` proofs for all confirmed transactions and bridge mints.
- **BFT Consensus & Invariants**: 7/7 formal mathematical invariants mathematically verified; 4-node PVE2 container cluster actively producing blocks.

### Included Binaries & Documentation
- `kpl-cli-windows-amd64.exe` (Windows x86_64 native CLI wallet & bridge tool)
- `kpl-cli-linux-amd64` (Linux x86_64 ELF binary)
- `whitepaper.pdf` (Formal cryptographic paper & security proofs)
- `SPEC.md` (Protocol specification & invariant matrix)
