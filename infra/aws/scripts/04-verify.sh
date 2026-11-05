#!/usr/bin/env bash
# Verify the EKS test-bed. Run at the start of every experimental session.
set -uo pipefail
kubectl cluster-info >/dev/null 2>&1 || {
  echo "Can't reach the cluster. Run: aws eks update-kubeconfig --region eu-central-1 --name incident-agent"
  exit 1
}

PASS=0; FAIL=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then printf '  [ OK ] %s\n' "$label"; PASS=$((PASS+1))
  else printf '  [FAIL] %s\n' "$label"; FAIL=$((FAIL+1)); fi
}

# True if every pod in namespace $1 (optionally filtered by label selector $3)
# runs on a node labelled workload-tier=$2. Checks labels, not node names,
# so it works however the nodes are named.
pods_on_tier() {
  local ns="$1" tier="$2" selector="${3:-}"
  local tier_nodes pod_nodes
  tier_nodes=" $(kubectl get nodes -l "workload-tier=$tier" -o jsonpath='{.items[*].metadata.name}') "
  pod_nodes=$(kubectl get pods -n "$ns" ${selector:+-l "$selector"} -o jsonpath='{.items[*].spec.nodeName}')
  [ -n "$pod_nodes" ] || return 1
  for n in $pod_nodes; do
    [[ "$tier_nodes" == *" $n "* ]] || return 1
  done
}

# True if the system node has spare pod capacity (EKS limits pods per instance).
system_node_has_room() {
  local node used max
  node=$(kubectl get nodes -l workload-tier=system -o jsonpath='{.items[0].metadata.name}')
  used=$(kubectl get pods -A --field-selector "spec.nodeName=$node" --no-headers | wc -l)
  max=$(kubectl get node "$node" -o jsonpath='{.status.allocatable.pods}')
  [ "$used" -lt "$max" ]
}

echo "=== Cluster ==="
check "API server reachable"             kubectl cluster-info
check "4 nodes Ready"                    bash -c '[ "$(kubectl get nodes --no-headers | grep -c " Ready ")" -eq 4 ]'
check "2 application nodes"              bash -c '[ "$(kubectl get nodes -l workload-tier=application --no-headers | wc -l)" -eq 2 ]'
check "1 observability node"             bash -c '[ "$(kubectl get nodes -l workload-tier=observability --no-headers | wc -l)" -eq 1 ]'
check "1 system node"                    bash -c '[ "$(kubectl get nodes -l workload-tier=system --no-headers | wc -l)" -eq 1 ]'
check "nodes in the VPC (10.0.x)"        bash -c '! kubectl get nodes -o jsonpath="{.items[*].status.addresses[?(@.type==\"InternalIP\")].address}" | tr " " "\n" | grep -qv "^10\.0\."'
check "system node has pod capacity"     system_node_has_room

echo "=== Application ==="
check "all boutique deployments up"      bash -c 'kubectl get deploy -n boutique -o json | python3 -c "
import json,sys
d=json.load(sys.stdin)[\"items\"]
sys.exit(0 if d and all(i[\"status\"].get(\"availableReplicas\",0)>0 for i in d) else 1)"'
check "boutique pods on application tier" pods_on_tier boutique application

echo "=== Observability ==="
check "prometheus pod running"           bash -c '[ "$(kubectl get pods -n observability -l app.kubernetes.io/name=prometheus --no-headers | grep -c Running)" -ge 1 ]'
check "grafana pod running"              bash -c '[ "$(kubectl get pods -n observability -l app.kubernetes.io/name=grafana --no-headers | grep -c Running)" -ge 1 ]'
check "loki pod running"                 bash -c '[ "$(kubectl get pods -n observability -l app=loki --no-headers | grep -c Running)" -ge 1 ]'
check "prometheus on observability tier" pods_on_tier observability observability app.kubernetes.io/name=prometheus

echo "=== Chaos tooling ==="
check "chaos-mesh controller running"    bash -c '[ "$(kubectl get pods -n chaos-mesh -l app.kubernetes.io/component=controller-manager --no-headers | grep -c Running)" -ge 1 ]'
check "chaos-daemon on every node"       bash -c '[ "$(kubectl get ds chaos-daemon -n chaos-mesh -o jsonpath="{.status.numberReady}")" -eq 4 ]'
check "chaos controllers on system tier" pods_on_tier chaos-mesh system app.kubernetes.io/component=controller-manager
check "PodChaos CRD registered"          kubectl get crd podchaos.chaos-mesh.org
check "NetworkChaos CRD registered"      kubectl get crd networkchaos.chaos-mesh.org

echo
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ] || { echo "Environment NOT ready."; exit 1; }
echo "Environment verified."