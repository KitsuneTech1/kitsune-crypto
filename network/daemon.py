"""Kitsune Private Layer - Live Multi-Node BFT Consensus Daemon.

Runs an independent HTTP P2P validator daemon on each container node (CT 401..404).
Implements proposal generation, distributed vote collection, Quorum Certificate
assembly, and single-slot deterministic block commits.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.consensus import BlockHeader, QuorumCertificate, Validator, calculate_block_reward
from core.ledger import LedgerState

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [NODE-%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kpl")


class DaemonState:
    def __init__(self, node_id: str, node_index: int, total_nodes: int, peers: List[str]):
        self.node_id = node_id
        self.node_index = node_index
        self.total_nodes = total_nodes
        self.peers = peers
        self.quorum_threshold = (2 * total_nodes) // 3 + 1
        self.ledger = LedgerState()
        self.chain: List[BlockHeader] = []
        self.lock = threading.Lock()

        # Genesis block
        genesis_reward = calculate_block_reward(0)
        genesis = BlockHeader(
            height=0,
            prev_hash="0" * 64,
            merkle_root="0" * 64,
            timestamp=1700000000.0,
            proposer="GENESIS_ORACLE",
            reward=genesis_reward,
            quorum_cert=QuorumCertificate("genesis", 0, {f"node_{i}": "genesis_sig" for i in range(total_nodes)}),
        )
        self.chain.append(genesis)

    @property
    def current_height(self) -> int:
        with self.lock:
            return self.chain[-1].height

    @property
    def latest_hash(self) -> str:
        with self.lock:
            return self.chain[-1].hash()

    def propose_next_block(self) -> BlockHeader:
        with self.lock:
            height = self.chain[-1].height + 1
            prev_hash = self.chain[-1].hash()
        reward = calculate_block_reward(height * 600_000)
        import hashlib
        merkle = hashlib.sha256(f"merkle_h{height}_{time.time()}".encode("utf8")).hexdigest()
        return BlockHeader(
            height=height,
            prev_hash=prev_hash,
            merkle_root=merkle,
            timestamp=time.time(),
            proposer=self.node_id,
            reward=reward,
        )

    def validate_and_vote(self, proposal: BlockHeader) -> Optional[str]:
        with self.lock:
            if proposal.height != self.chain[-1].height + 1:
                return None
            if proposal.prev_hash != self.chain[-1].hash():
                return None
        import hashlib
        sig_payload = f"VOTE:{proposal.hash()}:{self.node_id}"
        return hashlib.sha256(sig_payload.encode("utf8")).hexdigest()

    def commit_block(self, block: BlockHeader, qc: QuorumCertificate) -> bool:
        with self.lock:
            if block.height != self.chain[-1].height + 1:
                return False
            if block.prev_hash != self.chain[-1].hash():
                return False
            if len(qc.signatures) < self.quorum_threshold:
                return False
            block.quorum_cert = qc
            self.chain.append(block)
            logger.info("Committed block #%d [hash=%s] with %d/%d QC signatures", block.height, block.hash()[:12], len(qc.signatures), self.total_nodes)
            return True


GLOBAL_STATE: Optional[DaemonState] = None


class DaemonHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status" or self.path == "/health":
            assert GLOBAL_STATE is not None
            with GLOBAL_STATE.lock:
                chain_summary = [
                    {"height": b.height, "hash": b.hash(), "proposer": b.proposer, "reward": b.reward}
                    for b in GLOBAL_STATE.chain[-10:]
                ]
                data = {
                    "node_id": GLOBAL_STATE.node_id,
                    "node_index": GLOBAL_STATE.node_index,
                    "height": GLOBAL_STATE.chain[-1].height,
                    "latest_hash": GLOBAL_STATE.chain[-1].hash(),
                    "quorum_threshold": GLOBAL_STATE.quorum_threshold,
                    "total_nodes": GLOBAL_STATE.total_nodes,
                    "peers": GLOBAL_STATE.peers,
                    "recent_blocks": chain_summary,
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode("utf8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        assert GLOBAL_STATE is not None
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode("utf8"))

        if self.path == "/propose":
            block = BlockHeader(
                height=payload["height"],
                prev_hash=payload["prev_hash"],
                merkle_root=payload["merkle_root"],
                timestamp=payload["timestamp"],
                proposer=payload["proposer"],
                reward=payload["reward"],
            )
            sig = GLOBAL_STATE.validate_and_vote(block)
            if sig:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "voted", "validator": GLOBAL_STATE.node_id, "signature": sig}).encode("utf8"))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "invalid_proposal"}).encode("utf8"))

        elif self.path == "/commit":
            block_data = payload["block"]
            qc_data = payload["qc"]
            block = BlockHeader(
                height=block_data["height"],
                prev_hash=block_data["prev_hash"],
                merkle_root=block_data["merkle_root"],
                timestamp=block_data["timestamp"],
                proposer=block_data["proposer"],
                reward=block_data["reward"],
            )
            qc = QuorumCertificate(
                block_hash=qc_data["block_hash"],
                height=qc_data["height"],
                signatures=qc_data["signatures"],
            )
            success = GLOBAL_STATE.commit_block(block, qc)
            if success:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "committed", "height": block.height}).encode("utf8"))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "commit_failed"}).encode("utf8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence routine HTTP access logging
        return


def consensus_worker_loop(state: DaemonState, target_blocks: int = 100):
    """Periodically drives consensus rounds when this node is the scheduled leader."""
    logger.info("Consensus loop started for node %s (index %d)", state.node_id, state.node_index)
    time.sleep(3.0)  # Wait for all peer daemons to spin up

    while True:
        try:
            current_h = state.current_height
            next_h = current_h + 1
            leader_index = next_h % state.total_nodes

            if state.node_index == leader_index:
                logger.info("Node %s is leader for height #%d. Proposing block...", state.node_id, next_h)
                proposal = state.propose_next_block()

                # Vote locally
                local_sig = state.validate_and_vote(proposal)
                votes: Dict[str, str] = {}
                if local_sig:
                    votes[state.node_id] = local_sig

                # Solicit votes from peers
                proposal_payload = json.dumps({
                    "height": proposal.height,
                    "prev_hash": proposal.prev_hash,
                    "merkle_root": proposal.merkle_root,
                    "timestamp": proposal.timestamp,
                    "proposer": proposal.proposer,
                    "reward": proposal.reward,
                }).encode("utf8")

                for peer in state.peers:
                    url = f"http://{peer}/propose"
                    try:
                        req = urllib.request.Request(url, data=proposal_payload, headers={"Content-Type": "application/json"}, method="POST")
                        with urllib.request.urlopen(req, timeout=2.0) as resp:
                            res_data = json.loads(resp.read().decode("utf8"))
                            if res_data.get("status") == "voted":
                                votes[res_data["validator"]] = res_data["signature"]
                    except Exception as e:
                        logger.debug("Failed to get vote from peer %s: %s", peer, e)

                logger.info("Collected %d/%d votes for height #%d", len(votes), state.quorum_threshold, next_h)

                if len(votes) >= state.quorum_threshold:
                    qc = QuorumCertificate(block_hash=proposal.hash(), height=next_h, signatures=votes)
                    # Commit locally
                    state.commit_block(proposal, qc)

                    # Broadcast commit to all peers
                    commit_payload = json.dumps({
                        "block": {
                            "height": proposal.height,
                            "prev_hash": proposal.prev_hash,
                            "merkle_root": proposal.merkle_root,
                            "timestamp": proposal.timestamp,
                            "proposer": proposal.proposer,
                            "reward": proposal.reward,
                        },
                        "qc": {
                            "block_hash": qc.block_hash,
                            "height": qc.height,
                            "signatures": qc.signatures,
                        },
                    }).encode("utf8")

                    for peer in state.peers:
                        url = f"http://{peer}/commit"
                        try:
                            req = urllib.request.Request(url, data=commit_payload, headers={"Content-Type": "application/json"}, method="POST")
                            with urllib.request.urlopen(req, timeout=2.0) as resp:
                                pass
                        except Exception as e:
                            logger.debug("Failed commit broadcast to peer %s: %s", peer, e)
                else:
                    logger.warning("Quorum not reached for height #%d (got %d, need %d)", next_h, len(votes), state.quorum_threshold)

            time.sleep(4.0)
        except Exception as e:
            logger.error("Error in consensus loop: %s", e)
            time.sleep(4.0)


def main():
    parser = argparse.ArgumentParser(description="KPL BFT Consensus Daemon")
    parser.add_argument("--node-id", required=True, help="Unique validator node ID")
    parser.add_argument("--node-index", type=int, required=True, help="Node index 0..N-1")
    parser.add_argument("--total-nodes", type=int, default=4, help="Total validators in mesh")
    parser.add_argument("--port", type=int, default=9200, help="Listen port")
    parser.add_argument("--peers", default="", help="Comma-separated peer IP:port list")
    args = parser.parse_args()

    peer_list = [p.strip() for p in args.peers.split(",") if p.strip()]

    global GLOBAL_STATE
    GLOBAL_STATE = DaemonState(
        node_id=args.node_id,
        node_index=args.node_index,
        total_nodes=args.total_nodes,
        peers=peer_list,
    )

    # Start consensus driver thread
    driver_thread = threading.Thread(target=consensus_worker_loop, args=(GLOBAL_STATE,), daemon=True)
    driver_thread.start()

    server = HTTPServer(("0.0.0.0", args.port), DaemonHTTPHandler)
    logger.info("KPL Daemon %s listening on 0.0.0.0:%d with peers %s", args.node_id, args.port, peer_list)
    server.serve_forever()


if __name__ == "__main__":
    main()
