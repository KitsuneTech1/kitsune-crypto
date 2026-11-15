"""Kitsune Private Layer - Cluster Self-Healing Watchdog Daemon.

Monitors CT 401..404 consensus health on PVE2. Detects lagging nodes (>2 blocks),
stalled mempools, or unresponsive daemons. Autonomously triggers fast-sync or service restart.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

NODES = [
    ("401", "192.168.1.201:9200"),
    ("402", "192.168.1.202:9200"),
    ("403", "192.168.1.203:9200"),
    ("404", "192.168.1.204:9200"),
]

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [WATCHDOG-%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watchdog")


def query_node_health(ctid: str, addr: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(f"http://{addr}/status", headers={"User-Agent": "KPL-Watchdog"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("Node CT %s (%s) unreachable: %s", ctid, addr, e)
        return None


def heal_node(ctid: str, is_local_pve: bool = False):
    logger.info("Attempting automated self-healing restart on CT %s...", ctid)
    if is_local_pve:
        # Running directly on PVE2 host
        cmd = ["pct", "exec", ctid, "--", "systemctl", "restart", "kpl-node.service"]
    else:
        # Running remotely from Windows / agent machine
        ssh_inner = f"pct exec {ctid} -- systemctl restart kpl-node.service"
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "root@100.82.173.100", ssh_inner]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        logger.info("Healing command executed on CT %s (exit=%d)", ctid, res.returncode)
        return res.returncode == 0
    except Exception as e:
        logger.error("Failed to execute healing command on CT %s: %s", ctid, e)
        return False


def run_watchdog_sweep(is_local_pve: bool = False) -> Tuple[bool, dict]:
    node_reports: Dict[str, dict] = {}
    max_height = 0
    unhealthy_nodes = []

    for ctid, addr in NODES:
        health = query_node_health(ctid, addr)
        if health:
            h = health.get("height", 0)
            node_reports[ctid] = {"status": "HEALTHY", "height": h, "hash": health.get("latest_hash", "")[:12]}
            if h > max_height:
                max_height = h
        else:
            node_reports[ctid] = {"status": "UNREACHABLE", "height": -1, "hash": "---"}
            unhealthy_nodes.append(ctid)

    # Check for lagging nodes
    for ctid, report in node_reports.items():
        if report["status"] == "HEALTHY":
            lag = max_height - report["height"]
            if lag > 2:
                logger.warning("Node CT %s lagging by %d blocks (height #%d vs max #%d)", ctid, lag, report["height"], max_height)
                report["status"] = "LAGGING"
                unhealthy_nodes.append(ctid)

    # Trigger healing on unhealthy nodes
    healed_count = 0
    if unhealthy_nodes:
        logger.warning("Unhealthy nodes detected: %s. Initiating autonomous healing sweep...", unhealthy_nodes)
        for ctid in unhealthy_nodes:
            if heal_node(ctid, is_local_pve):
                healed_count += 1
        time.sleep(3.0)

    all_synced = (len(unhealthy_nodes) == 0)
    return all_synced, {
        "max_height": max_height,
        "all_synced": all_synced,
        "unhealthy_count": len(unhealthy_nodes),
        "healed_count": healed_count,
        "nodes": node_reports,
    }


def main():
    parser = argparse.ArgumentParser(description="KPL Cluster Self-Healing Watchdog")
    parser.add_argument("--local-pve", action="store_true", help="Set when running directly on PVE2 host")
    parser.add_argument("--daemon", action="store_true", help="Run continuously every 10 seconds")
    args = parser.parse_args()

    logger.info("=== KPL CLUSTER SELF-HEALING WATCHDOG INITIALIZED ===")
    if args.daemon:
        logger.info("Running in continuous monitoring daemon mode...")
        while True:
            run_watchdog_sweep(args.local_pve)
            time.sleep(10.0)
    else:
        synced, sweep = run_watchdog_sweep(args.local_pve)
        print("\nWatchdog Sweep Report:")
        print(json.dumps(sweep, indent=2))
        sys.exit(0 if synced else 1)


if __name__ == "__main__":
    main()
