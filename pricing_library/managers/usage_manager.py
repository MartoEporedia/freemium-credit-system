"""Usage tracking and credit management."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from ..models.usage import UsageRecord, UsageLimit, UsagePeriod, UserCredits
from ..models.pricing import CreditPricing, MixedPricing, FreePricing
from ..models.product import ProductTier
from ..exceptions import (
    InsufficientCreditsError,
    UsageLimitExceededError,
)


class UsageManager:
    """Manages usage tracking, credits, and limits."""

    def __init__(self):
        self._usage_records: List[UsageRecord] = []
        self._user_credits: Dict[Tuple[str, str], UserCredits] = {}  # (user_id, product_id)
        self._usage_limits: Dict[Tuple[str, str, UsagePeriod], UsageLimit] = {}  # (user_id, product_id, period)

    def initialize_user_credits(
        self,
        user_id: str,
        product_id: str,
        initial_credits: int = 0,
        from_subscription: bool = False,
    ) -> UserCredits:
        """Initialize credits for a user."""
        key = (user_id, product_id)
        if key not in self._user_credits:
            self._user_credits[key] = UserCredits(
                user_id=user_id,
                product_id=product_id,
            )

        if initial_credits > 0:
            self._user_credits[key].add_credits(initial_credits, from_subscription)

        return self._user_credits[key]

    def get_user_credits(self, user_id: str, product_id: str) -> UserCredits:
        """Get credit balance for a user."""
        key = (user_id, product_id)
        if key not in self._user_credits:
            return self.initialize_user_credits(user_id, product_id)
        return self._user_credits[key]

    def add_credits(
        self,
        user_id: str,
        product_id: str,
        amount: int,
        from_subscription: bool = False,
    ) -> UserCredits:
        """Add credits to a user's balance."""
        credits = self.get_user_credits(user_id, product_id)
        credits.add_credits(amount, from_subscription)
        return credits

    def deduct_credits(
        self,
        user_id: str,
        product_id: str,
        amount: int,
    ) -> UserCredits:
        """Deduct credits from a user's balance."""
        credits = self.get_user_credits(user_id, product_id)
        if not credits.deduct(amount):
            raise InsufficientCreditsError(
                required=amount,
                available=credits.total_credits,
            )
        return credits

    def set_usage_limit(
        self,
        user_id: str,
        product_id: str,
        period: UsagePeriod,
        limit: int,
    ) -> UsageLimit:
        """Set a usage limit for a user."""
        key = (user_id, product_id, period)
        reset_at = self._calculate_reset_time(period)
        self._usage_limits[key] = UsageLimit(
            period=period,
            limit=limit,
            reset_at=reset_at,
        )
        return self._usage_limits[key]

    def get_usage_limit(
        self,
        user_id: str,
        product_id: str,
        period: UsagePeriod,
    ) -> Optional[UsageLimit]:
        """Get usage limit for a user."""
        key = (user_id, product_id, period)
        limit = self._usage_limits.get(key)

        # Check if limit needs to be reset
        if limit and limit.reset_at and datetime.utcnow() >= limit.reset_at:
            limit.reset()
            limit.reset_at = self._calculate_reset_time(period)

        return limit

    def check_usage_limits(
        self,
        user_id: str,
        product_id: str,
        tier: ProductTier,
    ) -> None:
        """Check if user has exceeded any usage limits."""
        if isinstance(tier.pricing, FreePricing):
            # Check daily limit
            if tier.pricing.daily_limit:
                limit = self.get_usage_limit(user_id, product_id, UsagePeriod.DAILY)
                if limit and limit.is_exceeded():
                    raise UsageLimitExceededError(
                        limit_type="daily",
                        limit=limit.limit,
                        current=limit.current_usage,
                    )

            # Check monthly limit
            if tier.pricing.monthly_limit:
                limit = self.get_usage_limit(user_id, product_id, UsagePeriod.MONTHLY)
                if limit and limit.is_exceeded():
                    raise UsageLimitExceededError(
                        limit_type="monthly",
                        limit=limit.limit,
                        current=limit.current_usage,
                    )

    def record_usage(
        self,
        user_id: str,
        product_id: str,
        tier_id: str,
        action: str,
        credits_used: int = 0,
        metadata: Optional[Dict] = None,
        success: bool = True,
    ) -> UsageRecord:
        """Record a usage event."""
        record = UsageRecord(
            user_id=user_id,
            product_id=product_id,
            tier_id=tier_id,
            action=action,
            credits_used=credits_used,
            metadata=metadata or {},
            success=success,
        )
        self._usage_records.append(record)
        return record

    def use_action(
        self,
        user_id: str,
        product_id: str,
        tier: ProductTier,
        action: str,
        metadata: Optional[Dict] = None,
    ) -> UsageRecord:
        """
        Process an action with automatic credit deduction and limit checking.

        Returns the usage record if successful.
        Raises InsufficientCreditsError or UsageLimitExceededError if checks fail.
        """
        # Check usage limits first
        self.check_usage_limits(user_id, product_id, tier)

        # Calculate credit cost
        credits_needed = 0
        if isinstance(tier.pricing, (CreditPricing, MixedPricing)):
            credits_needed = tier.pricing.get_action_cost(action)

        # Deduct credits if needed
        if credits_needed > 0:
            self.deduct_credits(user_id, product_id, credits_needed)

        # Update usage limits
        if isinstance(tier.pricing, FreePricing):
            for period in [UsagePeriod.DAILY, UsagePeriod.MONTHLY]:
                limit = self.get_usage_limit(user_id, product_id, period)
                if limit:
                    limit.increment()

        # Record the usage
        return self.record_usage(
            user_id=user_id,
            product_id=product_id,
            tier_id=tier.tier_id,
            action=action,
            credits_used=credits_needed,
            metadata=metadata,
            success=True,
        )

    def get_user_usage_history(
        self,
        user_id: str,
        product_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[UsageRecord]:
        """Get usage history for a user."""
        records = [
            r for r in self._usage_records
            if r.user_id == user_id and (product_id is None or r.product_id == product_id)
        ]
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]

    def get_usage_stats(
        self,
        user_id: str,
        product_id: str,
        period: UsagePeriod = UsagePeriod.MONTHLY,
    ) -> Dict:
        """Get usage statistics for a user."""
        start_time = self._get_period_start(period)
        records = [
            r for r in self._usage_records
            if r.user_id == user_id
            and r.product_id == product_id
            and r.timestamp >= start_time
            and r.success
        ]

        total_actions = len(records)
        total_credits = sum(r.credits_used for r in records)

        # Count actions by type
        action_counts = defaultdict(int)
        for record in records:
            action_counts[record.action] += 1

        return {
            "period": period.value,
            "total_actions": total_actions,
            "total_credits_used": total_credits,
            "action_breakdown": dict(action_counts),
            "period_start": start_time.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
        }

    def _calculate_reset_time(self, period: UsagePeriod) -> datetime:
        """Calculate when a usage limit should reset."""
        now = datetime.utcnow()

        if period == UsagePeriod.DAILY:
            return (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == UsagePeriod.WEEKLY:
            days_ahead = 7 - now.weekday()
            return (now + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == UsagePeriod.MONTHLY:
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1, day=1,
                                 hour=0, minute=0, second=0, microsecond=0)
            return now.replace(month=now.month + 1, day=1,
                             hour=0, minute=0, second=0, microsecond=0)
        elif period == UsagePeriod.YEARLY:
            return now.replace(year=now.year + 1, month=1, day=1,
                             hour=0, minute=0, second=0, microsecond=0)
        else:  # ALL_TIME
            return now + timedelta(days=365 * 100)  # Far future

    def _get_period_start(self, period: UsagePeriod) -> datetime:
        """Get the start time of the current period."""
        now = datetime.utcnow()

        if period == UsagePeriod.DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == UsagePeriod.WEEKLY:
            days_back = now.weekday()
            return (now - timedelta(days=days_back)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == UsagePeriod.MONTHLY:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == UsagePeriod.YEARLY:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # ALL_TIME
            return datetime.min
