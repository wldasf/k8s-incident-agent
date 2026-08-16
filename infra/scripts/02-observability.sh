#!/usr/bin/env bash
# Install Prometheus, Loki, Promtail and Grafana onto the Hetzner cluster.
set -euo pipefail
: "${KUBECONFIG:?export KUBECONFIG=infra/terraform/kubeconfig.yaml first}"
NS="observability"

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add grafana               https://grafana.github.io/helm-charts             >/dev/null
helm repo update >/dev/null

echo "==> kube-prometheus-stack"
# Pinned to the observability-tier worker so that chaos experiments targeting
# the application tier cannot accidentally take down the measurement system.
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace "$NS" --create-namespace \
  --set prometheus.prometheusSpec.retention=12h \
  --set prometheus.prometheusSpec.scrapeInterval=15s \
  --set prometheus.prometheusSpec.resources.requests.memory=1Gi \
  --set prometheus.prometheusSpec.resources.limits.memory=2Gi \
  --set prometheus.prometheusSpec.nodeSelector."workload-tier"=observability \
  --set grafana.nodeSelector."workload-tier"=observability \
  --set grafana.adminPassword=admin \
  --wait --timeout 12m

echo "==> Loki + Promtail"
helm upgrade --install loki grafana/loki-stack \
  --namespace "$NS" \
  --set loki.persistence.enabled=false \
  --set loki.nodeSelector."workload-tier"=observability \
  --set promtail.enabled=true \
  --set grafana.enabled=false \
  --wait --timeout 12m

cat <<MSG
==> Observability installed.

Access via port-forward (the firewall blocks direct access by design):

  kubectl port-forward -n $NS svc/kube-prom-grafana 3000:80
  kubectl port-forward -n $NS svc/kube-prom-kube-prometheus-prometheus 9090:9090
MSG
