# Usage Guide

## Table of Contents
1. [Installation](#installation)
2. [Basic Concepts](#basic-concepts)
3. [Pricing Models](#pricing-models)
4. [Product Setup](#product-setup)
5. [User Management](#user-management)
6. [FastAPI Integration](#fastapi-integration)
7. [Common Patterns](#common-patterns)

## Installation

### From Source
```bash
git clone https://github.com/yourusername/pricing-library.git
cd pricing-library
pip install -e .
```

### Development Installation
```bash
pip install -e ".[dev]"
```

## Basic Concepts

### Products and Tiers
- A **Product** represents a service or offering
- A **Tier** represents a pricing level within a product (e.g., Free, Pro, Enterprise)
- Each tier has a **Pricing** model that defines how it's charged

### Credits and Usage
- **Credits** are virtual currency units
- **Usage Limits** restrict how many times an action can be performed
- **Usage Records** track all actions for analytics and billing

## Pricing Models

### 1. Free Pricing
Best for: Free tiers with usage limits

```python
from pricing_library import FreePricing

pricing = FreePricing(
    daily_limit=100,      # Max 100 actions per day
    monthly_limit=1000,   # Max 1000 actions per month
    total_limit=10000,    # Max 10000 actions total
)
```

### 2. Paid Pricing
Best for: Traditional subscriptions

```python
from pricing_library import PaidPricing
from pricing_library.models.pricing import RecurrenceInterval

# Monthly subscription
pricing = PaidPricing(
    amount=29.99,
    interval=RecurrenceInterval.MONTHLY,
    trial_days=14,         # 14-day free trial
    usage_included=5000,   # 5000 actions included
)

# Yearly subscription
pricing = PaidPricing(
    amount=299.99,
    interval=RecurrenceInterval.YEARLY,
)

# One-time payment
pricing = PaidPricing(
    amount=99.99,
    interval=RecurrenceInterval.ONE_TIME,
)
```

### 3. Credit Pricing
Best for: Pay-as-you-go models

```python
from pricing_library import CreditPricing

pricing = CreditPricing(
    cost_per_credit=0.01,  # $0.01 per credit
    credit_packages={
        100: 9.99,         # 100 credits for $9.99
        500: 45.99,        # 500 credits for $45.99 (8% discount)
        1000: 89.99,       # 1000 credits for $89.99 (10% discount)
    },
    action_costs={
        "simple_query": 1,
        "complex_query": 5,
        "data_export": 10,
        "ai_analysis": 20,
    },
)
```

### 4. Mixed Pricing
Best for: Subscription with included credits

```python
from pricing_library import MixedPricing

pricing = MixedPricing(
    subscription_amount=99.99,
    subscription_interval=RecurrenceInterval.MONTHLY,
    included_credits=10000,      # 10k credits included
    additional_credit_cost=0.005, # $0.005 per additional credit
    action_costs={
        "api_call": 1,
        "advanced_feature": 5,
    },
)
```

## Product Setup

### Complete Example

```python
from pricing_library import (
    ProductManager,
    Product,
    ProductTier,
    FreePricing,
    PaidPricing,
    CreditPricing,
)

# Initialize manager
pm = ProductManager()

# Create product
product = pm.create_product(
    product_id="my_api",
    name="My API Service",
    description="Powerful API for data processing",
)

# Add Free Tier
free_tier = ProductTier(
    tier_id="free",
    name="Free",
    pricing=FreePricing(daily_limit=100),
    features=[
        "100 API calls per day",
        "Basic features",
        "Community support",
    ],
    max_users=None,  # Unlimited users
)
product.add_tier(free_tier)

# Add Pro Tier
pro_tier = ProductTier(
    tier_id="pro",
    name="Professional",
    pricing=PaidPricing(amount=49.99),
    features=[
        "Unlimited API calls",
        "All features",
        "Priority support",
        "99.9% SLA",
    ],
    priority_support=True,
)
product.add_tier(pro_tier)

# Add Pay-as-you-go Tier
payg_tier = ProductTier(
    tier_id="payg",
    name="Pay As You Go",
    pricing=CreditPricing(
        cost_per_credit=0.01,
        credit_packages={100: 9.99, 500: 45.99},
        action_costs={"api_call": 1},
    ),
    features=["No monthly fee", "Pay only for what you use"],
)
product.add_tier(payg_tier)
```

## User Management

### Setting Up Users

```python
from pricing_library import UsageManager, UsagePeriod

um = UsageManager()

# User on Free Tier
um.set_usage_limit("user123", "my_api", UsagePeriod.DAILY, 100)

# User on Pro Tier (no limits needed)
# Nothing to set up for unlimited paid tier

# User on Pay-as-you-go
um.initialize_user_credits("user456", "my_api", initial_credits=100)

# User on Mixed Pricing
um.initialize_user_credits(
    "user789",
    "my_api",
    initial_credits=10000,
    from_subscription=True,  # These are subscription credits
)
```

### Managing Credits

```python
# Check balance
credits = um.get_user_credits("user456", "my_api")
print(f"Total: {credits.total_credits}")
print(f"Subscription: {credits.subscription_credits}")
print(f"Purchased: {credits.purchased_credits}")

# Add credits (purchase)
um.add_credits("user456", "my_api", 500, from_subscription=False)

# Deduct credits
try:
    um.deduct_credits("user456", "my_api", 10)
except InsufficientCreditsError as e:
    print(f"Need {e.required}, have {e.available}")

# Reset subscription credits (at billing cycle)
credits = um.get_user_credits("user789", "my_api")
credits.reset_subscription_credits(10000)
```

### Processing Actions

```python
# Get the tier
tier = pm.get_product_tier("my_api", "payg")

# Use an action (automatic credit deduction and limit checking)
try:
    record = um.use_action(
        user_id="user456",
        product_id="my_api",
        tier=tier,
        action="api_call",
        metadata={"endpoint": "/api/data", "method": "GET"},
    )
    print(f"Action completed, used {record.credits_used} credits")
except InsufficientCreditsError:
    print("Not enough credits!")
except UsageLimitExceededError:
    print("Usage limit exceeded!")
```

## FastAPI Integration

### Setup

```python
from fastapi import FastAPI
from pricing_library.fastapi import initialize_managers, PricingMiddleware

app = FastAPI()

# Initialize
pm = ProductManager()
um = UsageManager()
initialize_managers(pm, um)

# Add middleware (optional)
app.add_middleware(
    PricingMiddleware,
    product_manager=pm,
    usage_manager=um,
    add_usage_headers=True,
)
```

### Using Dependencies

```python
from fastapi import Depends
from pricing_library.fastapi import require_credits, get_usage_manager

# Automatic credit checking
@app.post("/api/query")
async def query(
    data: str,
    _=Depends(require_credits("my_api", "api_call"))
):
    # Your logic here
    return {"result": "success"}

# Manual management
@app.post("/api/complex")
async def complex_action(
    data: str,
    um: UsageManager = Depends(get_usage_manager)
):
    # Check remaining credits first
    credits = um.get_user_credits(user_id, product_id)
    if credits.total_credits < 10:
        raise HTTPException(402, "Not enough credits")

    # Your logic here
    # ...

    # Deduct credits after success
    um.deduct_credits(user_id, product_id, 10)
    return {"result": "success"}
```

## Common Patterns

### Pattern 1: Freemium with Upgrade Path

```python
# Free tier with limits
free_tier = ProductTier(
    tier_id="free",
    name="Free",
    pricing=FreePricing(monthly_limit=1000),
)

# Paid tier with more
pro_tier = ProductTier(
    tier_id="pro",
    name="Pro",
    pricing=PaidPricing(amount=29.99, usage_included=100000),
)
```

### Pattern 2: Credits that Roll Over

```python
# User buys credits
um.add_credits("user123", "my_api", 500, from_subscription=False)

# These purchased credits persist until used
# Subscription credits reset each month:
um.get_user_credits("user123", "my_api").reset_subscription_credits(1000)
# But purchased credits remain!
```

### Pattern 3: Different Costs per Action

```python
pricing = CreditPricing(
    cost_per_credit=0.01,
    action_costs={
        "read": 1,          # Cheap operation
        "write": 2,         # More expensive
        "ai_process": 50,   # Very expensive
    },
)

# Usage
tier = ProductTier(tier_id="credit", name="Credit", pricing=pricing)
um.use_action(user_id, product_id, tier, "ai_process")  # Uses 50 credits
```

### Pattern 4: Time-based Usage Tracking

```python
from pricing_library import UsagePeriod

# Get stats for different periods
daily_stats = um.get_usage_stats(user_id, product_id, UsagePeriod.DAILY)
monthly_stats = um.get_usage_stats(user_id, product_id, UsagePeriod.MONTHLY)

print(f"Today: {daily_stats['total_actions']} actions")
print(f"This month: {monthly_stats['total_actions']} actions")
```

### Pattern 5: Usage-based Alerts

```python
# Check if user is approaching limit
limit = um.get_usage_limit(user_id, product_id, UsagePeriod.MONTHLY)
if limit:
    percentage = (limit.current_usage / limit.limit) * 100
    if percentage > 80:
        send_alert(f"You've used {percentage}% of your monthly limit")
```

## Best Practices

1. **Always initialize users properly** when they subscribe
2. **Use `use_action()`** instead of manual deduction - it handles limits and credits
3. **Store tier_id with user** in your database for quick lookups
4. **Reset subscription credits** at billing cycle
5. **Log all usage** for analytics and debugging
6. **Handle exceptions** gracefully in your API
7. **Add metadata** to usage records for better tracking

## Troubleshooting

### Issue: Credits not deducting
- Check that user is initialized: `um.initialize_user_credits()`
- Verify tier has credit pricing: `isinstance(tier.pricing, CreditPricing)`

### Issue: Usage limits not working
- Ensure limits are set: `um.set_usage_limit()`
- Check tier has FreePricing with limits

### Issue: Getting 401 errors in FastAPI
- Implement proper user ID extraction
- Override `get_user_id_from_request()` in dependencies
