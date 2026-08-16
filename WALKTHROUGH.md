# The whole project, step by step

**Today:** Saturday 15 August 2026 · **Deadline:** Monday 12 October 2026 · **58 days**

This is the master document. Work through it in order. Each stage lists what
you are doing, why it comes where it does, how you know it worked, and what
usually goes wrong.

Two tracks run at once: the **build track** (stages 0–9) and the **writing
track**. The writing track is not a final phase. It starts in week one and
runs continuously. Leaving writing until October is the most reliable way to
lose marks you have already earned.

---

# Stage 0 — Before you spend anything

**Goal.** Confirm the repository is sound and your tooling is in place, with
no cloud account and no cost.

**Steps.**

1. Create your Hetzner Cloud account *first*, before anything else today. New
   accounts are sometimes held for manual review or ID verification, which can
   take from minutes to a couple of days. Starting that clock now costs
   nothing and removes the most likely cause of a stalled first week.

2. While that processes, install local tooling: `terraform >= 1.6`,
   `kubectl`, `helm`, the `hcloud` CLI, and Python 3.11+.

3. Generate an SSH key if you do not have one:
   `ssh-keygen -t ed25519 -C "msc-project"`

4. Validate the repository offline:

   ```bash
   pip install -r requirements.txt
   python3 scenarios/loader.py
   ```

**Done when.** The loader prints `All scenarios valid.` and all twelve
scenarios are listed.

**What goes wrong.** Missing `pydantic` or `pyyaml` — the pip install covers
both. If the loader reports a schema error, something in a YAML file is
malformed; the error names the file and field.

**Time.** About an hour, most of it installing.

---

# Stage 1 — Bring up the cluster

**Goal.** A running four-node Kubernetes cluster on Hetzner with the demo
application, monitoring, and chaos tooling installed.

**Why now.** Everything downstream depends on this existing. It also starts
your cost meter, so you want it up, verified, and torn down efficiently.

**Steps.**

1. In the Hetzner console: create a project, then Security → API Tokens →
   generate a **Read & Write** token.

2. Find your public address: `curl -4 ifconfig.me`

3. Configure Terraform:

   ```bash
   cd infra/terraform
   cp terraform.tfvars.example terraform.tfvars
   # edit: paste the token; set allowed_admin_ipv4 = ["YOUR.IP/32"]
   cd ../..
   ```

4. Provision and install:

   ```bash
   make up
   export KUBECONFIG=$PWD/infra/terraform/kubeconfig.yaml
   make observability
   make workload
   make verify
   ```

**Done when.** `make verify` passes all twelve checks and exits zero.

**What goes wrong.**
- *Workers never join.* Check cloud-init on the control plane:
  `ssh root@<ip> journalctl -u cloud-final -n 50`. Usually the API server was
  not ready when the agent tried to join; the script retries, so wait longer
  before intervening.
- *Chaos Mesh pods crash.* The containerd socket path differs on k3s. It is
  already set to `/run/k3s/containerd/containerd.sock` in the script — if you
  changed it, change it back.
- *Timeouts during `make workload`.* Image pulls for eleven services take
  fifteen to twenty minutes. This is normal. Use the time for the writing
  track.

**Time.** Two to three hours the first time, mostly waiting.

**Cost.** Roughly €0.20 for the session.

---

# Stage 2 — Probe the metrics

**Goal.** Establish which of the 42 PromQL expressions in your scenario
library actually return data.

**Why this is the single most important early step.** Every predicate, the E3
confidence estimator, and every resolution check depends on these series
existing. If they do not, and you discover it in week five, the affected runs
are invalid. Discovering it now costs an afternoon.

**Steps.**

```bash
kubectl port-forward -n observability \
  svc/kube-prom-kube-prometheus-prometheus 9090:9090 &
kubectl port-forward -n boutique svc/frontend 8080:80 &

# generate traffic first, or request-based series will not exist yet
for i in $(seq 1 300); do curl -s localhost:8080 > /dev/null; done
sleep 60

python3 harness/probe_metrics.py
```

**Done when.** You have a list of which expressions returned data and which
did not. **Expect failures.** The gRPC histogram series
(`grpc_server_handling_seconds_bucket`) depend on what Online Boutique
exposes, and label names may not match my assumptions.

**What to do with the result.**
- *Most expressions return data* → proceed to Stage 3.
- *Many gRPC series are empty* → before building anything, rewrite affected
  predicates around series that do exist. Options: use
  `container_network_*` and `kube_*` series instead of application-level
  histograms; or add a service mesh or exporter sidecar; or redesign the
  affected scenario around observable signals. Do not build on predicates that
  cannot be evaluated.

**Then tear down.**

```bash
make down
```

**Time.** One to two hours.

---

# Stage 3 — Build the agent core

**Goal.** A program that gathers cluster state, sends it to Claude, and
returns a structured decision.

