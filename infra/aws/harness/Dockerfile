# Harness image: runs the incident-agent experiments as a Kubernetes Job on EKS.
# Build from the repository root:
#   docker build --platform linux/amd64 -f infra/aws/harness/Dockerfile -t incident-agent/harness:v1 .
FROM python:3.12-slim

# kubectl, pinned to the cluster's Kubernetes version. Inside a pod it
# authenticates with the pod's service account automatically.
ARG KUBECTL_VERSION=v1.37.1
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSLo /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
 && chmod +x /usr/local/bin/kubectl \
 && apt-get purge -y curl && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so code changes don't invalidate this cached layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt boto3==1.35.0

COPY agent ./agent
COPY harness ./harness
COPY scenarios ./scenarios
COPY infra/aws/harness/entrypoint.py ./entrypoint.py

# Run as an unprivileged user.
RUN useradd --uid 10001 --create-home harness \
 && mkdir -p /app/results && chown harness /app/results
USER harness

# In-cluster service addresses (overridable in the Job manifest).
ENV PYTHONUNBUFFERED=1 \
    AWS_DEFAULT_REGION=eu-central-1 \
    PROMETHEUS_URL=http://kube-prom-kube-prometheus-prometheus.observability.svc:9090 \
    FRONTEND_URL=http://frontend.boutique.svc/

ENTRYPOINT ["python", "/app/entrypoint.py"]
