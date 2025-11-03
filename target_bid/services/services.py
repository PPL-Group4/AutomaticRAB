from decimal import Decimal
from target_bid.validators import TargetBudgetInput

class TargetBudgetConverter:
    """Converts validated target input ( percentage or absolute) into nominal rupiah value."""

    @staticmethod
    def to_nominal(target_input: TargetBudgetInput,current_total: Decimal) -> Decimal:
        if not isinstance(current_total, Decimal):
            raise TypeError("Expected 'current_total' to be of type 'Decimal'.")

        if target_input.mode=="percentage":
            nominal =(current_total*target_input.value)/Decimal("100")
        else:
            nominal = target_input.value


        return nominal.quantize(Decimal("0.01"))