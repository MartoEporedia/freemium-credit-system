"""Pricing models for different product types."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from decimal import Decimal


class PricingType(str, Enum):
    """Types of pricing models."""
    FREE = "free"
    PAID = "paid"
    CREDIT = "credit"
    MIXED = "mixed"


class RecurrenceInterval(str, Enum):
    """Recurrence intervals for subscriptions."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ONE_TIME = "one_time"


@dataclass
class BasePricing:
    """Base class for all pricing models."""
    pricing_type: PricingType
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing to dictionary."""
        return {
            "pricing_type": self.pricing_type.value,
            "currency": self.currency,
            "metadata": self.metadata,
        }


class FreePricing(BasePricing):
    """Free pricing model with optional usage limits."""

    def __init__(
        self,
        daily_limit: Optional[int] = None,
        monthly_limit: Optional[int] = None,
        total_limit: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            pricing_type=PricingType.FREE,
            metadata=metadata or {},
        )
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit
        self.total_limit = total_limit

    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing to dictionary."""
        data = super().to_dict()
        data.update({
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "total_limit": self.total_limit,
        })
        return data


class PaidPricing(BasePricing):
    """Paid pricing model for subscription or one-time payments."""

    def __init__(
        self,
        amount: float,
        interval: RecurrenceInterval = RecurrenceInterval.MONTHLY,
        currency: str = "USD",
        trial_days: Optional[int] = None,
        usage_included: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            pricing_type=PricingType.PAID,
            currency=currency,
            metadata=metadata or {},
        )
        self.amount = Decimal(str(amount))
        self.interval = interval
        self.trial_days = trial_days
        self.usage_included = usage_included

    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing to dictionary."""
        data = super().to_dict()
        data.update({
            "amount": float(self.amount),
            "interval": self.interval.value,
            "trial_days": self.trial_days,
            "usage_included": self.usage_included,
        })
        return data


class CreditPricing(BasePricing):
    """Credit-based pricing model."""

    def __init__(
        self,
        cost_per_credit: float,
        currency: str = "USD",
        credit_packages: Optional[Dict[int, float]] = None,
        action_costs: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            pricing_type=PricingType.CREDIT,
            currency=currency,
            metadata=metadata or {},
        )
        self.cost_per_credit = Decimal(str(cost_per_credit))
        self.credit_packages = {
            credits: Decimal(str(price))
            for credits, price in (credit_packages or {}).items()
        }
        self.action_costs = action_costs or {}

    def get_action_cost(self, action: str, default: int = 1) -> int:
        """Get the credit cost for a specific action."""
        return self.action_costs.get(action, default)

    def get_package_price(self, credits: int) -> Optional[Decimal]:
        """Get the price for a credit package."""
        return self.credit_packages.get(credits)

    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing to dictionary."""
        data = super().to_dict()
        data.update({
            "cost_per_credit": float(self.cost_per_credit),
            "credit_packages": {
                credits: float(price)
                for credits, price in self.credit_packages.items()
            },
            "action_costs": self.action_costs,
        })
        return data


class MixedPricing(BasePricing):
    """Mixed pricing model combining subscription and credits."""

    def __init__(
        self,
        subscription_amount: float,
        included_credits: int,
        additional_credit_cost: float,
        subscription_interval: RecurrenceInterval = RecurrenceInterval.MONTHLY,
        currency: str = "USD",
        credit_packages: Optional[Dict[int, float]] = None,
        action_costs: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            pricing_type=PricingType.MIXED,
            currency=currency,
            metadata=metadata or {},
        )
        self.subscription_amount = Decimal(str(subscription_amount))
        self.subscription_interval = subscription_interval
        self.included_credits = included_credits
        self.additional_credit_cost = Decimal(str(additional_credit_cost))
        self.credit_packages = {
            credits: Decimal(str(price))
            for credits, price in (credit_packages or {}).items()
        }
        self.action_costs = action_costs or {}

    def get_action_cost(self, action: str, default: int = 1) -> int:
        """Get the credit cost for a specific action."""
        return self.action_costs.get(action, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing to dictionary."""
        data = super().to_dict()
        data.update({
            "subscription_amount": float(self.subscription_amount),
            "subscription_interval": self.subscription_interval.value,
            "included_credits": self.included_credits,
            "additional_credit_cost": float(self.additional_credit_cost),
            "credit_packages": {
                credits: float(price)
                for credits, price in self.credit_packages.items()
            },
            "action_costs": self.action_costs,
        })
        return data
