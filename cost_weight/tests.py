from decimal import Decimal
from services.cost_weight_calc import calculate_cost_weights

def test_simple_case():
    items = {"A": Decimal("2500"), "B": Decimal("1500"), "C": Decimal("1000")}
    result = calculate_cost_weights(items)
    assert result["A"] == Decimal("50.00")
    assert result["B"] == Decimal("30.00")
    assert result["C"] == Decimal("20.00")
    assert sum(result.values()) == Decimal("100.00")

def test_zero_total():
    items = {"A": Decimal("0"), "B": Decimal("0")}
    result = calculate_cost_weights(items)
    assert all(v == Decimal("0.00") for v in result.values())

def run_all_tests():
    test_simple_case()
    test_zero_total()
    print("✅ All tests passed!")

if __name__ == "__main__":
    run_all_tests()
