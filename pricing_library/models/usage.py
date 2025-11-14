"""Usage tracking models."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class UsagePeriod(str, Enum):
    """Time period for usage tracking."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


@dataclass
class UsageLimit:
    """Represents usage limits for a user or product tier."""
    period: UsagePeriod
    limit: int
    current_usage: int = 0
    reset_at: Optional[datetime] = None

    def is_exceeded(self) -> bool:
        """Check if the usage limit has been exceeded."""
        return self.current_usage >= self.limit

    def remaining(self) -> int:
        """Get remaining usage before hitting the limit."""
        return max(0, self.limit - self.current_usage)

    def increment(self, amount: int = 1) -> None:
        """Increment current usage."""
        self.current_usage += amount

    def reset(self) -> None:
        """Reset the usage counter."""
        self.current_usage = 0
        self.reset_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert usage limit to dictionary."""
        return {
            "period": self.period.value,
            "limit": self.limit,
            "current_usage": self.current_usage,
            "remaining": self.remaining(),
            "is_exceeded": self.is_exceeded(),
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
        }


@dataclass
class UsageRecord:
    """Represents a single usage event."""
    user_id: str
    product_id: str
    tier_id: str
    action: str
    credits_used: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert usage record to dictionary."""
        return {
            "user_id": self.user_id,
            "product_id": self.product_id,
            "tier_id": self.tier_id,
            "action": self.action,
            "credits_used": self.credits_used,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "success": self.success,
        }


@dataclass
class UserCredits:
    """Represents a user's credit balance."""
    user_id: str
    product_id: str
    credits: int = 0
    subscription_credits: int = 0  # Credits from subscription
    purchased_credits: int = 0  # Credits purchased separately
    last_reset: Optional[datetime] = None
    next_reset: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_credits(self) -> int:
        """Get total available credits."""
        return self.subscription_credits + self.purchased_credits

    def deduct(self, amount: int) -> bool:
        """
        Deduct credits from the user's balance.
        Returns True if successful, False if insufficient credits.
        """
        if self.total_credits < amount:
            return False

        remaining = amount
        # First deduct from subscription credits
        if self.subscription_credits >= remaining:
            self.subscription_credits -= remaining
            return True

        remaining -= self.subscription_credits
        self.subscription_credits = 0

        # Then deduct from purchased credits
        self.purchased_credits -= remaining
        return True

    def add_credits(self, amount: int, from_subscription: bool = False) -> None:
        """Add credits to the user's balance."""
        if from_subscription:
            self.subscription_credits += amount
        else:
            self.purchased_credits += amount

    def reset_subscription_credits(self, new_amount: int) -> None:
        """Reset subscription credits (e.g., at billing cycle)."""
        self.subscription_credits = new_amount
        self.last_reset = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert user credits to dictionary."""
        return {
            "user_id": self.user_id,
            "product_id": self.product_id,
            "total_credits": self.total_credits,
            "subscription_credits": self.subscription_credits,
            "purchased_credits": self.purchased_credits,
            "last_reset": self.last_reset.isoformat() if self.last_reset else None,
            "next_reset": self.next_reset.isoformat() if self.next_reset else None,
            "metadata": self.metadata,
        }
