#!/usr/bin/env bash
# Install Prometheus, Loki, Promtail and Grafana onto the EKS cluster.
set -euo pipefail
kubectl cluster-info >/dev/null 2>&1 || {
  echo "Can't reach the cluster. Run: aws eks update-kubeconfig --region eu-central-1 --name incident-agent"
  exit 1
}
NS="observability"

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add grafana               https://grafana.github.io/helm-charts             >/dev/null
helm repo update >/dev/null

echo "==> kube-prometheus-stack"
# Prometheus, Grafana and Loki are pinned to the observability tier, and the
# operator, Alertmanager and kube-state-metrics to the system tier, so chaos
# experiments on the application tier cannot take down the measurement system.
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace "$NS" --create-namespace \
  --set prometheus.prometheusSpec.retention=12h \
  --set prometheus.prometheusSpec.scrapeInterval=15s \
  --set prometheus.prometheusSpec.resources.requests.memory=1Gi \
  --set prometheus.prometheusSpec.resources.limits.memory=2Gi \
  --set prometheus.prometheusSpec.nodeSelector."workload-tier"=observability \
  --set grafana.nodeSelector."workload-tier"=observability \
  --set prometheusOperator.nodeSelector."workload-tier"=system \
  --set alertmanager.alertmanagerSpec.nodeSelector."workload-tier"=system \
  --set kube-state-metrics.nodeSelector."workload-tier"=system \
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

Access via port-forward ( services are not exposed outside the cluster):

  kubectl port-forward -n $NS svc/kube-prom-grafana 3000:80
  kubectl port-forward -n $NS svc/kube-prom-kube-prometheus-prometheus 9090:9090
MSG
