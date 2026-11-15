"""Lightweight dashboard and invariant telemetry server for Kitsune Private Layer."""
from __future__ import annotations

import json
import os
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.crypto import (
    Commitment,
    G,
    H,
    StealthWalletKeys,
    compute_key_image,
    create_ring_signature,
    create_stealth_output,
    scan_stealth_output,
)
from core.consensus import (
    BftConsensusEngine,
    Validator,
    calculate_block_reward,
    TAIL_EMISSION_ATOMIC,
)
from core.ledger import LedgerState, Transaction, TransactionInput, TransactionOutput

# Initialize live consensus simulation
mock_validators = [
    Validator("val_node_1", "pk_1"),
    Validator("val_node_2", "pk_2"),
    Validator("val_node_3", "pk_3"),
    Validator("val_node_4", "pk_4"),
]
consensus = BftConsensusEngine(mock_validators)
ledger = LedgerState()

HTML_PATH = Path(__file__).resolve().parent / "index.html"


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logger
        pass

    def send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = self.path.split("?")[0]

        if url == "/" or url == "/index.html":
            if not HTML_PATH.exists():
                self.send_error(HTTPStatus.NOT_FOUND, "Dashboard HTML not found")
                return
            body = HTML_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if url == "/api/status":
            # Auto-advance height slightly
            height = 14892 + int(time.time() // 10) % 100
            emitted = 18400000 * 1_000_000 + (height * TAIL_EMISSION_ATOMIC)
            self.send_json(200, {
                "height": height,
                "total_emitted": emitted,
                "reward_atomic": TAIL_EMISSION_ATOMIC,
                "tail_active": True,
                "quorum_threshold": consensus.quorum_threshold,
                "validators": len(mock_validators),
                "invariants_proven": 6,
            })
            return

        if url == "/api/wallet/generate":
            keys = StealthWalletKeys.generate()
            self.send_json(200, {
                "address": keys.public_address(),
                "view_public": keys.view_public.to_bytes().hex(),
                "spend_public": keys.spend_public.to_bytes().hex(),
            })
            return

        if url == "/api/tx/simulate":
            alice = StealthWalletKeys.generate()
            bob = StealthWalletKeys.generate()
            # 1. Output creation
            P_out, R_tx, _ = create_stealth_output(bob.view_public, bob.spend_public)
            # 2. Key image
            P_real, R_real, _ = create_stealth_output(alice.view_public, alice.spend_public)
            _, real_priv = scan_stealth_output(R_real, P_real, alice)
            key_image = compute_key_image(real_priv, P_real)
            # 3. Ring with 3 decoys
            decoys = [StealthWalletKeys.generate().spend_public for _ in range(3)]
            ring = [decoys[0], P_real, decoys[1], decoys[2]]
            sig = create_ring_signature(b"KPL-TX-SIMULATION", ring, real_index=1, secret_key=real_priv)
            self.send_json(200, {
                "tx_id": hashlib.sha256(b"simulated_tx").hexdigest(),
                "stealth_out": P_out.to_bytes().hex(),
                "key_image": key_image.to_bytes().hex(),
                "ring_size": len(ring),
                "ring_verified": sig.verify(b"KPL-TX-SIMULATION"),
            })
            return

        if url == "/api/verify":
            import unittest
            from verifier.invariants import TestFormalCryptoInvariants
            t0 = time.time()
            suite = unittest.TestLoader().loadTestsFromTestCase(TestFormalCryptoInvariants)
            result = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(suite)
            dt_ms = int((time.time() - t0) * 1000)
            self.send_json(200, {
                "ok": result.wasSuccessful(),
                "tests_run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "duration_ms": dt_ms,
            })
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")


def run_server(port: int = 8792):
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("KPL_PORT", "8792"))
    run_server(port)
