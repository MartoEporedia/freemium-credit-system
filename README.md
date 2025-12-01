# Freemium Credit System - Product Pricing Library

A flexible Python library for managing products with free, paid, credit-based, and mixed pricing systems. Built for easy integration with FastAPI.

## ✨ Version 2.0.0 - NEW Features!

- **🗄️ PostgreSQL/SQLAlchemy Support**: Optional database persistence for production use
- **👥 Multi-Tenancy**: Support for flexible entity types (user, family, team, organization, etc.)
- **📊 Credit Transaction Audit Trail**: Complete history of all credit operations
- **🔄 Alembic Migrations**: Manage database schema changes easily
- **⚡ Dual-Mode Architecture**: Seamlessly switch between in-memory and database modes
- **🔒 Backward Compatible**: All v1.x code works without modification!

## Features

- **Multiple Pricing Models**
  - **Free**: With optional daily/monthly usage limits
  - **Paid**: Subscription-based (monthly, yearly) or one-time payments
  - **Credit**: Pay-per-use with configurable action costs
  - **Mixed**: Subscription + included credits + additional credit purchases

- **Usage Tracking**
  - Automatic usage recording
  - Historical usage data
  - Usage statistics by period
  - Credit balance management
  - **NEW**: Full audit trail in database mode

- **Database Persistence** (NEW in v2.0)
  - PostgreSQL support via SQLAlchemy
  - Automatic credit transaction logging
  - Usage analytics and reporting
  - Alembic migrations for schema management

- **Multi-Tenancy** (NEW in v2.0)
  - Flexible entity types (user, family, team, organization)
  - Configurable entity identifiers
  - Separate credit wallets per entity

- **FastAPI Integration**
  - Ready-to-use dependencies
  - Automatic credit checking
  - Usage limit enforcement
  - Middleware for request tracking
  - Custom error handlers
  - **NEW**: Database-backed managers

- **Flexible Architecture**
  - Product and tier management
  - Credit balance management
  - Configurable action costs
  - Metadata support throughout
  - **NEW**: In-memory or database mode

## Installation

```bash
# Basic installation (in-memory mode)
pip install -r requirements.txt

# For database support
pip install -r requirements.txt
# This includes: sqlalchemy, alembic, psycopg2-binary
```

## Quick Start

### 1. In-Memory Mode (Simple, No Database)

```python
from pricing_library import (
    ProductManager,
    UsageManager,
    Product,
    ProductTier,
    FreePricing,
    PaidPricing,
    CreditPricing,
    MixedPricing,
)
from pricing_library.models.pricing import RecurrenceInterval

# Initialize managers (in-memory mode)
product_manager = ProductManager()
usage_manager = UsageManager()

# Create a product
product = product_manager.create_product(
    product_id="api_service",
    name="API Service",
    description="My awesome API",
)
```

### 1b. Database Mode (Production-Ready) - NEW in v2.0!

```python
from pricing_library import ProductManager, UsageManager, PricingConfig
from pricing_library.database import init_db, get_session

# Configure database connection
config = PricingConfig.for_database(
    database_url="postgresql://user:password@localhost/pricing_db",
    entity_type="user",  # or "family", "team", "organization"
)

# Initialize database (creates tables)
init_db(config)

# Create managers with database support
session = get_session(config)
product_manager = ProductManager(db_session=session, config=config)
usage_manager = UsageManager(db_session=session, config=config)

# Use exactly the same API - data is now persisted!
product = product_manager.create_product(
    product_id="api_service",
    name="API Service",
    description="My awesome API",
)
```

### 2. Define Pricing Tiers

#### Free Tier

```python
free_tier = ProductTier(
    tier_id="free",
    name="Free Tier",
    pricing=FreePricing(
        daily_limit=100,
        monthly_limit=1000,
    ),
    features=["100 API calls/day", "Community support"],
)
product.add_tier(free_tier)
```

#### Paid Subscription Tier

```python
pro_tier = ProductTier(
    tier_id="pro",
    name="Pro",
    pricing=PaidPricing(
        amount=29.99,
        interval=RecurrenceInterval.MONTHLY,
        usage_included=10000,
    ),
    features=["10k API calls/month", "Priority support"],
)
product.add_tier(pro_tier)
```

