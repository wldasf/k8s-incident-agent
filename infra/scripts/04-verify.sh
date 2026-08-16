#!/usr/bin/env bash
# Verify the test-bed. Run at the start of every experimental session.
set -uo pipefail
: "${KUBECONFIG:?export KUBECONFIG=infra/terraform/kubeconfig.yaml first}"

PASS=0; FAIL=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then printf '  [ OK ] %s\n' "$label"; PASS=$((PASS+1))
  else printf '  [FAIL] %s\n' "$label"; FAIL=$((FAIL+1)); fi
}

echo "=== Cluster ==="
check "API server reachable"            kubectl cluster-info
check "4 nodes Ready"                    bash -c '[ "$(kubectl get nodes --no-headers | grep -c " Ready ")" -eq 4 ]'
check "node tier labels present"         bash -c '[ "$(kubectl get nodes -l workload-tier=application --no-headers | wc -l)" -ge 2 ]'
check "private network in use (10.10.x)" bash -c 'kubectl get nodes -o wide | grep -q "10\.10\.1\."'

echo "=== Application ==="
check "all boutique deployments up"      bash -c 'kubectl get deploy -n boutique -o json | python3 -c "
import json,sys
d=json.load(sys.stdin)[\"items\"]
sys.exit(0 if d and all(i[\"status\"].get(\"availableReplicas\",0)>0 for i in d) else 1)"'
check "app pods on application tier"     bash -c '[ "$(kubectl get pods -n boutique -o wide --no-headers | grep -c w1\\\|w2)" -ge 5 ]'

echo "=== Observability ==="
check "prometheus pod running"           bash -c '[ "$(kubectl get pods -n observability -l app.kubernetes.io/name=prometheus --no-headers | grep -c Running)" -ge 1 ]'
check "grafana pod running"              bash -c '[ "$(kubectl get pods -n observability -l app.kubernetes.io/name=grafana --no-headers | grep -c Running)" -ge 1 ]'
check "loki pod running"                 bash -c '[ "$(kubectl get pods -n observability -l app=loki --no-headers | grep -c Running)" -ge 1 ]'

echo "=== Chaos tooling ==="
check "chaos-mesh controller running"    bash -c '[ "$(kubectl get pods -n chaos-mesh --no-headers | grep -c Running)" -ge 1 ]'
check "PodChaos CRD registered"          kubectl get crd podchaos.chaos-mesh.org
check "NetworkChaos CRD registered"      kubectl get crd networkchaos.chaos-mesh.org

echo
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ] || { echo "Environment NOT ready."; exit 1; }
echo "Environment verified."
