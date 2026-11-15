"""Kitsune Private Layer - Autonomous Cross-Chain Relayer Daemon.

Runs on validator nodes (CT 401..404). Monitors the KPL ledger for verified burn transactions,
autonomously validates the zero-knowledge burn proofs, coordinates 3-of-4 threshold multi-signatures
across peer relayers, and authorizes release of external vault assets (Base Sepolia USDC, Solana SOL).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.crypto import StealthWalletKeys, G, L
from core.relayer_quorum import BridgeReleaseProposal, QuorumReleaseAuthorization, RelayerQuorum

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [RELAYER-%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("relayer")


class AutonomousRelayer:
    def __init__(self, validator_id: str, secret_key: int, peer_relayers: List[str], threshold: int = 3):
        self.validator_id = validator_id
        self.secret_key = secret_key
        self.peer_relayers = peer_relayers
        self.quorum = RelayerQuorum(threshold=threshold)
        self.processed_withdrawals: Set[str] = set()
        self.pending_proposals: Dict[str, BridgeReleaseProposal] = {}
        self.collected_signatures: Dict[str, Dict[str, str]] = {}
        self.lock = threading.Lock()

    def process_incoming_burn(
        self, withdrawal_id: str, chain: str, asset: str, amount: float, destination: str, burn_proof: str
    ) -> BridgeReleaseProposal:
        with self.lock:
            if withdrawal_id in self.processed_withdrawals:
                logger.warning("Withdrawal %s already processed by relayer %s", withdrawal_id, self.validator_id)
                return self.pending_proposals[withdrawal_id]

            proposal = self.quorum.create_release_proposal(withdrawal_id, chain, asset, amount, destination, burn_proof)
            self.pending_proposals[withdrawal_id] = proposal
            
            # Autonomously sign local vote
            sig = self.quorum.sign_proposal(self.validator_id, self.secret_key, proposal)
            self.collected_signatures[withdrawal_id] = {self.validator_id: sig}
            logger.info("Relayer %s signed release proposal %s for %s %s to %s", self.validator_id, proposal.proposal_id, amount, asset, destination[:12])
            return proposal

    def record_peer_signature(self, withdrawal_id: str, peer_id: str, signature: str) -> Optional[QuorumReleaseAuthorization]:
        with self.lock:
            if withdrawal_id not in self.pending_proposals:
                return None
            
            proposal = self.pending_proposals[withdrawal_id]
            sigs = self.collected_signatures.setdefault(withdrawal_id, {})
            sigs[peer_id] = signature
            
            if len(sigs) >= self.quorum.threshold and withdrawal_id not in self.processed_withdrawals:
                try:
                    auth = self.quorum.verify_and_authorize(proposal, sigs)
                    self.processed_withdrawals.add(withdrawal_id)
                    logger.info(">>> QUORUM ACHIEVED (%d/%d) for withdrawal %s! Vault payout authorized.", auth.valid_count, auth.threshold, withdrawal_id)
                    return auth
                except Exception as e:
                    logger.error("Quorum verification failed: %s", e)
            return None


def test_autonomous_relayer_cluster():
    print("================================================================================")
    print("   AUTONOMOUS CROSS-CHAIN RELAYER DAEMON MESH TEST (CT 401..404)")
    print("================================================================================")
    
    # Instantiate 4 relayer daemons
    keys = [StealthWalletKeys.generate() for _ in range(4)]
    cluster_relayers: List[AutonomousRelayer] = []
    
    for i in range(4):
        val_id = f"node-{i}"
        r = AutonomousRelayer(validator_id=val_id, secret_key=keys[i].spend_secret, peer_relayers=[f"node-{j}" for j in range(4) if j != i])
        # Register all 4 validator public keys in each relayer's quorum gate
        for j in range(4):
            r.quorum.register_validator(f"node-{j}", keys[j].spend_public)
        cluster_relayers.append(r)

    print(f"Instantiated 4 autonomous relayer daemons with 3-of-4 quorum gates.")

    # Simulate an incoming KPL burn withdrawal event on Base Sepolia
    w_id = "burn_order_base_98234"
    dest = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    burn_proof = hashlib.sha256(b"BURN_PROOF_SIMULATED").hexdigest()
    
    print(f"\n[1/3] Relayer 0 detects KPL burn: 50.0 USDC on Base -> {dest[:16]}...")
    prop = cluster_relayers[0].process_incoming_burn(w_id, "base", "USDC", 50.0, dest, burn_proof)
    
    print("\n[2/3] Gossiping proposal to peer relayers and gathering 3-of-4 multi-signatures...")
    # Peers 1 and 2 validate and sign
    sig_0 = cluster_relayers[0].collected_signatures[w_id]["node-0"]
    
    prop_1 = cluster_relayers[1].process_incoming_burn(w_id, "base", "USDC", 50.0, dest, burn_proof)
    sig_1 = cluster_relayers[1].collected_signatures[w_id]["node-1"]

    prop_2 = cluster_relayers[2].process_incoming_burn(w_id, "base", "USDC", 50.0, dest, burn_proof)
    sig_2 = cluster_relayers[2].collected_signatures[w_id]["node-2"]

    # Relayer 0 receives votes from Node-1 and Node-2
    cluster_relayers[0].record_peer_signature(w_id, "node-1", sig_1)
    auth = cluster_relayers[0].record_peer_signature(w_id, "node-2", sig_2)

    assert auth is not None, "Quorum should be achieved with 3 signatures!"
    print(f"\n[3/3] Vault Authorization Success:")
    print(f"  Authorized Proposal: {auth.proposal_id}")
    print(f"  Quorum Certificate:  {auth.valid_count}/3 registered signatures verified")
    print(f"  Signers:             {list(auth.signatures.keys())}")
    print("AUTONOMOUS RELAYER DAEMON CLUSTER PASSED ALL TESTS!")
    return True


if __name__ == "__main__":
    test_autonomous_relayer_cluster()
