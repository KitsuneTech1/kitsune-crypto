"""Kitsune Private Layer - Multi-Node P2P BFT Devnet Node.

Implements asynchronous gossip, proposal verification, vote gathering,
and deterministic single-slot block finalization across independent nodes.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Set

from core.consensus import (
    BlockHeader,
    QuorumCertificate,
    Validator,
    calculate_block_reward,
)
from core.ledger import LedgerState, Transaction

logger = logging.getLogger("kpl.node")


class DevnetNode:
    """Independent BFT validator node running in devnet mesh."""

    def __init__(self, node_id: str, port: int, validators: List[Validator], peer_ports: List[int]):
        self.node_id = node_id
        self.port = port
        self.peer_ports = peer_ports
        self.validators = {v.address: v for v in validators}
        self.quorum_threshold = (2 * len(validators)) // 3 + 1

        self.ledger = LedgerState()
        self.chain: List[BlockHeader] = []
        self.mempool: List[Transaction] = []
        self.staged_votes: Dict[str, Dict[str, str]] = {}  # block_hash -> {validator: sig}

        # Genesis setup
        genesis_reward = calculate_block_reward(0)
        genesis = BlockHeader(
            height=0,
            prev_hash="0" * 64,
            merkle_root="0" * 64,
            timestamp=1700000000.0,
            proposer="GENESIS_ORACLE",
            reward=genesis_reward,
            quorum_cert=QuorumCertificate("genesis", 0, {v.address: "genesis_sig" for v in validators}),
        )
        self.chain.append(genesis)
        self.is_running = False

    @property
    def current_height(self) -> int:
        return self.chain[-1].height

    @property
    def latest_hash(self) -> str:
        return self.chain[-1].hash()

    def propose_next_block(self) -> BlockHeader:
        """Constructs proposed block header from mempool transactions."""
        reward = calculate_block_reward(self.current_height * 600_000)
        block = BlockHeader(
            height=self.current_height + 1,
            prev_hash=self.latest_hash,
            merkle_root=f"merkle_root_h{self.current_height + 1}",
            timestamp=1700000000.0 + (self.current_height + 1) * 10,
            proposer=self.node_id,
            reward=reward,
        )
        return block

    def receive_proposal_and_vote(self, proposal: BlockHeader) -> Optional[str]:
        """Validates incoming proposal against consensus invariants and emits vote signature."""
        if proposal.height != self.current_height + 1:
            return None
        if proposal.prev_hash != self.latest_hash:
            return None
        if proposal.proposer not in self.validators:
            return None

        import hashlib
        sig_payload = f"VOTE:{proposal.hash()}:{self.node_id}"
        sig = hashlib.sha256(sig_payload.encode("utf8")).hexdigest()
        return sig

    def record_vote(self, block_hash: str, validator_id: str, signature: str) -> Optional[QuorumCertificate]:
        """Records vote from peer. If quorum threshold reached, returns new QuorumCertificate."""
        if block_hash not in self.staged_votes:
            self.staged_votes[block_hash] = {}
        self.staged_votes[block_hash][validator_id] = signature

        if len(self.staged_votes[block_hash]) >= self.quorum_threshold:
            qc = QuorumCertificate(
                block_hash=block_hash,
                height=self.current_height + 1,
                signatures=dict(self.staged_votes[block_hash]),
            )
            return qc
        return None

    def commit_block(self, block: BlockHeader, qc: QuorumCertificate) -> bool:
        """Applies finalized block and QC to local state machine."""
        if not qc.is_valid(self.quorum_threshold):
            return False
        if qc.block_hash != block.hash():
            return False
        if block.height != self.current_height + 1:
            return False

        block.quorum_cert = qc
        self.chain.append(block)
        self.staged_votes.pop(block.hash(), None)
        return True