**Why here.** It depends on knowing which metrics exist (Stage 2) and it must
exist before the harness can call it (Stage 5).

**What gets built.**

1. **Cluster view** — a read-only interface over the Kubernetes API,
   Prometheus, and Loki. Supplies pod status, recent logs, metric queries,
   deployment history, and the pod/replica counts the safety gate needs for
   blast-radius calculation.

2. **Tool catalogue** — the R0 read-only actions the agent may call during
   reasoning: `describe_pod`, `get_logs`, `query_metrics`, `get_events`,
   `rollout_history`. Already declared in `agent/actions.py`.

3. **Context builder** — turns raw alerts into the compact `IncidentContext`
   the model receives: deduplicated alerts, severity score, affected workload,
   recent logs, resource state, deployment history, one-hop dependencies.

4. **Reasoning loop** — a ReAct-style loop, capped at eight steps, that
   alternates between calling read-only tools and reasoning, then emits a
   structured decision: `{root_cause, target, action, params, confidence,
   justification}`.

5. **Runbook retrieval** — runbooks chunked and embedded, top-5 retrieved by
   similarity and injected into the prompt. This is also your retrieval
   ablation: running with it off is one of your experimental conditions.

**Done when.** You can run the agent by hand against a manually broken
cluster and get back a sensible structured decision.

**What goes wrong.** The model returns prose instead of valid JSON. Enforce a
schema, validate the response, and retry once on failure — then count
persistent failures as a result, not a bug to hide.

**Time.** Ten to fifteen hours.

---

# Stage 4 — Build the three confidence estimators

**Goal.** Three independent ways of scoring how confident the agent is,
so that confidence becomes an experimental variable rather than an assumption.

**Why separate from Stage 3.** This is your strongest novel contribution and
the direct answer to your supervisor's sharpest criticism. It deserves to be
built and tested deliberately, not folded into the agent as an afterthought.

**What gets built.**

- **E1 verbalised** — the model emits a scalar in its structured output.
  Cheap, and known to be overconfident. This is the naive baseline.

- **E2 self-consistency** — the diagnosis is sampled five times at
  temperature 0.7. Each response is reduced to a canonical
  `(root_cause, target, action)` triple; confidence is the modal agreement
  fraction. Costs five calls instead of one.

- **E3 evidence-grounded** — each candidate root cause has verification
  predicates in the scenario definition. Confidence is the weighted fraction
  that evaluate true against live cluster state. This is the only estimator
  grounded in observed reality rather than model self-report.

**Done when.** All three produce a score in [0,1] for the same incident, and
you can see them disagree — which is exactly the phenomenon you are studying.

**Time.** Six to eight hours.

---

# Stage 5 — Build the evaluation harness

**Goal.** One command runs a scenario end to end, unattended, and records
everything.

**Why this is the hardest stage.** It is also where most projects like this
slip. Budget more time than feels necessary.

**The loop it must implement.**

1. Validate the environment is clean before starting
2. Record pre-injection state (needed for teardown of patch-based scenarios)
3. Inject the fault
4. Wait `settle_seconds`
5. Invoke the agent under a named policy and confidence estimator
6. Pass the proposal through the safety gate
7. Execute or escalate accordingly
8. Watch the resolution check until it holds for `sustain_seconds` or times out
9. Classify the outcome with `harness/outcomes.py`
10. Tear down the fault
11. **Wait for the cluster to return to baseline** — verify, do not assume
12. Write a result record to disk

**The critical detail: run independence.** If run 47 is contaminated by
residue from run 46, your results are worthless and you will not easily
notice. The harness must verify baseline health between runs, not merely wait
a fixed period. Treat a failed baseline check as a hard stop.

**Done when.** You can run a single scenario end to end unattended, twice in
a row, and get consistent results.

**What goes wrong.** Teardown that does not fully restore state — especially
for `kubectl_patch` scenarios where the original spec must be captured before
injection, not reconstructed afterwards.

**Time.** Twelve to eighteen hours. This is the critical path.

---

# Stage 6 — Pilot runs

**Goal.** Find harness bugs before they contaminate the real dataset.

**Steps.** Run four scenarios — one from each class — under one policy, once
each. Inspect every result record by hand. Ask of each: did the fault inject
correctly? Did the agent see the right evidence? Did the gate decide as the
policy specifies? Did teardown fully restore baseline?

**Done when.** Four runs complete cleanly and you believe every field in the
output.

**What goes wrong.** This is where you discover that a resolution check never
fires, or a scenario's settle time is too short, or the model consistently
misreads one context field. All are cheap to fix now and expensive later.

**Time.** Four to six hours, plus fixes.

---

# Stage 7 — Full experimental runs

**Goal.** The complete dataset.

**Design.** 12 scenarios × 3 policies × 3 repetitions × 2 models ≈ 216 runs,
plus a retrieval-off ablation. Each run takes roughly ten to twenty minutes
including settle, resolution wait, and baseline recovery — so expect
40–70 hours of wall-clock cluster time.

