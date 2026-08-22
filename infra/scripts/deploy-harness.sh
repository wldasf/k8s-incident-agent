#!/usr/bin/env bash
# Deploy the harness onto the cluster's control plane and run a batch there.
#
# Rationale: running the harness from a laptop puts a WAN link and two
# kubectl port-forwards on the critical path of every measurement. Those
# tunnels drop under the probe's connection churn, and when the Prometheus
# tunnel drops, PromQL predicates return "no series" -- which the harness
# reads as evidence absent rather than measurement failed. Latency
# measurements are also distorted: a healthy p99 measured from Jordan to
# Germany was ~2000ms, almost all of it network.
#
# On the control plane, Prometheus and the frontend are reachable directly,
# there is no tunnel to drop, and the laptop can be closed mid-batch.
set -euo pipefail

TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform" 2>/dev/null || cd "$(dirname "${BASH_SOURCE[0]}")/infra/terraform"; pwd)"
CP_IP="$(terraform -chdir="$TF_DIR" output -raw control_plane_ip)"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."; pwd)"

: "${GEMINI_API_KEY:?export GEMINI_API_KEY before deploying}"

echo "==> Target control plane: $CP_IP"

echo "==> Installing python dependencies on the server"
ssh -o StrictHostKeyChecking=accept-new "root@$CP_IP" '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null 2>&1
  apt-get install -y -qq python3-pip python3-venv rsync >/dev/null 2>&1
  python3 -m venv /opt/harness-venv 2>/dev/null || true
  /opt/harness-venv/bin/pip install -q --upgrade pip pydantic pyyaml
  mkdir -p /opt/harness
'

echo "==> Copying project (excluding state, results and secrets)"
rsync -az --delete \
  --exclude '.git' --exclude 'results' --exclude '__pycache__' \
  --exclude 'infra/terraform/.terraform' --exclude '*.tfstate*' \
  --exclude 'terraform.tfvars' --exclude 'kubeconfig.yaml' \
  "$PROJECT_ROOT/agent" "$PROJECT_ROOT/harness" "$PROJECT_ROOT/scenarios" \
  "root@$CP_IP:/opt/harness/"

echo "==> Writing server-side environment"
ssh "root@$CP_IP" "cat > /opt/harness/env.sh <<EOF
export GEMINI_API_KEY='${GEMINI_API_KEY}'
export ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY:-}'
export LLM_PROVIDER='${LLM_PROVIDER:-gemini}'
export LLM_MODEL='${LLM_MODEL:-gemini-2.5-flash}'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
export PATH=/opt/harness-venv/bin:\\\$PATH
export PROMETHEUS_URL=http://\\\$(kubectl get svc -n observability -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].spec.clusterIP}'):9090
export FRONTEND_URL=http://\\\$(kubectl get svc frontend -n boutique -o jsonpath='{.spec.clusterIP}'):80
EOF
chmod 600 /opt/harness/env.sh"

echo "==> Verifying in-cluster endpoints"
ssh "root@$CP_IP" 'set -a; . /opt/harness/env.sh; set +a
  echo "  prometheus: $PROMETHEUS_URL"
  echo "  frontend:   $FRONTEND_URL"
  curl -s -o /dev/null -w "  prometheus health: %{http_code}\n" "$PROMETHEUS_URL/-/healthy"
  curl -s -o /dev/null -w "  frontend health:   %{http_code}\n" "$FRONTEND_URL/"
  curl -s -o /dev/null -w "  frontend latency:  %{time_total}s\n" "$FRONTEND_URL/"'

cat <<MSG

Harness deployed to $CP_IP:/opt/harness

Start a batch (detached, survives disconnection):

  ssh root@$CP_IP 'cd /opt/harness && set -a && . env.sh && set +a && \\
    nohup python3 -m harness.runner --all --policy balanced --estimator E3 \\
    --repeats 3 --out /opt/harness/results.jsonl > /opt/harness/batch.log 2>&1 &'

Watch progress:
  ssh root@$CP_IP 'tail -f /opt/harness/batch.log'

Retrieve results:
  scp root@$CP_IP:/opt/harness/results.jsonl results/\$(date +%Y%m%d)_batch.jsonl
MSG
