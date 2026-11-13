"""PATTERN (Behavioral): Strategy - interchangeable ticket-pricing rules."""
from abc import ABC, abstractmethod


class PricingStrategy(ABC):
    name = "base"

    @abstractmethod
    def price(self, show, seat) -> float: ...

    @staticmethod
    def _base(show, seat) -> float:
        return show.base_price * seat.seat_type.multiplier


class StandardPricing(PricingStrategy):
    name = "Standard"
    def price(self, show, seat): return round(self._base(show, seat), 2)


class WeekendPricing(PricingStrategy):
    name = "Weekend (+20%)"
    def price(self, show, seat): return round(self._base(show, seat) * 1.20, 2)


class StudentDiscountPricing(PricingStrategy):
    name = "Student (-15%)"
    def price(self, show, seat): return round(self._base(show, seat) * 0.85, 2)


def select_pricing(show, customer) -> PricingStrategy:
    """Student discount wins over weekend surcharge; otherwise weekend, otherwise standard."""
    if customer.is_student:
        return StudentDiscountPricing()
    if show.start_time.weekday() >= 5:
        return WeekendPricing()
    return StandardPricing()
