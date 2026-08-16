#!/usr/bin/env bash
# Destroy the cluster. Hetzner bills hourly, so this is the main cost control.
set -euo pipefail
TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform" && pwd)"
cd "$TF_DIR"

echo "This destroys all cluster servers. Experiment results in ./results are not affected."
read -rp "Type 'destroy' to confirm: " ans
[ "$ans" = "destroy" ] || { echo "Aborted."; exit 1; }

terraform destroy -auto-approve
rm -f kubeconfig.yaml
echo "Cluster destroyed. Billing stopped."
