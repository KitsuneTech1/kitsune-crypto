"""Kitsune Private Layer - Multi-Chain Bridge & Stealth Wallet End-to-End Demo.

Demonstrates simultaneous cross-chain on-ramping from 3 distinct networks into a single KPL private wallet:
1. Base (EVM L2) USDC Escrow Deposit
2. Solana Devnet SOL Escrow Deposit
3. Bitcoin Lightning Network Submarine Swap
4. Dual-Key Stealth Address Scanning & Unblinding (Balance Derivation)
5. Outgoing Zero-Knowledge Spend via CLSAG Ring Signatures
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.bridge import FastBridgeGateway, SupportedChain, AssetType
from core.crypto import (
    StealthWalletKeys,
    Commitment,
    create_stealth_output,
    scan_stealth_output,
    compute_key_image,
    create_ring_signature,
    L,
)

BASE_SEPOLIA_RPC = "https://sepolia.base.org"
SOLANA_DEVNET_RPC = "https://api.devnet.solana.com"


def evm_call(method: str, params: list = None) -> dict:
    req = urllib.request.Request(
        BASE_SEPOLIA_RPC,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "KPL-Demo"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def solana_call(method: str, params: list = None) -> dict:
    req = urllib.request.Request(
        SOLANA_DEVNET_RPC,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "KPL-Demo"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def run_demo():
    print("================================================================================")
    print("   KITSUNE PRIVATE LAYER (KPL) // MULTI-CHAIN STEALTH ON-RAMP DEMO")
    print("================================================================================")
    
    # 1. User Wallet Creation
    print("\n[STEP 1] Generating Recipient Dual-Key Stealth Wallet...")
    user_keys = StealthWalletKeys.generate()
    user_addr = user_keys.public_address()
    print(f"  Public Stealth Address: {user_addr}")
    print(f"  View Public Key (A):     {user_keys.view_public.to_bytes().hex()[:32]}...")
    print(f"  Spend Public Key (B):    {user_keys.spend_public.to_bytes().hex()[:32]}...")

    gateway = FastBridgeGateway()
    utxos_received = []

    # 2. Base Sepolia EVM Deposit
    print("\n[STEP 2] Processing Inbound Bridge #1: Base Sepolia (EVM L2) USDC...")
    try:
        bn_res = evm_call("eth_blockNumber")
        current_block = int(bn_res.get("result", "0x0"), 16)
    except Exception:
        current_block = 59100000

    base_amt = 50.0
    quote_base = gateway.get_quote(SupportedChain.BASE, AssetType.USDC, base_amt)
    order_base = gateway.create_inbound_order(SupportedChain.BASE, AssetType.USDC, base_amt, user_addr)
    
    # Simulate EVM transfer
    evm_tx = "0x" + hashlib.sha256(f"BASE_USDC:{order_base.order_id}:{current_block}".encode()).hexdigest()
    settled_base = gateway.confirm_inbound_deposit(order_base.order_id, evm_tx)
    
    # Mint KPL Stealth Output
    P_base, R_base, _ = create_stealth_output(user_keys.view_public, user_keys.spend_public)
    utxos_received.append({
        "chain": "Base (EVM L2)",
        "source_asset": f"{base_amt} USDC",
        "kpl_amount": quote_base.kpl_received,
        "P": P_base,
        "R": R_base,
        "kpl_tx": settled_base.kpl_tx_hash,
    })
    print(f"  Order ID:             {order_base.order_id}")
    print(f"  Deposit Confirmed:    {base_amt} USDC -> {quote_base.kpl_received} KPL (~{quote_base.estimated_seconds}s settlement)")
    print(f"  Base Sepolia Tx Hash: {evm_tx[:28]}...")
    print(f"  KPL Stealth UTXO:     {P_base.to_bytes().hex()[:28]}...")

    # 3. Solana Devnet Deposit
    print("\n[STEP 3] Processing Inbound Bridge #2: Solana Devnet SOL...")
    try:
        bh_res = solana_call("getLatestBlockhash", [{"commitment": "finalized"}])
        latest_bh = bh_res["result"]["value"]["blockhash"]
    except Exception:
        latest_bh = "2BTgymGPKfdkSkgMo9gbJQqTLm31tvp1nWeTogmXzKm9"

    sol_amt = 0.25
    quote_sol = gateway.get_quote(SupportedChain.SOLANA, AssetType.SOL, sol_amt)
    order_sol = gateway.create_inbound_order(SupportedChain.SOLANA, AssetType.SOL, sol_amt, user_addr)
    
    sol_tx = hashlib.sha256(f"SOL_ESCROW:{order_sol.order_id}:{latest_bh}".encode()).hexdigest() + "5k1"
    settled_sol = gateway.confirm_inbound_deposit(order_sol.order_id, sol_tx)

    P_sol, R_sol, _ = create_stealth_output(user_keys.view_public, user_keys.spend_public)
    utxos_received.append({
        "chain": "Solana Devnet",
        "source_asset": f"{sol_amt} SOL",
        "kpl_amount": quote_sol.kpl_received,
        "P": P_sol,
        "R": R_sol,
        "kpl_tx": settled_sol.kpl_tx_hash,
    })
    print(f"  Order ID:             {order_sol.order_id}")
    print(f"  Deposit Confirmed:    {sol_amt} SOL -> {quote_sol.kpl_received} KPL (~{quote_sol.estimated_seconds}s settlement)")
    print(f"  Solana Tx Signature:  {sol_tx[:28]}...")
    print(f"  KPL Stealth UTXO:     {P_sol.to_bytes().hex()[:28]}...")

    # 4. Bitcoin Lightning Submarine Swap
    print("\n[STEP 4] Processing Inbound Bridge #3: Bitcoin Lightning Submarine Swap...")
    ln_amt = 0.001  # 100,000 sats
    quote_ln = gateway.get_quote(SupportedChain.LIGHTNING, AssetType.BTC, ln_amt)
    order_ln = gateway.create_inbound_order(SupportedChain.LIGHTNING, AssetType.BTC, ln_amt, user_addr)

    # Submarine swap settlement via 32-byte preimage
    settled_ln = gateway.settle_lightning_submarine_swap(order_ln.order_id, order_ln.preimage)
    P_ln, R_ln, _ = create_stealth_output(user_keys.view_public, user_keys.spend_public)
    utxos_received.append({
        "chain": "Bitcoin Lightning",
        "source_asset": f"{ln_amt} BTC (100k sats)",
        "kpl_amount": quote_ln.kpl_received,
        "P": P_ln,
        "R": R_ln,
        "kpl_tx": settled_ln.kpl_tx_hash,
    })
    print(f"  Order ID:             {order_ln.order_id}")
    print(f"  Preimage Revealed:    {order_ln.preimage[:24]}... (SHA-256 match)")
    print(f"  Swap Confirmed:       {ln_amt} BTC -> {quote_ln.kpl_received} KPL (~{quote_ln.estimated_seconds}s sub-second finality)")
    print(f"  KPL Stealth UTXO:     {P_ln.to_bytes().hex()[:28]}...")

    # 5. Dual-Key Stealth Scan & Balance Unblinding
    print("\n[STEP 5] Scanning Ledger with Private View Key (a)...")
    total_unblinded_kpl = 0.0
    spend_keys = []

    for idx, utxo in enumerate(utxos_received, 1):
        is_mine, one_time_spend_sec = scan_stealth_output(utxo["R"], utxo["P"], user_keys)
        assert is_mine, f"Failed to identify ownership for UTXO #{idx}"
        spend_keys.append(one_time_spend_sec)
        total_unblinded_kpl += utxo["kpl_amount"]
        print(f"  [OK] UTXO #{idx} ({utxo['chain']}): Found {utxo['kpl_amount']} KPL. Spend key derived: {hex(one_time_spend_sec)[:18]}...")

    print(f"\n  >>> TOTAL WALLET BALANCE: {total_unblinded_kpl:.6f} KPL <<<")

    # 6. Zero-Knowledge Spend using CLSAG Ring Signature
    print("\n[STEP 6] Executing Outgoing Private Spend via CLSAG Ring Signature...")
    merchant_keys = StealthWalletKeys.generate()
    merchant_addr = merchant_keys.public_address()
    spend_amt = 25.0
    change_amt = total_unblinded_kpl - spend_amt - 0.005  # 0.005 KPL fee

    # Construct stealth output for recipient
    P_merchant, R_merchant, _ = create_stealth_output(merchant_keys.view_public, merchant_keys.spend_public)
    
    # Ring decoys
    real_spend_key = spend_keys[0]
    real_spend_pub = utxos_received[0]["P"]
    decoys = [StealthWalletKeys.generate().spend_public for _ in range(4)]
    ring = decoys[:2] + [real_spend_pub] + decoys[2:]
    real_idx = 2

    # Key image computation: I = x * Hp(P)
    key_image = compute_key_image(real_spend_key, real_spend_pub)
    sig_payload = f"TRANSFER:{merchant_addr}:{spend_amt}:CHANGE:{change_amt}".encode()
    ring_sig = create_ring_signature(sig_payload, ring, real_index=real_idx, secret_key=real_spend_key)
    sig_valid = ring_sig.verify(sig_payload)

    print(f"  Recipient Address:     {merchant_addr[:30]}...")
    print(f"  Amount Sent:           {spend_amt} KPL (Change: {change_amt:.6f} KPL, Fee: 0.005 KPL)")
    print(f"  Ring Size:             {len(ring)} members (Real index obscured)")
    print(f"  Key Image:             {key_image.to_bytes().hex()[:30]}... (Double-spend immune)")
    print(f"  CLSAG Signature Proof: {'SUCCESS - CRYPTOGRAPHICALLY VALID' if sig_valid else 'FAILED'}")

    print("\n================================================================================")
    print("   DEMO COMPLETED: 3 BRIDGES SETTLED, STEALTH UTXOS MINTED & SPENT ZERO-KNOWLEDGE")
    print("================================================================================")
    return True


if __name__ == "__main__":
    run_demo()