#### Credit-Based Tier

```python
credit_tier = ProductTier(
    tier_id="payg",
    name="Pay As You Go",
    pricing=CreditPricing(
        cost_per_credit=0.01,
        credit_packages={
            100: 9.99,
            500: 45.99,
            1000: 89.99,
        },
        action_costs={
            "simple_query": 1,
            "complex_query": 5,
        },
    ),
    features=["Pay only for what you use"],
)
product.add_tier(credit_tier)
```

#### Mixed Pricing Tier

```python
enterprise_tier = ProductTier(
    tier_id="enterprise",
    name="Enterprise",
    pricing=MixedPricing(
        subscription_amount=299.99,
        subscription_interval=RecurrenceInterval.MONTHLY,
        included_credits=50000,
        additional_credit_cost=0.005,
        action_costs={
            "simple_query": 1,
            "complex_query": 3,
        },
    ),
    features=["50k credits included", "Discounted additional credits"],
)
product.add_tier(enterprise_tier)
```

### 3. Manage User Credits

```python
# Initialize user credits
usage_manager.initialize_user_credits(
    user_id="user123",
    product_id="api_service",
    initial_credits=1000,
    from_subscription=True,
)

# Add credits
usage_manager.add_credits(
    user_id="user123",
    product_id="api_service",
    amount=500,
)

# Check balance
credits = usage_manager.get_user_credits("user123", "api_service")
print(f"Total credits: {credits.total_credits}")
```

### 4. Track Usage

```python
# Manual usage tracking
tier = product.get_tier("payg")
usage_record = usage_manager.use_action(
    user_id="user123",
    product_id="api_service",
    tier=tier,
    action="simple_query",
)

# Get usage statistics
stats = usage_manager.get_usage_stats(
    user_id="user123",
    product_id="api_service",
    period=UsagePeriod.MONTHLY,
)
```

## FastAPI Integration

### Setup

```python
from fastapi import FastAPI, Depends
from pricing_library.fastapi import (
    initialize_managers,
    get_product_manager,
    get_usage_manager,
    require_credits,
    PricingMiddleware,
)

app = FastAPI()

# Initialize managers
product_manager = ProductManager()
usage_manager = UsageManager()
initialize_managers(product_manager, usage_manager)

# Add middleware (optional)
app.add_middleware(
    PricingMiddleware,
    product_manager=product_manager,
    usage_manager=usage_manager,
    add_usage_headers=True,
)
```

### Using Dependencies

```python
@app.post("/api/query")
async def execute_query(
    query: str,
    usage_record=Depends(require_credits("api_service", "simple_query")),
):
    """
    This endpoint automatically:
    - Checks if user has sufficient credits
    - Checks if usage limits are exceeded
    - Deducts credits
    - Records usage
    """
    return {"status": "success", "credits_used": usage_record.credits_used}
```

### Manual Credit Management

```python
@app.post("/api/query/advanced")
async def advanced_query(
    query: str,
    pm: ProductManager = Depends(get_product_manager),
    um: UsageManager = Depends(get_usage_manager),
):
    # Get user info from your auth system
    user_id = "user123"
    tier = pm.get_product_tier("api_service", "pro")

    # Process action with automatic credit/limit checking
    usage_record = um.use_action(
        user_id=user_id,
        product_id="api_service",
        tier=tier,
        action="complex_query",
    )

    return {"status": "success"}
```

## Multi-Tenancy Example (NEW in v2.0)

```python
# Configure for family-based app instead of user-based
config = PricingConfig.for_database(
    database_url="postgresql://...",
    entity_type="family"  # Track by family instead of user!
)

session = get_session(config)
um = UsageManager(db_session=session, config=config)

# Initialize credits for a family
um.initialize_user_credits(
    user_id="family_12345",  # This is actually a family_id
    product_id="family_app",
    initial_credits=100,
)

# Deduct credits for family usage
um.deduct_credits(
    user_id="family_12345",
    product_id="family_app",
    amount=5,
    operation_type="ai_chat"
)
```

