"""
HTTP prober.

Online Boutique does not expose application-level Prometheus metrics
(request latency histograms, HTTP status counters), so those signals cannot
come from PromQL. This module measures them directly: the harness probes the
frontend over a port-forward and computes latency percentiles and error rate
from observed responses.

This is a deliberate methodological choice, not a workaround: the probe
measures what a user of the system experiences rather than what the
application self-reports, and it is independent of the workload's
instrumentation quality. Its limitation — visibility only at the frontend,
not per-service — is recorded in the study's limitations.

Probe statistics exposed to predicates and resolution checks:
    p95_latency_ms, p99_latency_ms   response-time percentiles
    error_rate                        fraction of responses with status >= 500
                                      (connection failures count as errors)
    requests_per_s                    achieved throughput during the window
"""

from __future__ import annotations

import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_URL = "http://localhost:8080/"
DEFAULT_PATHS = ["/", "/product/OLJCESPC7Z", "/cart"]


@dataclass
class ProbeResult:
    samples: int
    errors: int
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    requests_per_s: float

    def value(self, stat: str) -> float:
        return {
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "error_rate": self.error_rate,
            "requests_per_s": self.requests_per_s,
        }[stat]


def probe(
    base_url: str = DEFAULT_URL,
    paths: list[str] | None = None,
    duration_s: float = 30.0,
    interval_s: float = 0.2,
    timeout_s: float = 10.0,
) -> ProbeResult:
    """Probe the frontend for `duration_s`, one request every `interval_s`,
    rotating through `paths`. Timeouts and connection failures are counted as
    errors with latency equal to the timeout — a saturated or partitioned
    service should look slow and broken, not be silently dropped from the
    sample."""
    paths = paths or DEFAULT_PATHS
    latencies_ms: list[float] = []
    errors = 0
    n = 0
    start = time.monotonic()

    while time.monotonic() - start < duration_s:
        url = base_url.rstrip("/") + paths[n % len(paths)]
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                resp.read(1024)
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception:  # noqa: BLE001 - timeout, refused, reset all count
            status = 599
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        latencies_ms.append(min(elapsed_ms, timeout_s * 1000.0))
        if status >= 500:
            errors += 1
        n += 1
        remaining = interval_s - (time.monotonic() - t0)
        if remaining > 0:
            time.sleep(remaining)

    wall = max(time.monotonic() - start, 1e-6)
    qs = statistics.quantiles(latencies_ms, n=100) if len(latencies_ms) >= 10 else None
    return ProbeResult(
        samples=n,
        errors=errors,
        p95_latency_ms=qs[94] if qs else (max(latencies_ms) if latencies_ms else 0.0),
        p99_latency_ms=qs[98] if qs else (max(latencies_ms) if latencies_ms else 0.0),
        error_rate=errors / n if n else 1.0,
        requests_per_s=n / wall,
    )


def evaluate(stat: str, threshold: float, comparison: str, result: ProbeResult) -> bool:
    v = result.value(stat)
    if comparison == "gt":
        return v > threshold
    if comparison == "lt":
        return v < threshold
    if comparison == "eq":
        return v == threshold
    raise ValueError(f"unsupported comparison: {comparison}")


if __name__ == "__main__":
    r = probe(duration_s=15)
    print(f"samples={r.samples} errors={r.errors} error_rate={r.error_rate:.3f}")
    print(f"p95={r.p95_latency_ms:.0f}ms p99={r.p99_latency_ms:.0f}ms rps={r.requests_per_s:.1f}")
