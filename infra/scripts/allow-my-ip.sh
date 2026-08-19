#!/usr/bin/env bash
# Update the firewall to the current public IP, then apply.
# Run whenever SSH or the API server starts timing out.
set -euo pipefail
TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform" && pwd)"
MYIP=$(curl -s -4 ifconfig.me)
[ -n "$MYIP" ] || { echo "could not determine public IP"; exit 1; }
CURRENT=$(grep allowed_admin_ipv4 "$TF_DIR/terraform.tfvars" | grep -oE '[0-9.]+/32' || true)
echo "current in tfvars: ${CURRENT:-none}"
echo "actual public IP : $MYIP/32"
if [ "$CURRENT" = "$MYIP/32" ]; then
  echo "already correct; firewall unchanged."
  exit 0
fi
sed -i "s|allowed_admin_ipv4.*|allowed_admin_ipv4  = [\"$MYIP/32\"]|" "$TF_DIR/terraform.tfvars"
terraform -chdir="$TF_DIR" apply -auto-approve
echo "firewall updated to $MYIP/32"