## Examples

See the complete examples in the `examples/` directory:

```bash
# In-memory example
python examples/fastapi_example.py

# Database example (NEW in v2.0)
python examples/fastapi_database_example.py

# Or with uvicorn
uvicorn examples.fastapi_example:app --reload
```

The examples include:
- Complete product setup with all pricing models
- User subscription management
- Credit purchasing
- Usage tracking and statistics
- FastAPI dependencies and middleware
- Error handling
- **NEW**: Database persistence
- **NEW**: Multi-tenancy patterns

## API Reference

### Core Classes

#### ProductManager
- `create_product(product_id, name, description)` - Create a new product
- `get_product(product_id)` - Get a product by ID
- `add_tier_to_product(product_id, tier)` - Add a tier to a product
- `list_products(active_only=True)` - List all products

#### UsageManager
- `initialize_user_credits(user_id, product_id, initial_credits)` - Initialize user credits
- `get_user_credits(user_id, product_id)` - Get user's credit balance
- `add_credits(user_id, product_id, amount)` - Add credits to user
- `deduct_credits(user_id, product_id, amount)` - Deduct credits from user
- `use_action(user_id, product_id, tier, action)` - Process an action (checks limits, deducts credits)
- `get_usage_stats(user_id, product_id, period)` - Get usage statistics
- `set_usage_limit(user_id, product_id, period, limit)` - Set usage limits

### Pricing Models

- `FreePricing` - Free tier with optional limits
- `PaidPricing` - Subscription or one-time payment
- `CreditPricing` - Pay-per-use credits
- `MixedPricing` - Subscription + credits

### FastAPI Integration

- `initialize_managers(product_manager, usage_manager)` - Initialize global managers
- `get_product_manager()` - Dependency to get product manager
- `get_usage_manager()` - Dependency to get usage manager
- `require_credits(product_id, action)` - Dependency to require credits for endpoint
- `check_usage_limit(product_id)` - Dependency to check usage limits
- `PricingMiddleware` - Middleware for automatic tracking

## Error Handling

The library provides custom exceptions:

- `InsufficientCreditsError` - User doesn't have enough credits
- `UsageLimitExceededError` - Usage limit has been exceeded
- `ProductNotFoundError` - Product doesn't exist
- `InvalidPricingConfigError` - Invalid pricing configuration

These are automatically converted to appropriate HTTP responses in FastAPI:
- 402 Payment Required - Insufficient credits
- 429 Too Many Requests - Usage limit exceeded
- 404 Not Found - Product not found

## Database Setup (NEW in v2.0)

For detailed information on using database mode, see [DATABASE_GUIDE.md](DATABASE_GUIDE.md).

Quick setup:

```bash
# Create PostgreSQL database
createdb pricing_library

# Run migrations
alembic upgrade head

# Configure in your code
config = PricingConfig.for_database("postgresql://user:pass@localhost/pricing_library")
init_db(config)
```

## Testing

Run the tests:

```bash
# All tests (including backward compatibility)
pytest tests/

# Specific test file
pytest tests/test_pricing.py -v

# Database mode tests
pytest tests/test_database_mode.py -v
```

## Documentation

- **[README.md](README.md)** - This file, quick start guide
- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Comprehensive usage examples
- **[DATABASE_GUIDE.md](DATABASE_GUIDE.md)** - Database setup and multi-tenancy guide
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

## Migration from v1.x to v2.0

**Good news: No breaking changes!** All v1.x code works without modification.

To add database support:

```diff
  from pricing_library import ProductManager, UsageManager
+ from pricing_library import PricingConfig
+ from pricing_library.database import init_db, get_session

+ config = PricingConfig.for_database("postgresql://...")
+ init_db(config)
+ session = get_session(config)

- pm = ProductManager()
- um = UsageManager()
+ pm = ProductManager(db_session=session, config=config)
+ um = UsageManager(db_session=session, config=config)
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Version History

- **v2.0.0** - PostgreSQL support, multi-tenancy, audit trails, Alembic migrations
- **v1.0.0** - Initial release with in-memory support
