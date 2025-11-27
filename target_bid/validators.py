from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

# Thousand/decimal separator patterns reused from other validators in the project.
_THOUSAND_DOT_DECIMAL_COMMA = re.compile(r"^\d{1,3}(\.\d{3})+,\d+$")
_THOUSAND_COMMA_DECIMAL_DOT = re.compile(r"^\d{1,3}(,\d{3})+\.\d+$")

_ERR_NUMERIC_REQUIRED = "Target budget must be a numeric value."


@dataclass(frozen=True)
class TargetBudgetInput:
    """Normalised representation of the target budget entry."""

    mode: str
    value: Decimal


class ErrorCollector:
    """Collects validation messages per field and raises once on demand."""

    def __init__(self) -> None:
        self._messages: Dict[str, list[str]] = defaultdict(list)

    def add(self, field: str, message: str) -> None:
        self._messages[field].append(message)

    def has(self, field: str) -> bool:
        return bool(self._messages.get(field))

    def data(self) -> Dict[str, list[str]]:
        return {field: msgs for field, msgs in self._messages.items() if msgs}

    def raise_if_any(self) -> None:
        payload = self.data()
        if payload:
            raise ValidationError(payload)


class NumericNormaliser:
    """Normalises numeric strings regardless of locale-specific separators."""

    @staticmethod
    def normalise(candidate: str) -> str:
        if _THOUSAND_DOT_DECIMAL_COMMA.match(candidate):
            return candidate.replace(".", "").replace(",", ".")
        if _THOUSAND_COMMA_DECIMAL_DOT.match(candidate):
            return candidate.replace(",", "")

        if "," in candidate and "." not in candidate:
            return candidate.replace(",", ".")
        if "," in candidate and "." in candidate:
            if candidate.rfind(",") > candidate.rfind("."):
                return candidate.replace(".", "").replace(",", ".")
            return candidate.replace(",", "")
        return candidate


class NumericParser:
    """Responsible for converting arbitrary inputs into Decimal values."""

    def __init__(self, errors: ErrorCollector, field: str) -> None:
        self._errors = errors
        self._field = field

    def parse(self, value: Any, *, allow_percent: bool) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None

            if allow_percent:
                text = text.replace("%", "")
            elif "%" in text:
                self._errors.add(
                    self._field, "Percentage input is not allowed when mode is absolute."
                )
                return None

            text = re.sub(r"(?i)rp|idr", "", text)
            text = text.replace(" ", "").replace("_", "")

            cleaned = re.sub(r"[^0-9.,+-]", "", text)
            if not any(ch.isdigit() for ch in cleaned):
                self._errors.add(self._field, _ERR_NUMERIC_REQUIRED)
                return None

            normalised = NumericNormaliser.normalise(cleaned)
            try:
                return Decimal(normalised)
            except InvalidOperation:
                self._errors.add(self._field, _ERR_NUMERIC_REQUIRED)
                return None

        self._errors.add(self._field, _ERR_NUMERIC_REQUIRED)
        return None


class ModeStrategy(ABC):
    """Contract for individual mode validation strategies."""

    def __init__(self, aliases: Iterable[str]) -> None:
        self._aliases = {alias.lower() for alias in aliases}

    def matches(self, candidate: str) -> bool:
        return candidate in self._aliases

    @property
    @abstractmethod
    def canonical_name(self) -> str:
        ...

    @property
    @abstractmethod
    def allow_percent(self) -> bool:
        ...

    @abstractmethod
    def validate(self, value: Decimal, errors: ErrorCollector) -> None:
        ...


class PercentageModeStrategy(ModeStrategy):
    def __init__(self) -> None:
        super().__init__({"percent", "percentage", "%"})

    @property
    def canonical_name(self) -> str:
        return "percentage"

    @property
    def allow_percent(self) -> bool:
        return True

    def validate(self, value: Decimal, errors: ErrorCollector) -> None:
        if value <= 0 or value > 100:
            errors.add("target_budget", "Percentage value must be between 0 and 100.")


class AbsoluteModeStrategy(ModeStrategy):
    def __init__(self) -> None:
        super().__init__({"absolute", "currency", "rupiah", "idr", "value"})

    @property
    def canonical_name(self) -> str:
        return "absolute"

    @property
    def allow_percent(self) -> bool:
        return False

    def validate(self, value: Decimal, errors: ErrorCollector) -> None:
        if value <= 0:
            errors.add("target_budget", "Target budget must be greater than zero.")


class ModeResolver:
    """Translates raw mode inputs into concrete strategies."""

    def __init__(self, strategies: Iterable[ModeStrategy]) -> None:
        self._strategies = tuple(strategies)

    def resolve(self, candidate: Any, errors: ErrorCollector) -> Optional[ModeStrategy]:
        if not isinstance(candidate, str):
            errors.add("mode", "Mode must be either 'percentage' or 'absolute'.")
            return None

        key = candidate.strip().lower()
        for strategy in self._strategies:
            if strategy.matches(key):
                return strategy

        errors.add("mode", "Mode must be either 'percentage' or 'absolute'.")
        return None


def validate_target_budget_input(value: Any, *, mode: Any) -> TargetBudgetInput:
    """Validate and normalise the target budget entry provided by the user."""

    errors = ErrorCollector()
    resolver = ModeResolver((PercentageModeStrategy(), AbsoluteModeStrategy()))
    strategy = resolver.resolve(mode, errors)

    parser = NumericParser(errors, "target_budget")
    numeric_value = parser.parse(value, allow_percent=bool(strategy and strategy.allow_percent))

    if numeric_value is None and not errors.has("target_budget"):
        errors.add("target_budget", "Target budget is required.")
    elif numeric_value is not None and strategy is not None:
        strategy.validate(numeric_value, errors)
    elif numeric_value is not None and strategy is None:
        # No recognised strategy means we only report the mode error collected earlier.
        pass

    errors.raise_if_any()

    assert isinstance(numeric_value, Decimal)
    canonical_name = strategy.canonical_name if strategy is not None else "absolute"
    return TargetBudgetInput(mode=canonical_name, value=numeric_value)


def _normalise_mode(mode: Any) -> Optional[str]:
    """Legacy helper retained for compatibility with existing callers."""

    resolver = ModeResolver((PercentageModeStrategy(), AbsoluteModeStrategy()))
    errors = ErrorCollector()
    strategy = resolver.resolve(mode, errors)
    if strategy is None:
        return None
    return strategy.canonical_name


def _normalise_numeric_string(candidate: str) -> str:
    """Normalise thousand/decimal separators to standard dot-decimal format."""

    return NumericNormaliser.normalise(candidate)
