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

## Running on AWS

The test-bed also runs on Amazon EKS in eu-central-1 (Frankfurt). All
infrastructure is defined in Terraform: a VPC with private subnets, an EKS
cluster with three node groups, and the IAM roles the cluster and harness
need. The harness runs inside the cluster as a Kubernetes Job, reads its
API key from Secrets Manager and writes results to S3. One command builds
the whole environment (`make aws-up`) and one destroys it (`make aws-down`).

See [`docs/aws/design.md`](docs/aws/design.md) for the architecture.

### Requirements

- An AWS account, and an IAM user allowed to create the resources below
- AWS CLI v2.32 or later (for `aws login`)
- Terraform 1.10 or later
- `kubectl` and Helm
- Docker (to build the harness image)
- `envsubst` (part of the `gettext` package) and `make`
- A Google Gemini API key


### First-time setup

These steps are done once; their resources persist between sessions.

1. **Bootstrap.** `terraform -chdir=infra/aws/bootstrap apply` creates the
   Terraform state bucket, the results bucket, the ECR repository and an
   empty Secrets Manager secret. The bucket names end in a random suffix:
   copy it into `infra/aws/cluster/versions.tf` (state backend),
   `infra/aws/cluster/harness.tf` (`results_bucket`) and
   `infra/aws/k8s/harness-job.yaml` (`RESULTS_BUCKET`).
2. **Store the API key** without it entering your shell history or
   Terraform state:
   ```bash
   read -rs GEMINI_KEY
   aws secretsmanager put-secret-value --secret-id incident-agent/gemini-api-key --secret-string "$GEMINI_KEY"
   unset GEMINI_KEY
   ```
3. **Build and push the harness image:**
   ```bash
   ECR=$(terraform -chdir=infra/aws/bootstrap output -raw ecr_repository_url)
   aws ecr get-login-password | docker login --username AWS --password-stdin "${ECR%%/*}"
   docker build --platform linux/amd64 --provenance=false -f infra/aws/harness/Dockerfile -t "$ECR:v1" .
   docker push "$ECR:v1"
   ```

### Each session

```bash
aws login
make aws-up          # shows the Terraform plan and asks for confirmation; ~25 min
```

Run the harness. Edit `args` in `infra/aws/k8s/harness-job.yaml` to choose
the scenario, policy and repeats.

```bash
export HARNESS_IMAGE="$(terraform -chdir=infra/aws/bootstrap output -raw ecr_repository_url):v1"
envsubst < infra/aws/k8s/harness-job.yaml | kubectl apply -f -
kubectl logs -n harness job/harness-run -f
```

To run again, delete the finished Job first:
`kubectl delete job harness-run -n harness`.

Results are uploaded to S3 when the run ends:

```bash
aws s3 ls s3://<results-bucket>/runs/ --recursive
aws s3 cp s3://<results-bucket>/runs/<run-id>/<run-id>.jsonl - | python3 -m json.tool
```

Destroy everything at the end of every session. `make aws-down` also
checks for billable leftovers.

```bash
make aws-down
```

### Cost

| Item | Approx. cost (eu-central-1) |
|---|---|
| EKS control plane | $0.10/hour |
| 4 × t3.large nodes | ~$0.38/hour |
| NAT Gateway + Elastic IP | ~$0.06/hour |
| **Running total** | **~$0.54/hour (~$1.60 per 3-hour session)** |
| Left running 24/7 | ~$395/month |
| Persistent (state, results, ECR, secret) | under $1/month |

The cluster is destroyed after every session, and `make aws-down` checks for
billable leftovers (NAT Gateways, Elastic IPs, clusters, instances, load
balancers).

### Design decisions

- **Private worker nodes, one NAT Gateway.** Nodes have no public IPs. A
  single NAT Gateway keeps cost down, at the price of a single-AZ egress path.
- **Three node groups.** Application, observability and system tiers, so
  fault injection on the application tier cannot take down measurement or
  the chaos tooling.
- **Remote Terraform state.** State lives in a versioned S3 bucket with
  native locking; persistent resources sit in a separate `bootstrap`
  configuration that is never destroyed.
- **No static credentials.** The operator uses short-lived `aws login`
  sessions, and the harness pod gets AWS access through EKS Pod Identity.
  The API key lives in Secrets Manager and never enters Terraform state.
- **Least-privilege RBAC.** The harness service account can create chaos
  experiments only against the application namespace, derived from the
  kubectl commands the harness actually runs.
- **Pinned versions.** Kubernetes, the Online Boutique release, kubectl in
  the image, and an immutable ECR tag, for reproducible runs.

### Problems solved during the migration

- **`terraform destroy` hung for 20 minutes.** Online Boutique's LoadBalancer
  Service made Kubernetes create an AWS load balancer outside Terraform's
  state, which blocked deleting the public subnets. Fixed by deleting the
  load balancer, and removing that Service at deploy time (access is via
  port-forward).
- **Fault injection was rejected despite correct RBAC.** Chaos Mesh's
  admission webhook checks chaos permissions in the *target* namespace as
  well as where the object is created. Fixed by granting chaos permissions
  in the application namespace.
- **Teardown timed out after moving a permission to the right Role.**
  `kubectl delete` waits by watching the object, and the narrower Role
  lacked `watch`; a broader ClusterRole had been hiding the gap. Fixed by
  adding `list` and `watch`.
- **Drift from a manual console fix.** A route table association repaired in
  the console left Terraform state pointing at a deleted resource. Detected
  with `terraform plan`, reconciled with `terraform state rm` and
  `terraform import`.
- **Three images per push.** Docker's default provenance attestation pushed
  an image index plus two manifests, which breaks ECR scanning and miscounts
  lifecycle rules. Fixed by building with `--provenance=false`.

## Licence

MIT. See [LICENSE](LICENSE).
