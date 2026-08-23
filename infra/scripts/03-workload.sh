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

# emailservice is a Python gRPC service that takes longer to become
# responsive than its default 1s probe timeout allows. The process starts
# healthy but is killed by its own liveness probe before it can answer,
# producing a CrashLoopBackOff with no error in the application logs.
# Relaxing the probe timings is part of provisioning, not a manual repair:
# the benchmark must be reproducible without hand-patching.
echo "==> Relaxing namespace probe timings"
bash "$(dirname "${BASH_SOURCE[0]}")/probe-fix.sh" "$NS"

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
