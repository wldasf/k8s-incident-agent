# Citations used in the literature review — VERIFY ALL BEFORE SUBMISSION

Every key below appears in `literature_review.md`. Some were found via
secondary sources during drafting and **must be confirmed against the
primary source**. Do not submit an unverified citation.

## Confirmed — high confidence

| Key | Reference | Status |
|---|---|---|
| `Yao23` | S. Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models," ICLR 2023. arXiv:2210.03629 | Solid |
| `Lewis20` | P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS 2020. arXiv:2005.11401 | Solid |
| `Guo17` | C. Guo et al., "On Calibration of Modern Neural Networks," ICML 2017 | Solid |
| `Kadavath22` | S. Kadavath et al., "Language Models (Mostly) Know What They Know," 2022. arXiv:2207.05221 | Solid |
| `Wang23` | X. Wang et al., "Self-Consistency Improves Chain of Thought Reasoning," ICLR 2023 | Solid |
| `Chen25` | Y. Chen et al., "AIOpsLab: A Holistic Framework to Evaluate AI Agents for Enabling Autonomous Clouds," MLSys 2025. arXiv:2501.06706 | Solid |
| `Chen23` | Y. Chen et al., "Automatic Root Cause Analysis via Large Language Models for Cloud Incidents," 2023. arXiv:2305.15778 | Solid |
| `Wang24` | Z. Wang et al., "RCAgent: Cloud Root Cause Analysis by Autonomous Agents with Tool-Augmented LLMs," CIKM 2024, pp. 4966–4974 | Solid |
| `Oops25` | "When AIOps Become 'AI Oops': Subverting LLM-driven IT Operations via Telemetry Manipulation," 2025. arXiv:2508.06394 | Solid |
| `K8sGPT` | K8sGPT project documentation, https://k8sgpt.ai | Cite homepage |
| `Holmes` | HolmesGPT project, https://github.com/robusta-dev/holmesgpt | Verify URL |

## Found during drafting — MUST VERIFY

| Key | Reference as recorded | What to check |
|---|---|---|
| `Oper26` | "OperAID: Benchmarking LLM Agents for Autonomous Kubernetes Fault Remediation," 2026 | Venue, authors, exact figures (10.9% → 61.1%, 900 experiments) |
| `Meta26` | "MetaKube: An Experience-Aware LLM Framework for Kubernetes Failure Diagnosis," WWW 2026. doi:10.1145/3774904.3792631 | Authors; the 15.3% EPMN figure |
| `Rec26` | "Can LLMs Really Recover Microservice Failures? A Recovery-Aware Evaluation of Diagnosis-to-Action Reasoning," arXiv:2607.04623 | Authors, venue |
| `Xiang25` | Q. Wang / Xiang et al., "Simplifying Root Cause Analysis in Kubernetes with StateGraph and LLM (SynergyRCA)," 2025. arXiv:2506.02490 | Author order; the 0.90 precision figure |
| `Chen26` | Y. Chen et al., "STRATUS: A Multi-Agent System for Autonomous Reliability Engineering of Modern Clouds," 2026. arXiv:2506.02009 | Year, venue |
| `Li25` | Y. Li et al., "COCA: Generative Root Cause Analysis for Distributed Systems with Code Knowledge," 2025. arXiv:2503.23051 | Authors |
| `Pei25` | C. Pei et al., "Flow-of-Action: SOP Enhanced LLM-Based Multi-Agent System for Root Cause Analysis," 2025. arXiv:2502.08224 | Authors |
| `Jha25` | S. Jha et al., "ITBench: Evaluating AI Agents across Diverse Real-World IT Automation Tasks," ICML 2025 | Venue confirmation |
| `AIR26` | "AIR: Improving Agent Safety through Incident Response," 2026. arXiv:2602.11749 | Authors, venue |
| `Cap26` | "Oversight Has a Capacity: Calibrating Agent Guards to a Subjective, Fatiguing Human," 2026. arXiv:2606.08919 | Authors; the inverted-U claim |
| `Xiong24` | S. Xiong et al., on verbalized confidence in LLMs, 2024 | **Full citation not yet established** |
| `Meas26` | "A Measurement Substrate for Agentic Kubernetes Operations," 2026 | **arXiv id uncertain — verify or drop** |

## Non-academic sources — use sparingly

These are practitioner sources. They are legitimate evidence of *industry
practice* but must not be cited as research findings. Prefer an academic
source where one exists; where one does not, that absence is itself the
argument.

| Key | Source | Used for |
|---|---|---|
| `Zyl26` | Zylos Research, "LLM Calibration and Uncertainty Quantification in Production AI Agents," Apr 2026 | Confidence-gated escalation as dominant pattern; the ICML 2025 UQ benchmark gap. **Trace the ICML position paper and cite it directly.** |
| `Dig26` | digitalapplied.com, "Human-in-the-Loop Escalation Design for AI Agents," Jun 2026 | Four-tier risk classification; 90%-claimed vs 75%-actual |
| `Gal26` | Galileo, "How to Build Human-in-the-Loop Oversight for AI Agents," Apr 2026 | Calibration and discrimination as independent properties |
| `Dev26` | DEV Community, HITL patterns and best practices, Apr 2026 | Recommendation against single-signal gating |

## Priority actions

1. **Trace the ICML 2025 UQ position paper.** It is the single strongest
   citation for the gap this project addresses, and it is currently sourced
   second-hand. Find and cite the primary.
2. **Read OperAID properly.** It is the closest work to this project. The
   review must state precisely how this project differs, and that statement
   must be accurate.
3. **Resolve `Xiong24` and `Meas26`** or remove them; each currently carries
   a claim on an uncertain citation.
4. Replace practitioner sources with academic equivalents wherever possible.
