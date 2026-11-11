"""GET /metrics under SGLang's metric names and `model_name` label, so the MISA "LLM Monitoring" Grafana dashboard reads
a Flide workload as it reads an SGLang one. Only what Flide measures: requests in flight (all counted as running, Flide
has no separate queue to report, so `num_queue_reqs` is 0), finished requests, prompt and answer tokens, server time
per request as both e2e latency and time to first token (a System One answer is its first token), the session cache
when there is one, and process memory and GC.

ponytail: per process; with --frontends each front end reports only its own requests.
"""
from __future__ import annotations

import gc
import os

# SGLang's e2e buckets start at 0.1 s; Flide answers are often faster, so a few smaller ones go first.
BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 20.0, 40.0, 60.0, 120.0, 300.0,
           600.0)


class Metrics:
    """Updated from the event loop only, so no lock."""

    def __init__(self, model_name: str = "", engine=None):
        self.label = f'{{model_name="{model_name}"}}'
        self.engine = engine
        self.running = self.requests = self.prompt_tokens = self.generation_tokens = 0
        self.buckets = [0] * len(BUCKETS)
        self.seconds = 0.0

    def finished(self, seconds: float, ok: bool) -> None:
        self.running -= 1
        if not ok:
            return
        self.requests += 1
        self.seconds += seconds
        for i, le in enumerate(BUCKETS):
            if seconds <= le:
                self.buckets[i] += 1

    def usage(self, usage) -> None:
        self.prompt_tokens += usage.input_tokens
        self.generation_tokens += usage.output_tokens

    def text(self) -> str:
        m, out = self.label, []

        def one(name, kind, value, sample=None):
            out.extend((f"# TYPE sglang:{name} {kind}", f"sglang:{sample or name}{m} {value}"))

        one("num_running_reqs", "gauge", self.running)
        one("num_queue_reqs", "gauge", 0)
        one("num_requests", "counter", self.requests, "num_requests_total")
        one("prompt_tokens", "counter", self.prompt_tokens, "prompt_tokens_total")
        one("generation_tokens", "counter", self.generation_tokens, "generation_tokens_total")
        for name in ("e2e_request_latency_seconds", "time_to_first_token_seconds"):
            out.append(f"# TYPE sglang:{name} histogram")
            lab = m[1:-1]
            out += [f'sglang:{name}_bucket{{{lab},le="{le}"}} {n}' for le, n in zip(BUCKETS, self.buckets)]
            out += [f'sglang:{name}_bucket{{{lab},le="+Inf"}} {self.requests}',
                    f"sglang:{name}_sum{m} {self.seconds:.6f}", f"sglang:{name}_count{m} {self.requests}"]
        s = getattr(self.engine, "sessions", None)
        if s is not None:
            one("cache_hit_rate", "gauge", f"{s.hits / max(1, s.hits + s.misses):.6f}")
            one("token_usage", "gauge", f"{s.used / max(1, s.budget):.6f}")
        try:
            rss = int(open("/proc/self/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            out += ["# TYPE process_resident_memory_bytes gauge", f"process_resident_memory_bytes {rss}"]
        except OSError:
            pass
        out.append("# TYPE python_gc_collections_total counter")
        out += [f'python_gc_collections_total{{generation="{g}"}} {st["collections"]}'
                for g, st in enumerate(gc.get_stats())]
        return "\n".join(out) + "\n"


if __name__ == "__main__":
    from types import SimpleNamespace

    x = Metrics("m", SimpleNamespace(sessions=SimpleNamespace(hits=1, misses=3, used=5, budget=10)))
    x.running = 2
    x.finished(0.03, True)
    x.finished(1.5, False)
    x.usage(SimpleNamespace(input_tokens=7, output_tokens=1))
    t = x.text()
    assert 'sglang:num_running_reqs{model_name="m"} 0' in t
    assert 'sglang:num_requests_total{model_name="m"} 1' in t
    assert 'sglang:e2e_request_latency_seconds_bucket{model_name="m",le="0.025"} 0' in t
    assert 'sglang:e2e_request_latency_seconds_bucket{model_name="m",le="0.05"} 1' in t
    assert 'sglang:prompt_tokens_total{model_name="m"} 7' in t and 'sglang:cache_hit_rate{model_name="m"} 0.25' in t
    print(t)
