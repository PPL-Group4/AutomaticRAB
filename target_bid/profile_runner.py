"""
Run lightweight profiling for target_bid service functions.
Usage:
    python manage.py runscript target_bid.profile_runner
or
    python -m target_bid.profile_runner
"""

import cProfile
import pstats
from decimal import Decimal

from target_bid.service_utils.budgetservice import TargetBudgetConverter
from target_bid.service_utils.proportional_adjustment import ProportionalAdjustmentCalculator
from target_bid.validators import TargetBudgetInput


def run_profile():
    """Run a representative workload to measure performance of conversion and adjustment."""
    data = TargetBudgetInput(mode="percentage", value=Decimal("80"))

    for _ in range(10000):
        TargetBudgetConverter.to_nominal(data, Decimal("1000000"))

    for _ in range(5000):
        ProportionalAdjustmentCalculator.compute(Decimal("1000000"), Decimal("800000"))


def main():
    print("🔍 Profiling target_bid computational performance...")
    with cProfile.Profile() as pr:
        run_profile()

    stats = pstats.Stats(pr)
    stats.strip_dirs().sort_stats("cumulative").print_stats(15)


if __name__ == "__main__":
    main()
