#!/usr/bin/env bash
# Kitsune Private Layer (KPL) - PVE2 Multi-Node Validator Cluster Deployment
# Target Host: PVE2 (192.168.1.7) / tailnet 100.82.173.100
# Deploys 4 unprivileged LXC containers on local vmbr0 network (CT 401..404)

set -euo pipefail

echo "=== [KPL] Starting 4-Node Validator Cluster Provisioning on PVE2 ==="

CT_BASE=401
STORAGE="local-lvm"
BRIDGE="vmbr0"
TEMPLATE="local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"

for i in {0..3}; do
  CT_ID=$((CT_BASE + i))
  IP_SUFFIX=$((201 + i))
  IP="192.168.1.${IP_SUFFIX}/24"
  GW="192.168.1.1"
  HOSTNAME="kpl-validator-node-${i}"

  echo "-> Provisioning CT ${CT_ID} (${HOSTNAME}) on ${IP}..."
  
  if pct status "${CT_ID}" &>/dev/null; then
    echo "   CT ${CT_ID} already exists, skipping creation."
  else
    pct create "${CT_ID}" "${TEMPLATE}" \
      --cores 1 \
      --memory 1024 \
      --swap 256 \
      --rootfs "${STORAGE}:4" \
      --net0 "name=eth0,bridge=${BRIDGE},firewall=1,ip=${IP},gw=${GW}" \
      --ostype ubuntu \
      --hostname "${HOSTNAME}" \
      --unprivileged 1 \
      --start 1
    
    echo "   Installed and started CT ${CT_ID}."
  fi

  # Deploy validator systemd service
  echo "   Configuring systemd validator unit on CT ${CT_ID}..."
  pct exec "${CT_ID}" -- bash -c "cat << 'EOF' > /etc/systemd/system/kpl-validator.service
[Unit]
Description=Kitsune Private Layer Validator Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/kpl
ExecStart=/usr/bin/python3 -m network.node --node-id val_node_${i} --port 910${i}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
"
done

echo "=== [KPL] 4-Node Devnet Validator Cluster Deployment Ready ==="
