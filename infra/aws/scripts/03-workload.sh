#!/usr/bin/env bash
# Deploy Online Boutique and Chaos Mesh.
set -euo pipefail
kubectl cluster-info >/dev/null 2>&1 || {
  echo "Can't reach the cluster. Run: aws eks update-kubeconfig --region eu-central-1 --name incident-agent"
  exit 1
}
NS="boutique"

# Pinned release for reproducibility
MANIFEST="https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/v0.10.7/release/kubernetes-manifests.yaml"

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Deploying Online Boutique"
kubectl apply -n "$NS" -f "$MANIFEST"

# Online Boutique ships a LoadBalancer service. On EKS that creates a real AWS
# load balancer outside Terraform's state, which blocks 'terraform destroy'.
# Access is via port-forward, so remove it.
kubectl delete service frontend-external -n "$NS" --ignore-not-found

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

echo "==> Installing Chaos Mesh (containerd at the standard EKS socket path)"
helm repo add chaos-mesh https://charts.chaos-mesh.org >/dev/null
helm repo update >/dev/null
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --set controllerManager.nodeSelector."workload-tier"=system \
  --set dashboard.nodeSelector."workload-tier"=system \
  --set dnsServer.nodeSelector."workload-tier"=system \
  --wait --timeout 12m

echo "==> Done. Frontend: kubectl port-forward -n $NS svc/frontend 8080:80"
