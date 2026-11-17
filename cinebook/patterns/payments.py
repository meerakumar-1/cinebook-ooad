"""PATTERN (Creational): Factory Method - each creator decides which PaymentProcessor to build."""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..errors import ValidationError


@dataclass
class PaymentResult:
    success: bool
    txn_ref: str
    message: str = ""


def _ref(prefix): return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ---- products ----
class PaymentProcessor(ABC):
    prefix = "PAY"

    @abstractmethod
    def charge(self, amount: float, details: dict) -> PaymentResult: ...


class UPIProcessor(PaymentProcessor):
    prefix = "UPI"
    def charge(self, amount, details):
        ok = "@" in details.get("upi_id", "")
        return PaymentResult(ok, _ref(self.prefix), "" if ok else "Invalid UPI id")


class CardProcessor(PaymentProcessor):
    prefix = "CARD"
    def charge(self, amount, details):
        num = str(details.get("card_number", "")).replace(" ", "")
        ok = num.isdigit() and len(num) == 16 and len(str(details.get("cvv", ""))) == 3
        return PaymentResult(ok, _ref(self.prefix), "" if ok else "Invalid card details")


class WalletProcessor(PaymentProcessor):
    prefix = "WAL"
    def charge(self, amount, details):
        ok = details.get("balance", 0) >= amount
        return PaymentResult(ok, _ref(self.prefix), "" if ok else "Insufficient wallet balance")


# ---- creators (factory method lives in subclasses) ----
class PaymentCreator(ABC):
    @abstractmethod
    def create_processor(self) -> PaymentProcessor: ...

    def process(self, amount: float, details: dict) -> PaymentResult:
        return self.create_processor().charge(amount, details)


class UPICreator(PaymentCreator):
    def create_processor(self): return UPIProcessor()

class CardCreator(PaymentCreator):
    def create_processor(self): return CardProcessor()

class WalletCreator(PaymentCreator):
    def create_processor(self): return WalletProcessor()


_CREATORS = {"UPI": UPICreator, "CARD": CardCreator, "WALLET": WalletCreator}


def get_creator(method: str) -> PaymentCreator:
    try:
        return _CREATORS[method.upper()]()
    except KeyError:
        raise ValidationError(f"Unsupported payment method: {method}")
