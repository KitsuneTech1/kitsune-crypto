#!/usr/bin/env bash
# Kitsune Private Layer (KPL) - Devnet Orchestration Script
set -e

ACTION="${1:-status}"

case "$ACTION" in
  up)
    echo "=== Starting 4-node KPL BFT Devnet Cluster ==="
    docker compose up -d --build
    echo "Waiting for cluster synchronization..."
    sleep 3
    "$0" status
    ;;
  down)
    echo "=== Stopping KPL Devnet Cluster ==="
    docker compose down -v
    ;;
  logs)
    docker compose logs -f
    ;;
  status)
    echo "=== KPL Local Devnet Node Status ==="
    for port in 9201 9202 9203 9204; do
      echo -n "Port $port: "
      curl -s "http://127.0.0.1:$port/status" | grep -E '"(node_id|height|latest_hash)"' | tr -d ' ",' || echo "OFFLINE"
    done
    ;;
  stress)
    shift || true
    COUNT="${1:-50}"
    KPL_NODES="127.0.0.1:9201,127.0.0.1:9202,127.0.0.1:9203,127.0.0.1:9204" python3 scripts/stress_cluster.py "$COUNT"
    ;;
  *)
    echo "Usage: $0 {up|down|logs|status|stress [count]}"
    exit 1
    ;;
esac
