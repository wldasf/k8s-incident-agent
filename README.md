# Autonomous Incident Response in Kubernetes

A test rig for measuring when an AI agent should be allowed to fix a production
system on its own.

Systems that let language-model agents act on live infrastructure usually gate
that action on the agent's confidence: act above a threshold, escalate to a
human below it. This project measures whether that confidence can be trusted.
It injects reproducible faults into a live Kubernetes cluster, lets an agent
diagnose each one and propose a fix, and passes each proposal through a safety
gate that decides whether it may run.

The full write-up is in [`writing/report.md`](writing/report.md).

## Findings, briefly

Across 99 runs under three policies, diagnosis was accurate on faults whose
cause is written in cluster configuration (98%) and poor on faults that must be
inferred across services (24%). The model's own stated confidence ranked
correct diagnoses above incorrect ones better than an evidence-grounded
alternative, despite being worse calibrated. No confidence threshold gave both
useful automation and a low error rate.

## Repository layout

```
agent/        diagnosis loop, action catalogue, safety gate, confidence estimators
  policies/   permissive, balanced, conservative and no-op policies (YAML)
harness/      experiment runner, fault injection, outcome scoring, analysis
scenarios/    fault definitions with ground truth
  excluded/   scenarios removed after validation, kept for the record
infra/        Terraform for the Hetzner cluster, and setup scripts
results/      the three result files the report is based on
writing/      the final report
decisions.md  dated log of design decisions and corrections
```

## Requirements

- A Hetzner Cloud account and API token
- Terraform 1.6 or later, `kubectl`, `helm`, the `hcloud` CLI
- Python 3.11 or later
- A Google Gemini API key

## Reproducing the results

Create `infra/terraform/terraform.tfvars` from the example file and add your
Hetzner token and public IP address. Then:

```bash
make up              # provision four servers and install k3s
make observability   # Prometheus and Loki
make workload        # Online Boutique and Chaos Mesh
make verify          # check everything is healthy

export GEMINI_API_KEY=...
bash infra/scripts/deploy-harness.sh
```

Validate that every scenario's resolution check detects its own fault before
collecting data:

```bash
ssh root@<control-plane-ip> 'cd /opt/harness && set -a && . env.sh && set +a && python3 -m harness.validate_scenarios'
```

Run a policy condition (about 8 to 12 hours for 33 runs):

```bash
ssh root@<control-plane-ip> '/opt/harness/run-batch.sh --all --policy balanced --estimator E1 --repeats 3'
```

Analyse the results:

```bash
python3 harness/analyse.py results/*.jsonl
```

If your public IP address changes, `make fixip` updates the firewall. Run
`make down` to destroy the cluster when finished; servers are billed while they
exist.

## Licence

MIT. See [LICENSE](LICENSE).
