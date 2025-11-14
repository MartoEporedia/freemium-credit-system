"""Tests for the pricing library."""

import pytest
from datetime import datetime
from decimal import Decimal

from pricing_library import (
    ProductManager,
    UsageManager,
    Product,
    ProductTier,
    FreePricing,
    PaidPricing,
    CreditPricing,
    MixedPricing,
    UsagePeriod,
    InsufficientCreditsError,
    UsageLimitExceededError,
    ProductNotFoundError,
)
from pricing_library.models.pricing import RecurrenceInterval


class TestPricingModels:
    """Test pricing model classes."""

    def test_free_pricing(self):
        """Test FreePricing model."""
        pricing = FreePricing(daily_limit=100, monthly_limit=1000)
        assert pricing.daily_limit == 100
        assert pricing.monthly_limit == 1000
        data = pricing.to_dict()
        assert data["pricing_type"] == "free"
        assert data["daily_limit"] == 100

    def test_paid_pricing(self):
        """Test PaidPricing model."""
        pricing = PaidPricing(
            amount=29.99,
            interval=RecurrenceInterval.MONTHLY,
            trial_days=7,
        )
        assert pricing.amount == Decimal("29.99")
        assert pricing.interval == RecurrenceInterval.MONTHLY
        assert pricing.trial_days == 7
        data = pricing.to_dict()
        assert data["amount"] == 29.99

    def test_credit_pricing(self):
        """Test CreditPricing model."""
        pricing = CreditPricing(
            cost_per_credit=0.01,
            credit_packages={100: 9.99, 500: 45.99},
            action_costs={"simple": 1, "complex": 5},
        )
        assert pricing.get_action_cost("simple") == 1
        assert pricing.get_action_cost("complex") == 5
        assert pricing.get_action_cost("unknown", default=2) == 2
        assert pricing.get_package_price(100) == Decimal("9.99")

    def test_mixed_pricing(self):
        """Test MixedPricing model."""
        pricing = MixedPricing(
            subscription_amount=99.99,
            included_credits=1000,
            additional_credit_cost=0.05,
            action_costs={"api_call": 2},
        )
        assert pricing.subscription_amount == Decimal("99.99")
        assert pricing.included_credits == 1000
        assert pricing.get_action_cost("api_call") == 2


class TestProductManager:
    """Test ProductManager class."""

    def test_create_product(self):
        """Test creating a product."""
        pm = ProductManager()
        product = pm.create_product(
            product_id="test_product",
            name="Test Product",
            description="A test product",
        )
        assert product.product_id == "test_product"
        assert product.name == "Test Product"
        assert product.is_active

    def test_add_tier(self):
        """Test adding a tier to a product."""
        pm = ProductManager()
        product = pm.create_product("test", "Test", "Test product")

        tier = ProductTier(
            tier_id="free",
            name="Free",
            pricing=FreePricing(daily_limit=100),
        )
        pm.add_tier_to_product("test", tier)

        retrieved_tier = pm.get_product_tier("test", "free")
        assert retrieved_tier.tier_id == "free"

    def test_get_nonexistent_product(self):
        """Test getting a product that doesn't exist."""
        pm = ProductManager()
        with pytest.raises(ProductNotFoundError):
            pm.get_product("nonexistent")

    def test_list_products(self):
        """Test listing products."""
        pm = ProductManager()
        pm.create_product("prod1", "Product 1", "First")
        pm.create_product("prod2", "Product 2", "Second")

        products = pm.list_products()
        assert len(products) == 2

    def test_deactivate_product(self):
        """Test deactivating a product."""
        pm = ProductManager()
        product = pm.create_product("test", "Test", "Test")
        assert product.is_active

        pm.deactivate_product("test")
        assert not product.is_active

        active_products = pm.list_products(active_only=True)
        assert len(active_products) == 0


