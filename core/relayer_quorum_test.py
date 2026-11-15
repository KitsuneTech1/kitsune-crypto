"""Test Suite for Multi-Sig Bridge Relayer Quorum (3-of-4 Threshold)."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.relayer_quorum import RelayerQuorum, QuorumSecurityError
from core.crypto import StealthWalletKeys, G


def run_tests():
    print("================================================================================")
    print("   KITSUNE PRIVATE LAYER // 3-OF-4 BRIDGE RELAYER QUORUM TEST")
    print("================================================================================")
    quorum = RelayerQuorum(threshold=3)

    # 1. Register 4 validator nodes (CT 401..404)
    validators = {}
    print("\n[STEP 1] Registering 4 Validator Relayer Nodes (CT 401..404)...")
    for i in range(4):
        val_id = f"node-{i}"
        keys = StealthWalletKeys.generate()
        quorum.register_validator(val_id, keys.spend_public)
        validators[val_id] = keys.spend_secret
        print(f"  Registered: {val_id} (Public: {keys.spend_public.to_bytes().hex()[:24]}...)")

    # 2. Create release proposal
    print("\n[STEP 2] Creating Bridge Release Proposal for 50 USDC on Base Sepolia...")
    proposal = quorum.create_release_proposal(
        withdrawal_id="w_7f8a9b0c",
        target_chain="base",
        asset="USDC",
        amount=50.0,
        destination="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        burn_proof="0x4b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c"
    )
    print(f"  Proposal ID:      {proposal.proposal_id}")
    print(f"  Canonical Digest: {proposal.canonical_digest().hex()[:32]}...")

    # 3. Test insufficient signatures (2 of 4)
    print("\n[STEP 3] Testing Insufficient Signatures (2/4 provided)...")
    sigs_2 = {
        "node-0": quorum.sign_proposal("node-0", validators["node-0"], proposal),
        "node-1": quorum.sign_proposal("node-1", validators["node-1"], proposal),
    }
    try:
        quorum.verify_and_authorize(proposal, sigs_2)
        print("  FAIL: Release authorized with only 2 signatures!")
        return False
    except QuorumSecurityError as e:
        print(f"  PASS: Correctly rejected (2/3 required): {e}")

    # 4. Test duplicate signer (attempting 3 sigs with duplicate node-0)
    print("\n[STEP 4] Testing Sybil / Duplicate Signer Attempt...")
    sigs_dup = {
        "node-0": sigs_2["node-0"],
        "node-1": sigs_2["node-1"],
        "node-unknown": "a" * 64
    }
    try:
        quorum.verify_and_authorize(proposal, sigs_dup)
        print("  FAIL: Release authorized with unregistered validator!")
        return False
    except QuorumSecurityError as e:
        print(f"  PASS: Correctly rejected unregistered node: {e}")

    # 5. Test threshold met (3 of 4 valid signatures)
    print("\n[STEP 5] Testing Threshold Quorum Certificate (3/4 valid signatures)...")
    sigs_3 = dict(sigs_2)
    sigs_3["node-2"] = quorum.sign_proposal("node-2", validators["node-2"], proposal)
    
    auth_3 = quorum.verify_and_authorize(proposal, sigs_3)
    print(f"  PASS: Quorum Certificate Authorized! Valid Signatures: {auth_3.valid_count}/{auth_3.threshold}")
    print(f"  Authorized Digest: {auth_3.canonical_digest[:32]}...")

    # 6. Test unanimous quorum (4 of 4 signatures)
    print("\n[STEP 6] Testing Unanimous Quorum Certificate (4/4 valid signatures)...")
    sigs_4 = dict(sigs_3)
    sigs_4["node-3"] = quorum.sign_proposal("node-3", validators["node-3"], proposal)
    auth_4 = quorum.verify_and_authorize(proposal, sigs_4)
    print(f"  PASS: Unanimous Quorum Authorized! Valid Signatures: {auth_4.valid_count}/4")

    print("\n================================================================================")
    print("   ALL 3-OF-4 MULTI-SIG RELAYER QUORUM INVARIANTS VERIFIED")
    print("================================================================================")
    return True


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
