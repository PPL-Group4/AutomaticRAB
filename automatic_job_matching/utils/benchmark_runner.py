# ...existing code...
import time
from statistics import mean
from typing import Callable, List, Tuple


class BenchmarkRunner:
    def __init__(self, func: Callable, runs: int = 5, warmup: int = 1):
        if runs < 0 or warmup < 0:
            raise ValueError("runs and warmup must be non-negative")
        self.func = func
        self.runs = int(runs)
        self.warmup = int(warmup)

    def run(self) -> dict:
        """Run warmup calls (not measured) then `runs` measured invocations.
        Returns metrics with times in milliseconds.
        """
        for _ in range(self.warmup):
            self.func()

        times: List[float] = []
        for _ in range(self.runs):
            start = time.perf_counter()
            self.func()
            end = time.perf_counter()
            times.append((end - start) * 1000.0)

        if not times:
            return {
                "runs": self.runs,
                "times_ms": [],
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
            }

        return {
            "runs": self.runs,
            "times_ms": times,
            "avg_ms": mean(times),
            "min_ms": min(times),
            "max_ms": max(times),
        }


def run_benchmark(func: Callable, repeats: int = 3) -> Tuple[List[float], float]:
    """Convenience wrapper returning per-run durations (ms) and total elapsed (ms)."""
    start_total = time.perf_counter()
    results: List[float] = []
    for _ in range(repeats):
        s = time.perf_counter()
        func()
        e = time.perf_counter()
        results.append((e - s) * 1000.0)
    end_total = time.perf_counter()

    total_elapsed_ms = (end_total - start_total) * 1000.0
    return results, total_elapsed_ms


