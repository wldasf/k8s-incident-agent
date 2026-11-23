#!/usr/bin/env bash
# Waits until every node is Ready, then restarts CoreDNS so its two pods
# are spread across different nodes instead of all landing on the first one.set 
-euo pipefail
kubectl cluster-info >/dev/null 2>&1 || {
  echo "Can't reach the cluster. Run: aws eks update-kubeconfig --region eu-central-1 --name incident-agent"
  exit 1
}

echo "==> Waiting for nodes"
kubectl wait --for=condition=Ready nodes --all --timeout=10m

echo "==> Restarting CoreDNS"
kubectl rollout restart deployment coredns -n kube-system

echo "==> Waiting for CoreDNS restart to finish"
kubectl rollout status deployment coredns -n kube-system --timeout=5m
