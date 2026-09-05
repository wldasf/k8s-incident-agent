# Citations used in the literature review — VERIFY ALL BEFORE SUBMISSION

Every key below appears in `literature_review.md`. Some were found via
secondary sources during drafting and **must be confirmed against the
primary source**. Do not submit an unverified citation.

## Confirmed

| Key | Reference | Notes |
|---|---|---|
| `Yao23` | S. Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models," ICLR 2023. arXiv:2210.03629 | Solid |
| `Lewis20` | P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS 2020. arXiv:2005.11401 | Solid |
| `Guo17` | C. Guo et al., "On Calibration of Modern Neural Networks," ICML 2017 | Solid |
| `Kadavath22` | S. Kadavath et al., "Language Models (Mostly) Know What They Know," 2022. arXiv:2207.05221 | Solid |
| `Wang23` | X. Wang et al., "Self-Consistency Improves Chain of Thought Reasoning," ICLR 2023 | Solid |
| `Chen25` | Y. Chen et al., "AIOpsLab: A Holistic Framework to Evaluate AI Agents for Enabling Autonomous Clouds," MLSys 2025. arXiv:2501.06706 | Solid. Note: same first author as Stratus25. |
| `Chen23` | Y. Chen et al., "Automatic Root Cause Analysis via Large Language Models for Cloud Incidents," 2023. arXiv:2305.15778 | Solid |
| `Wang24` | Z. Wang et al., "RCAgent: Cloud Root Cause Analysis by Autonomous Agents with Tool-Augmented LLMs," CIKM 2024, pp. 4966–4974 | Solid |
| `Oops25` | "When AIOps Become 'AI Oops': Subverting LLM-driven IT Operations via Telemetry Manipulation," 2025. arXiv:2508.06394 | Solid |
| `Xiong24` | M. Xiong, Z. Hu, X. Lu, Y. Li, J. Fu, J. He, B. Hooi, "Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs," ICLR 2024. arXiv:2306.13063 | Verified. Benchmarks black-box confidence on calibration *and* failure prediction; finds verbalized confidence overconfident; covers sampling-consistency aggregation (E2). |
| `Meas26` | J. Odmark, G. Rubin, D. van der Vyver, "A Measurement Substrate for Agentic Kubernetes Operations: Methodology and a Case Study in Retrieval-Compounding Falsification," 2026. arXiv:2605.23058 | Verified. Argues claims about Kubernetes agents are largely unfalsifiable for want of agent-disabled controls; reports three confounds its instrumentation caught. |
| `Kirchhof25` | M. Kirchhof, G. Kasneci, E. Kasneci, "Position: Uncertainty Quantification Needs Reassessment for Large-language Model Agents," ICML 2025, PMLR 267. arXiv:2505.22655 | Read in full. Supports reasoning from the task rather than the aleatoric/epistemic labels (§2.3), and numeric thresholds for automated abstention (§4.3). Does **not** support any claim about a missing agentic UQ benchmark. |
| `K8sGPT` | K8sGPT project documentation, https://k8sgpt.ai | Cite homepage |
| `Holmes` | HolmesGPT project, https://github.com/robusta-dev/holmesgpt | Verify URL |
| `Stratus25` | Y. Chen, J. Pan, J. Clark, Y. Su, N. Zheutlin, B. Bhavya, R. Arora, Y. Deng, S. Jha, T. Xu, "STRATUS: A Multi-agent System for Autonomous Reliability Engineering of Modern Clouds," 2025. arXiv:2506.02009 | Verified. Formalises Transactional No-Regression, a safety specification for safe exploration. |
| `Meta26` | W. Sun, T. Wang, X. Tian, W. Lan, X. Feng, H. Li, F. Wang, "MetaKube: An Experience-Aware LLM Framework for Kubernetes Failure Diagnosis," Proc. ACM Web Conference (WWW) 2026. doi:10.1145/3774904.3792631, arXiv:2603.23580 | Verified. 15.3% EPMN improvement figure confirmed. arXiv preprint accessible; ACM version paywalled. |

## Found during drafting — MUST VERIFY

| Key | Reference as recorded | What to check |
|---|---|---|
| `Rec26` | "Can LLMs Really Recover Microservice Failures? A Recovery-Aware Evaluation of Diagnosis-to-Action Reasoning," arXiv:2607.04623 | Authors, venue |
| `Xiang25` | Q. Wang / Xiang et al., "Simplifying Root Cause Analysis in Kubernetes with StateGraph and LLM (SynergyRCA)," 2025. arXiv:2506.02490 | Author order; the 0.90 precision figure |
| `Li25` | Y. Li et al., "COCA: Generative Root Cause Analysis for Distributed Systems with Code Knowledge," 2025. arXiv:2503.23051 | Authors |
| `Pei25` | C. Pei et al., "Flow-of-Action: SOP Enhanced LLM-Based Multi-Agent System for Root Cause Analysis," 2025. arXiv:2502.08224 | Authors |
| `Jha25` | S. Jha et al., "ITBench: Evaluating AI Agents across Diverse Real-World IT Automation Tasks," ICML 2025 | Venue confirmation |
| `AIR26` | "AIR: Improving Agent Safety through Incident Response," 2026. arXiv:2602.11749 | Authors, venue |
| `Cap26` | "Oversight Has a Capacity: Calibrating Agent Guards to a Subjective, Fatiguing Human," 2026. arXiv:2606.08919 | Authors; the inverted-U claim |

## Non-academic sources — use sparingly

Legitimate evidence of *industry practice* but not of research findings.
Prefer an academic source where one exists.

| Key | Source | Used for |
|---|---|---|
| `Zyl26` | Zylos Research, "LLM Calibration and Uncertainty Quantification in Production AI Agents," Apr 2026. https://zylos.ai/research/2026-04-18-llm-calibration-uncertainty-production-agents/ | Confidence-gated escalation as the dominant industry pattern **only**. Its claim that no mature agentic UQ benchmark exists is an embellishment of arXiv:2505.22655, which makes no such claim; that assertion was removed from the dissertation rather than re-cited. |
| `Dig26` | digitalapplied.com, "Human-in-the-Loop Escalation Design for AI Agents," Jun 2026 | Four-tier risk classification; 90%-claimed vs 75%-actual |
| `Gal26` | Galileo, "How to Build Human-in-the-Loop Oversight for AI Agents," Apr 2026 | Calibration and discrimination as independent properties |
| `Dev26` | DEV Community, HITL patterns and best practices, Apr 2026 | Recommendation against single-signal gating |

## Remaining actions

1. **Read AIOpsLab in full.** §5.6 makes claims about how this study differs
   from it and those claims must be accurate.
2. Verify the seven entries in the MUST VERIFY table.
3. Replace practitioner sources with academic equivalents where possible.