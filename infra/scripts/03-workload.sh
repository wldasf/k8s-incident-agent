#!/usr/bin/env bash
# Deploy Online Boutique and Chaos Mesh.
set -euo pipefail
: "${KUBECONFIG:?export KUBECONFIG=infra/terraform/kubeconfig.yaml first}"
NS="boutique"
MANIFEST="https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml"

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Deploying Online Boutique"
kubectl apply -n "$NS" -f "$MANIFEST"

echo "==> Pinning application pods to the application tier"
for d in $(kubectl get deploy -n "$NS" -o name); do
  kubectl patch -n "$NS" "$d" --type=strategic \
    -p '{"spec":{"template":{"spec":{"nodeSelector":{"workload-tier":"application"}}}}}'
done

echo "==> Waiting for rollout"
kubectl wait --for=condition=available --timeout=15m deployment --all -n "$NS"

echo "==> Installing Chaos Mesh (k3s uses containerd at a non-default socket path)"
helm repo add chaos-mesh https://charts.chaos-mesh.org >/dev/null
helm repo update >/dev/null
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/k3s/containerd/containerd.sock \
  --wait --timeout 12m

echo "==> Done. Frontend: kubectl port-forward -n $NS svc/frontend 8080:80"
