#!/usr/bin/env bash
# Report current spend for the project. Requires the hcloud CLI, authenticated.
set -euo pipefail
command -v hcloud >/dev/null || { echo "hcloud CLI not installed"; exit 1; }

echo "=== Running servers ==="
hcloud server list -o columns=name,type,status,ipv4,created

echo
echo "=== Snapshots (billed per GB/month) ==="
hcloud image list --type snapshot -o columns=id,description,image_size,created 2>/dev/null || echo "none"

echo
echo "Reminder: servers bill hourly while they exist, whether or not they are"
echo "powered on. Only 'terraform destroy' stops the charge."
