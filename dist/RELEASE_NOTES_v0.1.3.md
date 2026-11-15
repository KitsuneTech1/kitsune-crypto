# Kitsune Private Layer (Monero-Z) v0.1.3 - Cold Storage Paper Wallets, Autonomous Relayers & Hostile Fuzzing

Version 0.1.3 introduces air-gapped paper wallet generation, autonomous cross-chain relayer daemons, and formal adversarial invariant fuzzing.

### Highlights
- **Air-Gapped Cold Storage (`kpl-cli wallet paper`)**: Generate printable, air-gapped HTML cold storage certificates with dark-themed QR codes, dual-key stealth addresses, and 12-word BIP-39 recovery phrases.
- **Autonomous Multi-Sig Relayer Daemon (`relayer_daemon.py`)**: Autonomous 3-of-4 threshold relayer mesh running on validator containers, coordinating Byzantine fault-tolerant vault payout authorization.
- **155-Trial Cryptographic Invariant Fuzzer (`verifier/fuzzer.py`)**: Randomized adversarial mutation harness targeting Curve25519 stealth bit-flips, CLSAG scalar corruption, commitment inflation deltas, and key-image collisions (100.0% rejection rate).
- **Outbound Bridge (Burn & Redeem)**: Burn private KPL stealth UTXOs to redeem native Base/Arbitrum USDC and Solana SOL with nullifier double-redeem immunity.

### Included Assets
- `kpl-cli-windows-amd64.exe` (Windows x86_64 CLI wallet with cold storage & mnemonic engine)
- `kpl-cli-linux-amd64` (Linux x86_64 ELF binary)
- `kpl-v0.1.3-all-platforms.zip` (Complete distribution archive)
- `whitepaper.pdf` (Formal cryptographic paper & security proofs)
- `SPEC.md` (Protocol specification & invariant matrix)
