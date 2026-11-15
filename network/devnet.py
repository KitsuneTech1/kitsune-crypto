"""Kitsune Private Layer - Multi-Node Devnet Orchestrator.

Simulates and coordinates 4 distributed BFT validator nodes in a peer-to-peer mesh.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.consensus import Validator
from network.node import DevnetNode


def setup_devnet(num_nodes: int = 4) -> List[DevnetNode]:
    base_port = 9100
    validators = [Validator(f"val_node_{i+1}", f"pubkey_node_{i+1}") for i in range(num_nodes)]

    nodes = []
    for i in range(num_nodes):
        port = base_port + (i + 1)
        peer_ports = [base_port + (j + 1) for j in range(num_nodes) if j != i]
        node = DevnetNode(
            node_id=f"val_node_{i+1}",
            port=port,
            validators=validators,
            peer_ports=peer_ports,
        )
        nodes.append(node)
    return nodes


def run_devnet_epoch(nodes: List[DevnetNode], blocks_to_produce: int = 5) -> dict:
    """Executes a multi-round distributed BFT consensus epoch across all nodes."""
    num_nodes = len(nodes)
    results = []

    for round_num in range(blocks_to_produce):
        # 1. Proposer selection (round-robin)
        proposer_idx = round_num % num_nodes
        proposer = nodes[proposer_idx]

        # 2. Proposer creates block proposal
        proposal = proposer.propose_next_block()

        # 3. Broadcast to all peers and collect votes
        votes = {}
        for node in nodes:
            sig = node.receive_proposal_and_vote(proposal)
            if sig:
                votes[node.node_id] = sig

        # 4. Proposer builds Quorum Certificate
        qc = None
        for val_id, sig in votes.items():
            candidate_qc = proposer.record_vote(proposal.hash(), val_id, sig)
            if candidate_qc:
                qc = candidate_qc
                break

        if not qc:
            raise RuntimeError(f"Consensus stalled at height {proposal.height}: quorum not reached")

        # 5. Broadcast QC to all nodes for deterministic commit
        for node in nodes:
            committed = node.commit_block(proposal, qc)
            if not committed:
                raise RuntimeError(f"Node {node.node_id} failed to commit block {proposal.height}")

        results.append({
            "height": proposal.height,
            "hash": proposal.hash(),
            "proposer": proposal.proposer,
            "votes_collected": len(qc.signatures),
            "quorum_required": proposer.quorum_threshold,
            "finalized": True,
        })

    return {
        "status": "HEALTHY",
        "nodes": num_nodes,
        "blocks_finalized": len(results),
        "latest_height": nodes[0].current_height,
        "chain_synchronized": all(n.current_height == nodes[0].current_height for n in nodes),
        "epoch_log": results,
    }


if __name__ == "__main__":
    nodes = setup_devnet(4)
    res = run_devnet_epoch(nodes, 5)
    print(f"Devnet consensus epoch complete: {res['blocks_finalized']} blocks finalized. Synced: {res['chain_synchronized']}")