class TestUsageManager:
    """Test UsageManager class."""

    def test_initialize_credits(self):
        """Test initializing user credits."""
        um = UsageManager()
        credits = um.initialize_user_credits(
            user_id="user1",
            product_id="prod1",
            initial_credits=100,
        )
        assert credits.total_credits == 100

    def test_add_credits(self):
        """Test adding credits."""
        um = UsageManager()
        um.initialize_user_credits("user1", "prod1")
        credits = um.add_credits("user1", "prod1", 50)
        assert credits.total_credits == 50

    def test_deduct_credits(self):
        """Test deducting credits."""
        um = UsageManager()
        um.initialize_user_credits("user1", "prod1", 100)
        credits = um.deduct_credits("user1", "prod1", 30)
        assert credits.total_credits == 70

    def test_insufficient_credits(self):
        """Test deducting more credits than available."""
        um = UsageManager()
        um.initialize_user_credits("user1", "prod1", 10)

        with pytest.raises(InsufficientCreditsError) as exc_info:
            um.deduct_credits("user1", "prod1", 50)

        assert exc_info.value.required == 50
        assert exc_info.value.available == 10

    def test_subscription_vs_purchased_credits(self):
        """Test distinction between subscription and purchased credits."""
        um = UsageManager()
        credits = um.initialize_user_credits("user1", "prod1")

        # Add subscription credits
        um.add_credits("user1", "prod1", 100, from_subscription=True)
        assert credits.subscription_credits == 100
        assert credits.purchased_credits == 0

        # Add purchased credits
        um.add_credits("user1", "prod1", 50, from_subscription=False)
        assert credits.subscription_credits == 100
        assert credits.purchased_credits == 50
        assert credits.total_credits == 150

        # Deduct credits (should take from subscription first)
        um.deduct_credits("user1", "prod1", 120)
        assert credits.subscription_credits == 0
        assert credits.purchased_credits == 30

    def test_usage_limits(self):
        """Test setting and checking usage limits."""
        um = UsageManager()
        limit = um.set_usage_limit("user1", "prod1", UsagePeriod.DAILY, 100)
        assert limit.limit == 100
        assert limit.current_usage == 0

        # Increment usage
        limit.increment(50)
        assert limit.current_usage == 50
        assert not limit.is_exceeded()

        limit.increment(60)
        assert limit.is_exceeded()

    def test_record_usage(self):
        """Test recording usage."""
        um = UsageManager()
        record = um.record_usage(
            user_id="user1",
            product_id="prod1",
            tier_id="free",
            action="api_call",
            credits_used=1,
        )
        assert record.user_id == "user1"
        assert record.action == "api_call"
        assert record.success

    def test_use_action_with_credits(self):
        """Test using an action with credit deduction."""
        um = UsageManager()
        pm = ProductManager()

        # Setup product with credit pricing
        product = pm.create_product("prod1", "Product", "Test")
        tier = ProductTier(
            tier_id="credit",
            name="Credit Tier",
            pricing=CreditPricing(
                cost_per_credit=0.01,
                action_costs={"api_call": 5},
            ),
        )
        product.add_tier(tier)

        # Initialize user with credits
        um.initialize_user_credits("user1", "prod1", 100)

        # Use action
        record = um.use_action("user1", "prod1", tier, "api_call")
        assert record.credits_used == 5

        credits = um.get_user_credits("user1", "prod1")
        assert credits.total_credits == 95

    def test_use_action_with_usage_limits(self):
        """Test using an action with usage limits."""
        um = UsageManager()
        pm = ProductManager()

        # Setup product with free pricing
        product = pm.create_product("prod1", "Product", "Test")
        tier = ProductTier(
            tier_id="free",
            name="Free Tier",
            pricing=FreePricing(daily_limit=10),
        )
        product.add_tier(tier)

        # Set usage limit
        um.set_usage_limit("user1", "prod1", UsagePeriod.DAILY, 10)

        # Use action 10 times
        for i in range(10):
            um.use_action("user1", "prod1", tier, "api_call")

        # 11th time should fail
        with pytest.raises(UsageLimitExceededError):
            um.use_action("user1", "prod1", tier, "api_call")

    def test_usage_stats(self):
        """Test getting usage statistics."""
        um = UsageManager()

        # Record some usage
        for i in range(5):
            um.record_usage(
                user_id="user1",
                product_id="prod1",
                tier_id="free",
                action="api_call",
                credits_used=1,
            )

        stats = um.get_usage_stats("user1", "prod1", UsagePeriod.DAILY)
        assert stats["total_actions"] == 5
        assert stats["total_credits_used"] == 5

    def test_usage_history(self):
        """Test getting usage history."""
        um = UsageManager()

        # Record some usage
        for i in range(3):
            um.record_usage(
                user_id="user1",
                product_id="prod1",
                tier_id="free",
                action=f"action_{i}",
            )

        history = um.get_user_usage_history("user1", "prod1", limit=10)
        assert len(history) == 3


class TestIntegration:
    """Integration tests for the full system."""

    def test_full_workflow(self):
        """Test a complete workflow from product creation to usage."""
        pm = ProductManager()
        um = UsageManager()

        # 1. Create product
        product = pm.create_product("api", "API Service", "My API")

        # 2. Add tiers
        free_tier = ProductTier(
            tier_id="free",
            name="Free",
            pricing=FreePricing(daily_limit=100),
        )
        product.add_tier(free_tier)

        credit_tier = ProductTier(
            tier_id="credit",
            name="Credit",
            pricing=CreditPricing(
                cost_per_credit=0.01,
                action_costs={"query": 2},
            ),
        )
        product.add_tier(credit_tier)

        # 3. Setup user with free tier
        um.set_usage_limit("user1", "api", UsagePeriod.DAILY, 100)

        # 4. Use free tier
        for i in range(50):
            um.use_action("user1", "api", free_tier, "query")

        stats = um.get_usage_stats("user1", "api", UsagePeriod.DAILY)
        assert stats["total_actions"] == 50

        # 5. Setup another user with credit tier
        um.initialize_user_credits("user2", "api", 1000)

        # 6. Use credit tier
        record = um.use_action("user2", "api", credit_tier, "query")
        assert record.credits_used == 2

        credits = um.get_user_credits("user2", "api")
        assert credits.total_credits == 998


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