**Practical approach.** Run in batches by scenario class. Keep the cluster up
across a batch rather than cycling it. Checkpoint results to disk after every
run so a crash costs one run, not the batch.

**Baselines.** Also run the no-op baseline (observe only) and the rule-based
baseline (fixed alerts, pre-set responses). Run the human baseline yourself,
timed, without the agent — and note in your limitations chapter that a
self-administered baseline is biased, because you designed the scenarios.

**Done when.** You have a complete results file with no gaps.

**What goes wrong.** API rate limits and transient cluster failures. Make the
harness resumable: it should skip runs already recorded.

**Time.** Two weeks of mostly-unattended running. Write during it.

---

# Stage 8 — Analysis

**Goal.** Turn 216 rows into findings.

**What to produce.**

- **The headline curve.** Sweep the confidence threshold and plot automation
  rate against error rate. Where does it bend? That point is your answer to
  the research question.
- **Calibration comparison.** For each estimator: reliability diagram,
  Expected Calibration Error, Brier score, AUROC for action success. Which one
  can actually be thresholded safely?
- **Outcome breakdown.** All four cells per configuration, with harmful
  successes reported separately. This is the number prior work does not have.
- **Error taxonomy.** Using each scenario's recorded distractors, report *how*
  the agent was wrong, not only that it was.
- **Baseline comparison.** Agent versus rule-based versus human on MTTR,
  resolution rate, and safety.
- **Statistics.** Small samples, so report effect sizes alongside significance
  and be explicit about the limits of *n* = 3 per cell.

**Time.** Eight to twelve hours.

---

# Stage 9 — Write-up and submission

**Goal.** The dissertation, plus released code and benchmark.

By this point most chapters should already be drafted from the writing track.
What remains is results, discussion, conclusion, and assembly.

**Final checks.** Reference list at least two pages. No bold in body text —
italics only. Every technical term glossed on first use. Every claim either
cited or demonstrated. Limitations chapter substantive — the rubric requires
contribution *and limitations* fully justified for a distinction.

**Time.** The final two weeks, with buffer.

---

# The writing track (runs in parallel from week one)

| When | Write |
|---|---|
| Weeks 1–2 | Literature review, including the structured comparison table demonstrating the diagnosis-versus-mitigation gap |
| Week 2 | Problem definition, fully cited |
| Week 3 | Design chapter — safety gate formalism, confidence estimators, action tiers |
| Week 4 | Methodology — benchmark construction, experimental design, metrics |
| Weeks 5–6 | Results scaffolding: table and figure templates, ready to fill |
| Week 7 | Results and discussion as data arrives |
| Week 8 | Conclusion, abstract, references, limitations |

**Keep a decisions log from day one.** Every time you choose something —
CX over CPX servers, twelve scenarios not thirty, excluding log-probability
confidence — write one line saying what you chose and why. That log becomes
your design justification and limitations chapters, and it is far better than
reconstructing reasoning from memory in October.

---

# Schedule

| Week | Dates | Build | Write |
|---|---|---|---|
| 1 | 15–21 Aug | Stages 0–2: environment up, metrics probed | Literature review |
| 2 | 22–28 Aug | Stage 3: agent core | Literature review, problem definition |
| 3 | 29 Aug–4 Sep | Stage 4: confidence estimators | Design chapter |
| 4 | 5–11 Sep | Stage 5: harness | Methodology |
| 5 | 12–18 Sep | Stage 6: pilot, then begin Stage 7 | Results scaffolding |
| 6 | 19–25 Sep | Stage 7: full runs | Draft results as data arrives |
| 7 | 26 Sep–2 Oct | Stage 8: analysis | Results and discussion |
| 8 | 3–9 Oct | Code and benchmark release | Conclusion, limitations, references |
| 9 | 10–12 Oct | Buffer | Final proofread, submit |

**Scope freeze at the end of week 3.** No new scenarios after that date, no
matter how tempting.

**If you fall behind**, cut in this order: repetitions 3 → 2; then the second
model; then policies 3 → 2. Cut scenarios last — coverage across fault
classes is what makes the benchmark a contribution.

---

# Costs

| Item | Estimate |
|---|---|
| Hetzner cluster | €12–25 total with teardown discipline |
| Claude API (development, cheap tier) | €10–30 |
| Claude API (full runs, two models) | €40–120 |
| **Total** | **roughly €60–175** |

Servers bill while they *exist*, not while they run. Only `make down` stops
the charge.

---

# What to do in the next hour

1. Create the Hetzner account — start any verification delay now.
2. `pip install -r requirements.txt && python3 scenarios/loader.py`
3. Install `terraform`, `kubectl`, `helm`, `hcloud`; generate an SSH key.
4. Open a file called `decisions.md` and write the first entry.

Then Stage 1 when the account clears.
