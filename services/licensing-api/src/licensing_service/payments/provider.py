"""Extensible payment provider interface and manual payment implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class PaymentResult:
    success: bool
    reference: str
    amount: int
    currency: str
    payment_method: str
    recorded_at: str
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentProvider(ABC):
    """Abstract interface for payment processing and verification."""

    @abstractmethod
    def record_manual_payment(
        self,
        subscription_id: int,
        amount: int,
        currency: str,
        reference: str,
        payment_method: str = "MANUAL_BANK_TRANSFER",
        notes: Optional[str] = None,
    ) -> PaymentResult:
        """Record manual confirmation of payment from a client."""
        pass

    @abstractmethod
    def verify_payment(self, reference: str) -> bool:
        """Check payment status with provider."""
        pass


class ManualPaymentProvider(PaymentProvider):
    """Default manual payment provider for bank transfers, UPI, cheques, and cash."""

    def record_manual_payment(
        self,
        subscription_id: int,
        amount: int,
        currency: str,
        reference: str,
        payment_method: str = "MANUAL_BANK_TRANSFER",
        notes: Optional[str] = None,
    ) -> PaymentResult:
        now_str = datetime.now(timezone.utc).isoformat()
        return PaymentResult(
            success=True,
            reference=reference.strip() or f"MANUAL-{now_str}",
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            recorded_at=now_str,
            notes=notes,
            metadata={"recorded_by": "vendor_admin", "mode": "MANUAL"},
        )

    def verify_payment(self, reference: str) -> bool:
        # For manual payment, existence of a valid non-empty reference is verified
        return bool(reference and len(reference.strip()) > 0)


# Factory function to resolve active provider (Stripe/Razorpay extension point)
def get_payment_provider() -> PaymentProvider:
    return ManualPaymentProvider()
