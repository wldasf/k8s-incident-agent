# Getting started — first session

Goal of session one is **not** to build anything. It is to prove the
environment works and to discover what does not, while there is still time to
adapt. Budget about three hours.

---

## Step 0 — Local tooling (once, ~20 min)

Install: `terraform >= 1.6`, `kubectl`, `helm`, `hcloud`, `python3.11+`.

```bash
python3 -m pip install -r requirements.txt
python3 scenarios/loader.py          # should print "All scenarios valid."
```

That runs offline. If it passes, the repository is sound before you spend a
cent on infrastructure.

## Step 1 — Hetzner account (~20 min)

1. Create a Hetzner Cloud account and a project.
2. Project → Security → API Tokens → generate a **Read & Write** token.
3. Ensure you have an SSH key at `~/.ssh/id_ed25519.pub` (create with
   `ssh-keygen -t ed25519` if not).
4. Find your public address: `curl -4 ifconfig.me`

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit: paste the token, set allowed_admin_ipv4 = ["YOUR.IP/32"]
```

## Step 2 — Provision (~15 min, billing starts)

```bash
cd ../..
make up
export KUBECONFIG=$PWD/infra/terraform/kubeconfig.yaml
kubectl get nodes
```

Expect four nodes Ready. If workers do not join, check cloud-init on the
control plane: `ssh root@<ip> journalctl -u cloud-final -n 50`.

## Step 3 — Stack and workload (~25 min, mostly image pulls)

```bash
make observability
make workload
make verify
```

`make verify` runs twelve checks and exits non-zero on any failure. Do not
proceed past a failure — everything downstream depends on this being sound.

## Step 4 — The critical check: do the metrics exist? (~15 min)

This is the highest-risk unknown in the whole project.

```bash
kubectl port-forward -n observability svc/kube-prom-kube-prometheus-prometheus 9090:9090 &
# generate traffic first so request-based series appear
kubectl port-forward -n boutique svc/frontend 8080:80 &
for i in $(seq 1 200); do curl -s localhost:8080 > /dev/null; done

python3 harness/probe_metrics.py
```

The probe tests all 42 PromQL expressions in the scenario library and reports
which return no data.

**Expect some failures.** The gRPC histogram series (`grpc_server_handling_*`)
depend on whether Online Boutique services expose them, and label names may
differ. Record exactly which expressions fail — this determines whether
predicates need rewriting or whether a scenario needs redesigning. Finding
this now is the entire point of session one.

## Step 5 — Manual smoke test of one scenario (~30 min)

Use RES-01: it is the simplest injection and needs no chaos tooling.

```bash
# capture the current spec so you can restore it
kubectl get deploy cartservice -n boutique -o yaml > /tmp/cartservice-before.yaml

# inject: drop the memory limit below the working set
kubectl set resources deploy/cartservice -n boutique \
  --limits=memory=24Mi --requests=memory=24Mi

# observe (give it ~90s)
kubectl get pods -n boutique -l app=cartservice -w
kubectl describe pod -n boutique -l app=cartservice | grep -A3 "Last State"

# expected: OOMKilled, restart count climbing

# teardown
kubectl set resources deploy/cartservice -n boutique \
  --limits=memory=128Mi --requests=memory=64Mi
```

Confirm the pod recovers. This validates the whole injection-observe-restore
cycle the harness will automate.

## Step 6 — Stop billing

```bash
make down
```

Servers bill while they *exist*, not while they are running. Stopping a server
does not stop the charge; only `terraform destroy` does.

---

## What to record from session one

Keep a running log — it becomes your methodology and limitations chapters, and
reconstructing it from memory later always produces something thinner.

- Which PromQL expressions returned no data, and why
- Actual provisioning time and cost for the session
- Any deviation from the documented setup
- Whether RES-01 injection and recovery behaved as specified

## In parallel, not after

The critical review is 30% of the proposal mark, was your second-lowest score,
and needs no cluster. Write it during image pulls and while experiments run.
Leaving writing until October is the most reliable way to lose marks already
earned.

## Session two

Depends entirely on what the probe finds:

- **Most metrics present** → build the agent core (ReAct loop, tool catalogue,
  structured output, confidence estimators).
- **Many gRPC series missing** → first rewrite affected predicates around
  metrics that do exist, or add a sidecar exporter. Do not build on top of
  predicates that cannot be evaluated.
