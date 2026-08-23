#!/usr/bin/env bash
# Relax probe timings across the whole Online Boutique namespace.
#
# Online Boutique ships probe timings tuned for a fast local cluster:
# timeoutSeconds 1, no initialDelaySeconds. Several services are Python gRPC
# servers that call dependencies during startup and cannot answer within a
# second of launch, so the liveness probe kills them (exit 137) before they
# become ready -- producing a CrashLoopBackOff with entirely healthy
# application logs.
#
# This was first seen on emailservice and patched there individually. It then
# recurred on recommendationservice, where it went unnoticed for three days.
# Patching per-service is therefore the wrong granularity: the timings are
# applied namespace-wide as part of provisioning, so the environment is
# reproducible without manual repair.
set -euo pipefail
NS="${1:-boutique}"

echo "==> Relaxing probe timings across namespace '$NS'"
for d in $(kubectl get deploy -n "$NS" -o jsonpath='{.items[*].metadata.name}'); do
  for probe in livenessProbe readinessProbe; do
    has=$(kubectl get deploy "$d" -n "$NS" \
      -o jsonpath="{.spec.template.spec.containers[0].$probe}" 2>/dev/null || true)
    [ -z "$has" ] && continue
    kubectl patch deploy "$d" -n "$NS" --type=json -p="[
      {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/$probe/timeoutSeconds\",\"value\":5},
      {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/$probe/periodSeconds\",\"value\":10},
      {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/$probe/failureThreshold\",\"value\":5}
    ]" >/dev/null 2>&1 || true
    # initialDelaySeconds is absent by default, so add rather than replace.
    kubectl patch deploy "$d" -n "$NS" --type=json -p="[
      {\"op\":\"add\",\"path\":\"/spec/template/spec/containers/0/$probe/initialDelaySeconds\",\"value\":25}
    ]" >/dev/null 2>&1 || \
    kubectl patch deploy "$d" -n "$NS" --type=json -p="[
      {\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/$probe/initialDelaySeconds\",\"value\":25}
    ]" >/dev/null 2>&1 || true
  done
  echo "    patched $d"
done

echo "==> Waiting for rollout"
kubectl wait --for=condition=available --timeout=10m deployment --all -n "$NS"

echo "==> Confirming no pod is crash-looping"
bad=$(kubectl get pods -n "$NS" --no-headers | grep -v " Running " || true)
if [ -n "$bad" ]; then
  echo "$bad"
  echo "ERROR: namespace not healthy after probe patch"
  exit 1
fi
echo "==> All pods healthy."
