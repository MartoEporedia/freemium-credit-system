"""SQLAlchemy models for database persistence."""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship

from .base import Base


class SubscriptionPlan(Base):
    """
    Represents a product tier/plan with pricing configuration.

    This table stores product tiers with their pricing configurations.
    The pricing_config is stored as JSONB for flexibility.
    """

    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String(50), unique=True, nullable=False, index=True)
    product_id = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    tier_id = Column(String(50), nullable=False)

    # Pricing configuration stored as JSON
    pricing_type = Column(String(20), nullable=False)  # 'free', 'paid', 'credit', 'mixed'
    pricing_config = Column(JSONB, nullable=False)  # Full pricing configuration as JSON

    # Features and metadata
    features = Column(JSONB)
    meta_data = Column("metadata", JSONB)  # Use meta_data attribute, store as "metadata" column

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_subscription_plans_product_tier", "product_id", "tier_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "product_id": self.product_id,
            "name": self.name,
            "tier_id": self.tier_id,
            "pricing_type": self.pricing_type,
            "pricing_config": self.pricing_config,
            "features": self.features,
            "metadata": self.meta_data,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CreditWallet(Base):
    """
    Represents a credit wallet for an entity (user, family, team, etc.).

    This table supports multi-tenancy through entity_type and entity_id.
    Credits are separated into subscription credits and purchased credits.
    """

    __tablename__ = "credit_wallets"

    id = Column(Integer, primary_key=True)

    # Multi-tenancy support
    entity_type = Column(String(50), nullable=False, index=True)  # 'user', 'family', 'team', etc.
    entity_id = Column(String(100), nullable=False, index=True)  # UUID or ID as string

    # Product association
    product_id = Column(String(50), nullable=False, index=True)

    # Credit balances
    subscription_credits = Column(Integer, default=0, nullable=False)
    purchased_credits = Column(Integer, default=0, nullable=False)

    # Subscription plan reference (optional)
    subscription_plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    subscription_plan = relationship("SubscriptionPlan")

    # Feature flags
    is_credits_enabled = Column(Boolean, default=True, nullable=False)

    # Reset tracking
    credits_reset_at = Column(DateTime, nullable=True)
    next_reset_at = Column(DateTime, nullable=True)

    # Metadata
    meta_data = Column("metadata", JSONB)  # Use meta_data attribute, store as "metadata" column

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Constraints and indexes
    __table_args__ = (
        Index("ix_credit_wallets_entity", "entity_type", "entity_id"),
        Index("ix_credit_wallets_entity_product", "entity_type", "entity_id", "product_id", unique=True),
        CheckConstraint("subscription_credits >= 0", name="ck_subscription_credits_positive"),
        CheckConstraint("purchased_credits >= 0", name="ck_purchased_credits_positive"),
    )

    @property
    def total_credits(self) -> int:
        """Get total available credits."""
        return self.subscription_credits + self.purchased_credits

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "product_id": self.product_id,
            "subscription_credits": self.subscription_credits,
            "purchased_credits": self.purchased_credits,
            "total_credits": self.total_credits,
            "is_credits_enabled": self.is_credits_enabled,
            "credits_reset_at": self.credits_reset_at.isoformat() if self.credits_reset_at else None,
            "next_reset_at": self.next_reset_at.isoformat() if self.next_reset_at else None,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CreditTransaction(Base):
    """
    Audit log for all credit operations.

    This table provides a complete audit trail of all credit changes.
    """

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)

    # Multi-tenancy support
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(100), nullable=False, index=True)

    # Product association
    product_id = Column(String(50), nullable=False, index=True)

    # Transaction details
    amount = Column(Integer, nullable=False)  # Positive for additions, negative for deductions
    transaction_type = Column(String(50), nullable=False)  # 'deduction', 'purchase', 'reset', 'refund'
    operation_type = Column(String(100), nullable=True)  # 'ai_chat', 'api_call', etc.

    # Balance tracking
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)

    # Additional context
    description = Column(Text, nullable=True)
    meta_data = Column("metadata", JSONB)  # Use meta_data attribute, store as "metadata" column

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("ix_credit_transactions_entity", "entity_type", "entity_id"),
        Index("ix_credit_transactions_entity_product", "entity_type", "entity_id", "product_id"),
        Index("ix_credit_transactions_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "product_id": self.product_id,
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "operation_type": self.operation_type,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "description": self.description,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UsageRecord(Base):
    """
    Tracks API usage and actions.

    This table records every API call or action performed by entities.
    """

    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True)

    # Multi-tenancy support
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(100), nullable=False, index=True)

    # Product and tier
    product_id = Column(String(50), nullable=False, index=True)
    tier_id = Column(String(50), nullable=False)

    # Action details
    action = Column(String(100), nullable=False, index=True)
    credits_used = Column(Integer, default=0, nullable=False)

    # Status
    success = Column(Boolean, default=True, nullable=False)

    # Metadata
    meta_data = Column("metadata", JSONB)  # Use meta_data attribute, store as "metadata" column

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("ix_usage_records_entity", "entity_type", "entity_id"),
        Index("ix_usage_records_entity_product", "entity_type", "entity_id", "product_id"),
        Index("ix_usage_records_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "product_id": self.product_id,
            "tier_id": self.tier_id,
            "action": self.action,
            "credits_used": self.credits_used,
            "success": self.success,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UsageLimit(Base):
    """
    Stores usage limits per entity and period.

    This table tracks usage limits and current usage for rate limiting.
    """

    __tablename__ = "usage_limits"

    id = Column(Integer, primary_key=True)

    # Multi-tenancy support
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(100), nullable=False, index=True)

    # Product association
    product_id = Column(String(50), nullable=False, index=True)

    # Limit details
    period = Column(String(20), nullable=False)  # 'daily', 'weekly', 'monthly', 'yearly'
    limit_value = Column(Integer, nullable=False)
    current_usage = Column(Integer, default=0, nullable=False)

    # Reset tracking
    reset_at = Column(DateTime, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Constraints and indexes
    __table_args__ = (
        Index("ix_usage_limits_entity", "entity_type", "entity_id"),
        Index("ix_usage_limits_entity_product_period", "entity_type", "entity_id", "product_id", "period", unique=True),
        CheckConstraint("limit_value >= 0", name="ck_limit_value_positive"),
        CheckConstraint("current_usage >= 0", name="ck_current_usage_positive"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "product_id": self.product_id,
            "period": self.period,
            "limit_value": self.limit_value,
            "current_usage": self.current_usage,
            "remaining": max(0, self.limit_value - self.current_usage),
            "is_exceeded": self.current_usage >= self.limit_value,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
