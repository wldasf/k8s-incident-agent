#!/usr/bin/env bash
# Provision the cluster and fetch a working kubeconfig.
set -euo pipefail
TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform" && pwd)"
cd "$TF_DIR"

[ -f terraform.tfvars ] || { echo "ERROR: create terraform.tfvars from terraform.tfvars.example"; exit 1; }

echo "==> terraform apply"
terraform init -input=false
terraform apply -auto-approve

CP_IP="$(terraform output -raw control_plane_ip)"
# Servers are recreated with new host keys but often reuse IPs; clear stale entries.
for ip in $(terraform output -json worker_ips | tr -d '[]", ' | tr '\n' ' ') "$CP_IP"; do
  ssh-keygen -R "$ip" >/dev/null 2>&1 || true
done

echo "==> Control plane: $CP_IP"

echo "==> Waiting for k3s to finish installing (cloud-init)"
for i in $(seq 1 60); do
  if ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 \
      "root@$CP_IP" 'test -f /var/lib/k3s-ready' 2>/dev/null; then
    echo "    k3s ready"; break
  fi
  printf '.'; sleep 10
done

echo "==> Fetching kubeconfig"
ssh "root@$CP_IP" 'cat /etc/rancher/k3s/k3s.yaml' \
  | sed "s/127.0.0.1/$CP_IP/" > "$TF_DIR/kubeconfig.yaml"
chmod 600 "$TF_DIR/kubeconfig.yaml"

export KUBECONFIG="$TF_DIR/kubeconfig.yaml"
echo "==> Waiting for all nodes to register"
for i in $(seq 1 40); do
  n=$(kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready ' || true)
  [ "$n" -ge 4 ] && break
  printf '.'; sleep 10
done
kubectl get nodes -o wide

cat <<MSG

Cluster is up. Run this in your shell:

    export KUBECONFIG=$TF_DIR/kubeconfig.yaml

Billing is hourly. Run 'make down' when you finish a session.
MSG
