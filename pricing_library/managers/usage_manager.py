"""Usage tracking and credit management with multi-tenancy support."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session

from ..models.usage import UsageRecord, UsageLimit, UsagePeriod, UserCredits
from ..models.pricing import CreditPricing, MixedPricing, FreePricing
from ..models.product import ProductTier
from ..exceptions import (
    InsufficientCreditsError,
    UsageLimitExceededError,
)
from ..config import PricingConfig


class UsageManager:
    """
    Manages usage tracking, credits, and limits with multi-tenancy support.

    Supports both in-memory mode (default) and database mode.
    Supports flexible entity types (user, family, team, organization, etc.).

    In-memory mode:
        um = UsageManager()
        um.initialize_user_credits(user_id="user123", product_id="app", initial_credits=100)

    Database mode:
        config = PricingConfig.for_database("postgresql://...", entity_type="family")
        session = get_session(config)
        um = UsageManager(db_session=session, config=config)
        um.initialize_user_credits(user_id="family_123", product_id="app", initial_credits=100)
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        config: Optional[PricingConfig] = None,
    ):
        """
        Initialize UsageManager.

        Args:
            db_session: Optional SQLAlchemy session for database mode
            config: Optional configuration (required if db_session is provided)
        """
        self._usage_records: List[UsageRecord] = []
        self._user_credits: Dict[Tuple[str, str], UserCredits] = {}  # (user_id, product_id)
        self._usage_limits: Dict[Tuple[str, str, UsagePeriod], UsageLimit] = {}  # (user_id, product_id, period)

        self._db_session = db_session
        self._config = config or PricingConfig()

        # Validate configuration
        if db_session is not None and not config:
            raise ValueError("config must be provided when using db_session")

        if db_session is not None and not config.use_database:
            raise ValueError("config.use_database must be True when using db_session")

    @property
    def use_database(self) -> bool:
        """Check if database mode is enabled."""
        return self._db_session is not None and self._config.use_database

    @property
    def entity_type(self) -> str:
        """Get the configured entity type."""
        return self._config.entity_type

    def initialize_user_credits(
        self,
        user_id: str,
        product_id: str,
        initial_credits: int = 0,
        from_subscription: bool = False,
    ) -> UserCredits:
        """
        Initialize credits for an entity (user, family, team, etc.).

        Note: Despite the method name "user_credits" for backward compatibility,
        this actually works with any entity type configured in the config.

        Args:
            user_id: Entity ID (can be user_id, family_id, team_id, etc.)
            product_id: Product ID
            initial_credits: Initial credit amount
            from_subscription: Whether credits are from subscription

        Returns:
            UserCredits object
        """
        if self.use_database:
            return self._initialize_credits_db(user_id, product_id, initial_credits, from_subscription)

        # In-memory mode
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
        """
        Get credit balance for an entity.

        Args:
            user_id: Entity ID
            product_id: Product ID

        Returns:
            UserCredits object
        """
        if self.use_database:
            return self._get_credits_db(user_id, product_id)

        # In-memory mode
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
        description: Optional[str] = None,
    ) -> UserCredits:
        """
        Add credits to an entity's balance.

        Args:
            user_id: Entity ID
            product_id: Product ID
            amount: Credit amount to add
            from_subscription: Whether credits are from subscription
            description: Optional description for transaction log

        Returns:
            Updated UserCredits object
        """
        if self.use_database:
            return self._add_credits_db(user_id, product_id, amount, from_subscription, description)

        # In-memory mode
        credits = self.get_user_credits(user_id, product_id)
        credits.add_credits(amount, from_subscription)
        return credits

    def deduct_credits(
        self,
        user_id: str,
        product_id: str,
        amount: int,
        operation_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> UserCredits:
        """
        Deduct credits from an entity's balance.

        Args:
            user_id: Entity ID
            product_id: Product ID
            amount: Credit amount to deduct
            operation_type: Type of operation (e.g., "ai_chat", "api_call")
            description: Optional description for transaction log

        Returns:
            Updated UserCredits object

        Raises:
            InsufficientCreditsError: If entity doesn't have enough credits
        """
        if self.use_database:
            return self._deduct_credits_db(user_id, product_id, amount, operation_type, description)

        # In-memory mode
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
        """
        Set a usage limit for an entity.

        Args:
            user_id: Entity ID
            product_id: Product ID
            period: Usage period (daily, weekly, monthly, etc.)
            limit: Usage limit value

        Returns:
            UsageLimit object
        """
        if self.use_database:
            return self._set_usage_limit_db(user_id, product_id, period, limit)

        # In-memory mode
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
        """
        Get usage limit for an entity.

        Args:
            user_id: Entity ID
            product_id: Product ID
            period: Usage period

        Returns:
            UsageLimit object or None
        """
        if self.use_database:
            return self._get_usage_limit_db(user_id, product_id, period)

        # In-memory mode
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
        """
        Check if entity has exceeded any usage limits.

        Args:
            user_id: Entity ID
            product_id: Product ID
            tier: Product tier

        Raises:
            UsageLimitExceededError: If usage limit is exceeded
        """
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
        """
        Record a usage event.

        Args:
            user_id: Entity ID
            product_id: Product ID
            tier_id: Tier ID
            action: Action name
            credits_used: Credits used
            metadata: Optional metadata
            success: Whether the action was successful

        Returns:
            UsageRecord object
        """
        if self.use_database:
            return self._record_usage_db(user_id, product_id, tier_id, action, credits_used, metadata, success)

        # In-memory mode
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

        Args:
            user_id: Entity ID
            product_id: Product ID
            tier: Product tier
            action: Action name
            metadata: Optional metadata

        Returns:
            UsageRecord object

        Raises:
            InsufficientCreditsError: If entity doesn't have enough credits
            UsageLimitExceededError: If usage limit is exceeded
        """
        # Check usage limits first
        self.check_usage_limits(user_id, product_id, tier)

        # Calculate credit cost
        credits_needed = 0
        if isinstance(tier.pricing, (CreditPricing, MixedPricing)):
            credits_needed = tier.pricing.get_action_cost(action)

        # Deduct credits if needed
        if credits_needed > 0:
            self.deduct_credits(user_id, product_id, credits_needed, operation_type=action)

        # Update usage limits
        if isinstance(tier.pricing, FreePricing):
            for period in [UsagePeriod.DAILY, UsagePeriod.MONTHLY]:
                limit = self.get_usage_limit(user_id, product_id, period)
                if limit:
                    limit.increment()
                    # Persist to database if needed
                    if self.use_database:
                        self._update_usage_limit_db(limit, user_id, product_id, period)

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
        """
        Get usage history for an entity.

        Args:
            user_id: Entity ID
            product_id: Optional product ID filter
            limit: Maximum number of records to return

        Returns:
            List of UsageRecord objects
        """
        if self.use_database:
            return self._get_usage_history_db(user_id, product_id, limit)

        # In-memory mode
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
        """
        Get usage statistics for an entity.

        Args:
            user_id: Entity ID
            product_id: Product ID
            period: Usage period

        Returns:
            Dictionary with usage statistics
        """
        if self.use_database:
            return self._get_usage_stats_db(user_id, product_id, period)

        # In-memory mode
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

    # Database persistence methods

    def _initialize_credits_db(
        self,
        user_id: str,
        product_id: str,
        initial_credits: int,
        from_subscription: bool,
    ) -> UserCredits:
        """Initialize credits in database mode."""
        from ..database.models import CreditWallet, CreditTransaction

        # Check if wallet exists
        wallet = (
            self._db_session.query(CreditWallet)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
            )
            .first()
        )

        if not wallet:
            # Create new wallet
            wallet = CreditWallet(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
                subscription_credits=initial_credits if from_subscription else 0,
                purchased_credits=0 if from_subscription else initial_credits,
            )
            self._db_session.add(wallet)
        elif initial_credits > 0:
            # Add credits to existing wallet
            if from_subscription:
                wallet.subscription_credits += initial_credits
            else:
                wallet.purchased_credits += initial_credits

            # Log transaction
            transaction = CreditTransaction(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
                amount=initial_credits,
                transaction_type="initialization" if not wallet else "purchase",
                balance_before=0 if not wallet else wallet.total_credits - initial_credits,
                balance_after=wallet.total_credits,
                description="Initial credits" if not wallet else "Credits added",
            )
            self._db_session.add(transaction)

        self._db_session.commit()

        # Convert to UserCredits object
        return self._wallet_to_user_credits(wallet)

    def _get_credits_db(self, user_id: str, product_id: str) -> UserCredits:
        """Get credits from database."""
        from ..database.models import CreditWallet

        wallet = (
            self._db_session.query(CreditWallet)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
            )
            .first()
        )

        if not wallet:
            # Initialize with zero credits
            return self._initialize_credits_db(user_id, product_id, 0, False)

        return self._wallet_to_user_credits(wallet)

    def _add_credits_db(
        self,
        user_id: str,
        product_id: str,
        amount: int,
        from_subscription: bool,
        description: Optional[str],
    ) -> UserCredits:
        """Add credits in database mode."""
        from ..database.models import CreditWallet, CreditTransaction

        wallet = (
            self._db_session.query(CreditWallet)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
            )
            .first()
        )

        if not wallet:
            return self._initialize_credits_db(user_id, product_id, amount, from_subscription)

        balance_before = wallet.total_credits

        if from_subscription:
            wallet.subscription_credits += amount
        else:
            wallet.purchased_credits += amount

        wallet.updated_at = datetime.utcnow()

        # Log transaction
        transaction = CreditTransaction(
            entity_type=self.entity_type,
            entity_id=user_id,
            product_id=product_id,
            amount=amount,
            transaction_type="purchase" if not from_subscription else "subscription",
            balance_before=balance_before,
            balance_after=wallet.total_credits,
            description=description or ("Subscription credits" if from_subscription else "Purchased credits"),
        )
        self._db_session.add(transaction)
        self._db_session.commit()

        return self._wallet_to_user_credits(wallet)

    def _deduct_credits_db(
        self,
        user_id: str,
        product_id: str,
        amount: int,
        operation_type: Optional[str],
        description: Optional[str],
    ) -> UserCredits:
        """Deduct credits in database mode."""
        from ..database.models import CreditWallet, CreditTransaction

        wallet = (
            self._db_session.query(CreditWallet)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
            )
            .first()
        )

        if not wallet or wallet.total_credits < amount:
            raise InsufficientCreditsError(
                required=amount,
                available=wallet.total_credits if wallet else 0,
            )

        balance_before = wallet.total_credits

        # Deduct from subscription credits first, then purchased
        remaining = amount
        if wallet.subscription_credits >= remaining:
            wallet.subscription_credits -= remaining
        else:
            remaining -= wallet.subscription_credits
            wallet.subscription_credits = 0
            wallet.purchased_credits -= remaining

        wallet.updated_at = datetime.utcnow()

        # Log transaction
        transaction = CreditTransaction(
            entity_type=self.entity_type,
            entity_id=user_id,
            product_id=product_id,
            amount=-amount,
            transaction_type="deduction",
            operation_type=operation_type,
            balance_before=balance_before,
            balance_after=wallet.total_credits,
            description=description or f"Credits deducted for {operation_type or 'operation'}",
        )
        self._db_session.add(transaction)
        self._db_session.commit()

        return self._wallet_to_user_credits(wallet)

    def _set_usage_limit_db(
        self,
        user_id: str,
        product_id: str,
        period: UsagePeriod,
        limit: int,
    ) -> UsageLimit:
        """Set usage limit in database mode."""
        from ..database.models import UsageLimit as DBUsageLimit

        reset_at = self._calculate_reset_time(period)

        # Check if limit exists
        db_limit = (
            self._db_session.query(DBUsageLimit)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
                period=period.value,
            )
            .first()
        )

        if db_limit:
            db_limit.limit_value = limit
            db_limit.reset_at = reset_at
            db_limit.updated_at = datetime.utcnow()
        else:
            db_limit = DBUsageLimit(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
                period=period.value,
                limit_value=limit,
                current_usage=0,
                reset_at=reset_at,
            )
            self._db_session.add(db_limit)

        self._db_session.commit()

        return UsageLimit(
            period=period,
            limit=db_limit.limit_value,
            current_usage=db_limit.current_usage,
            reset_at=db_limit.reset_at,
        )

    def _get_usage_limit_db(
        self,
        user_id: str,
        product_id: str,
        period: UsagePeriod,
    ) -> Optional[UsageLimit]:
        """Get usage limit from database."""
        from ..database.models import UsageLimit as DBUsageLimit

        db_limit = (
            self._db_session.query(DBUsageLimit)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
                period=period.value,
            )
            .first()
        )

        if not db_limit:
            return None

        # Check if needs reset
        if db_limit.reset_at and datetime.utcnow() >= db_limit.reset_at:
            db_limit.current_usage = 0
            db_limit.reset_at = self._calculate_reset_time(period)
            db_limit.updated_at = datetime.utcnow()
            self._db_session.commit()

        return UsageLimit(
            period=period,
            limit=db_limit.limit_value,
            current_usage=db_limit.current_usage,
            reset_at=db_limit.reset_at,
        )

    def _update_usage_limit_db(
        self,
        limit: UsageLimit,
        user_id: str,
        product_id: str,
        period: UsagePeriod,
    ) -> None:
        """Update usage limit in database."""
        from ..database.models import UsageLimit as DBUsageLimit

        db_limit = (
            self._db_session.query(DBUsageLimit)
            .filter_by(
                entity_type=self.entity_type,
                entity_id=user_id,
                product_id=product_id,
                period=period.value,
            )
            .first()
        )

        if db_limit:
            db_limit.current_usage = limit.current_usage
            db_limit.updated_at = datetime.utcnow()
            self._db_session.commit()

    def _record_usage_db(
        self,
        user_id: str,
        product_id: str,
        tier_id: str,
        action: str,
        credits_used: int,
        metadata: Optional[Dict],
        success: bool,
    ) -> UsageRecord:
        """Record usage in database."""
        from ..database.models import UsageRecord as DBUsageRecord

        db_record = DBUsageRecord(
            entity_type=self.entity_type,
            entity_id=user_id,
            product_id=product_id,
            tier_id=tier_id,
            action=action,
            credits_used=credits_used,
            metadata=metadata or {},
            success=success,
        )
        self._db_session.add(db_record)
        self._db_session.commit()

        # Convert to UsageRecord object
        return UsageRecord(
            user_id=user_id,
            product_id=product_id,
            tier_id=tier_id,
            action=action,
            credits_used=credits_used,
            timestamp=db_record.created_at,
            metadata=metadata or {},
            success=success,
        )

    def _get_usage_history_db(
        self,
        user_id: str,
        product_id: Optional[str],
        limit: int,
    ) -> List[UsageRecord]:
        """Get usage history from database."""
        from ..database.models import UsageRecord as DBUsageRecord

        query = self._db_session.query(DBUsageRecord).filter_by(
            entity_type=self.entity_type,
            entity_id=user_id,
        )

        if product_id:
            query = query.filter_by(product_id=product_id)

        db_records = query.order_by(DBUsageRecord.created_at.desc()).limit(limit).all()

        # Convert to UsageRecord objects
        return [
            UsageRecord(
                user_id=r.entity_id,
                product_id=r.product_id,
                tier_id=r.tier_id,
                action=r.action,
                credits_used=r.credits_used,
                timestamp=r.created_at,
                metadata=r.metadata or {},
                success=r.success,
            )
            for r in db_records
        ]

    def _get_usage_stats_db(
        self,
        user_id: str,
        product_id: str,
        period: UsagePeriod,
    ) -> Dict:
        """Get usage statistics from database."""
        from ..database.models import UsageRecord as DBUsageRecord
        from sqlalchemy import func

        start_time = self._get_period_start(period)

        # Query records in period
        query = self._db_session.query(DBUsageRecord).filter(
            DBUsageRecord.entity_type == self.entity_type,
            DBUsageRecord.entity_id == user_id,
            DBUsageRecord.product_id == product_id,
            DBUsageRecord.created_at >= start_time,
            DBUsageRecord.success == True,
        )

        records = query.all()

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

    def _wallet_to_user_credits(self, wallet) -> UserCredits:
        """Convert database wallet to UserCredits object."""
        return UserCredits(
            user_id=wallet.entity_id,
            product_id=wallet.product_id,
            subscription_credits=wallet.subscription_credits,
            purchased_credits=wallet.purchased_credits,
            last_reset=wallet.credits_reset_at,
            next_reset=wallet.next_reset_at,
            metadata=wallet.metadata or {},
        )
