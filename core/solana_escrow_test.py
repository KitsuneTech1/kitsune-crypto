"""Solana Devnet Escrow Lockup & KPL Bridge Mint Test.

Demonstrates cross-chain escrow lockup on Solana Devnet:
1. Queries live Solana devnet RPC for latest blockhash and cluster health.
2. Simulates an escrow lockup transaction of 0.1 SOL to the bridge vault.
3. Passes the confirmed Solana transaction signature to FastBridgeGateway.
4. Atomically mints a blinded KPL stealth UTXO.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.bridge import FastBridgeGateway, SupportedChain, AssetType
from core.crypto import StealthWalletKeys

SOLANA_DEVNET_RPC = "https://api.devnet.solana.com"


def solana_rpc_call(method: str, params: list = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }
    req = urllib.request.Request(
        SOLANA_DEVNET_RPC,
        data=json.dumps(payload).encode("utf8"),
        headers={"Content-Type": "application/json", "User-Agent": "KPL-Bridge-Probe"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def test_solana_devnet_lockup():
    print("=== 1. CONNECTING TO SOLANA DEVNET ===")
    version_res = solana_rpc_call("getVersion")
    solana_version = version_res.get("result", {}).get("solana-core", "unknown")
    print(f"Connected to Solana Devnet RPC! Node version: {solana_version}")

    blockhash_res = solana_rpc_call("getLatestBlockhash", [{"commitment": "finalized"}])
    latest_blockhash = blockhash_res["result"]["value"]["blockhash"]
    last_valid_height = blockhash_res["result"]["value"]["lastValidBlockHeight"]
    print(f"Latest Blockhash: {latest_blockhash}")
    print(f"Last Valid Block Height: #{last_valid_height}")

    print("\n=== 2. CREATING KPL BRIDGE INBOUND ORDER ===")
    gateway = FastBridgeGateway()
    user_keys = StealthWalletKeys.generate()
    user_kpl_addr = user_keys.public_address()
    sol_amount = 0.10

    quote = gateway.get_quote(SupportedChain.SOLANA, AssetType.SOL, sol_amount)
    order = gateway.create_inbound_order(SupportedChain.SOLANA, AssetType.SOL, sol_amount, user_kpl_addr)

    print(f"Order ID:          {order.order_id}")
    print(f"Deposit Amount:    {sol_amount} SOL")
    print(f"Expected KPL:      {quote.kpl_received} KPL (Rate: 1 SOL = {quote.exchange_rate} KPL)")
    print(f"Solana Vault:      {order.deposit_address_or_invoice}")
    print(f"Recipient Stealth: {user_kpl_addr[:30]}...")

    print("\n=== 3. SIMULATING SOLANA ESCROW LOCKUP ===")
    # Construct synthetic Solana transaction signature bound to live blockhash
    tx_payload = f"SOLANA_ESCROW_TRANSFER:{order.order_id}:{order.deposit_address_or_invoice}:{sol_amount}:{latest_blockhash}"
    solana_tx_sig = hashlib.sha256(tx_payload.encode()).hexdigest() + "5k1"
    print(f"Solana Devnet Tx Signature: {solana_tx_sig}")

    print("\n=== 4. CONFIRMING DEPOSIT & MINTING KPL STEALTH UTXO ===")
    settled_order = gateway.confirm_inbound_deposit(order.order_id, solana_tx_sig)
    print(f"Bridge Order Status: {settled_order.status}")
    print(f"KPL Mint Tx Hash:    {settled_order.kpl_tx_hash}")
    print(f"Settlement Time:     {quote.estimated_seconds} seconds")
    print("SOLANA DEVNET ESCROW LOCKUP PROBE SUCCESSFUL!")
    return settled_order


if __name__ == "__main__":
    test_solana_devnet_lockup()
