# Database Persistence Guide

This guide explains how to use the freemium-credit-system library with PostgreSQL database persistence.

## Version 2.0.0 Features

- **PostgreSQL/SQLAlchemy Support**: Persist all data to a PostgreSQL database
- **Multi-Tenancy**: Support for flexible entity types (user, family, team, organization, etc.)
- **Credit Transaction Audit Trail**: Complete history of all credit operations
- **Alembic Migrations**: Manage database schema changes
- **Dual-Mode Architecture**: Seamlessly switch between in-memory and database modes

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This includes:
- `sqlalchemy>=2.0.0` - Database ORM
- `alembic>=1.12.0` - Database migrations
- `psycopg2-binary>=2.9.0` - PostgreSQL adapter

### 2. Set Up PostgreSQL Database

```bash
# Create a PostgreSQL database
createdb pricing_library

# Or use Docker
docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres
docker exec -it postgres createdb -U postgres pricing_library
```

### 3. Configure Database Connection

```python
from pricing_library import PricingConfig
from pricing_library.database import init_db, get_session

# Create configuration
config = PricingConfig.for_database(
    database_url="postgresql://user:password@localhost/pricing_library",
    entity_type="user",  # or "family", "team", "organization"
)

# Initialize database (creates tables)
init_db(config)
```

### 4. Use Database-Backed Managers

```python
from pricing_library import ProductManager, UsageManager

# Create managers with database support
session = get_session(config)
product_manager = ProductManager(db_session=session, config=config)
usage_manager = UsageManager(db_session=session, config=config)

# Use them exactly like before - but data is now persisted!
product = product_manager.create_product(
    product_id="my_app",
    name="My Application",
    description="My awesome app"
)
```

## Multi-Tenancy Support

One of the major features in v2.0 is flexible multi-tenancy. Instead of being limited to `user_id`, you can track any entity type.

### Example: Family-Based App

```python
# Configure for family-based tenancy
config = PricingConfig.for_database(
    database_url="postgresql://...",
    entity_type="family"  # Track by family instead of user
)

session = get_session(config)
um = UsageManager(db_session=session, config=config)

# Initialize credits for a family
um.initialize_user_credits(
    user_id="family_12345",  # This is actually a family_id
    product_id="family_app",
    initial_credits=100,
)

# Use credits
um.deduct_credits(
    user_id="family_12345",
    product_id="family_app",
    amount=5,
    operation_type="ai_chat",
    description="Family chat with AI assistant"
)
```

### Example: Team/Organization App

```python
# Configure for team-based tenancy
config = PricingConfig.for_database(
    database_url="postgresql://...",
    entity_type="team"
)

session = get_session(config)
um = UsageManager(db_session=session, config=config)

# Track team usage
um.initialize_user_credits(
    user_id="team_engineering",
    product_id="project_manager",
    initial_credits=1000,
)
```

## Database Schema

The library creates the following tables:

### subscription_plans
Stores product tiers with pricing configurations.

- `id`: Primary key
- `plan_id`: Unique plan identifier (format: `{product_id}_{tier_id}`)
- `product_id`: Product identifier
- `tier_id`: Tier identifier
- `name`: Plan name
- `pricing_type`: Type of pricing (free/paid/credit/mixed)
- `pricing_config`: JSONB - Full pricing configuration
- `features`: JSONB - List of features
- `metadata`: JSONB - Additional metadata
- `is_active`: Boolean flag
- `created_at`, `updated_at`: Timestamps

### credit_wallets
Stores credit balances for each entity.

- `id`: Primary key
- `entity_type`: Type of entity (user/family/team/etc.)
- `entity_id`: Entity identifier
- `product_id`: Product identifier
- `subscription_credits`: Credits from subscription
- `purchased_credits`: Separately purchased credits
- `subscription_plan_id`: Foreign key to subscription_plans (optional)
- `is_credits_enabled`: Feature flag
- `credits_reset_at`, `next_reset_at`: Reset timestamps
- `metadata`: JSONB - Additional metadata
- `created_at`, `updated_at`: Timestamps

**Unique constraint**: `(entity_type, entity_id, product_id)`

### credit_transactions
Audit log for all credit operations.

- `id`: Primary key
- `entity_type`, `entity_id`: Entity identifiers
- `product_id`: Product identifier
- `amount`: Credit amount (positive for additions, negative for deductions)
- `transaction_type`: Type (deduction/purchase/reset/refund)
- `operation_type`: Operation that triggered the transaction (e.g., "ai_chat")
- `balance_before`, `balance_after`: Credit balance tracking
- `description`: Human-readable description
- `metadata`: JSONB - Additional metadata
- `created_at`: Timestamp

### usage_records
Tracks all API usage and actions.

- `id`: Primary key
- `entity_type`, `entity_id`: Entity identifiers
- `product_id`, `tier_id`: Product and tier identifiers
- `action`: Action name
- `credits_used`: Credits consumed
- `success`: Boolean flag
- `metadata`: JSONB - Additional metadata
- `created_at`: Timestamp

### usage_limits
Stores usage limits per period.

- `id`: Primary key
- `entity_type`, `entity_id`: Entity identifiers
- `product_id`: Product identifier
- `period`: Period type (daily/weekly/monthly/yearly)
- `limit_value`: Maximum allowed usage
- `current_usage`: Current usage count
- `reset_at`: When the limit resets
- `created_at`, `updated_at`: Timestamps

**Unique constraint**: `(entity_type, entity_id, product_id, period)`

## Alembic Migrations

The library uses Alembic for database schema management.

### Running Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# View migration history
alembic history

# View current version
alembic current
```

### Creating Custom Migrations

```bash
# After modifying models, create a new migration
alembic revision --autogenerate -m "Add new column"

# Review the generated migration file
# Edit if necessary
# Apply the migration
alembic upgrade head
```

### Custom Schema Names

For PostgreSQL, you can use custom schemas:

```python
config = PricingConfig.for_database(
    database_url="postgresql://...",
    schema_name="pricing"  # Use "pricing" schema instead of "public"
)
```

## Credit Transaction Audit Trail

Every credit operation is logged to the `credit_transactions` table.

### Viewing Transaction History

```python
from pricing_library.database.models import CreditTransaction

# Query recent transactions for an entity
transactions = (
    session.query(CreditTransaction)
    .filter_by(entity_type="user", entity_id="user123")
    .order_by(CreditTransaction.created_at.desc())
    .limit(10)
    .all()
)

for txn in transactions:
    print(f"{txn.created_at}: {txn.transaction_type} "
          f"{txn.amount} credits ({txn.operation_type})")
    print(f"  Balance: {txn.balance_before} -> {txn.balance_after}")
```

### Transaction Types

- `initialization`: Initial credit setup
- `purchase`: Credits purchased
- `subscription`: Credits from subscription
- `deduction`: Credits used for an operation
- `refund`: Credits refunded
- `reset`: Subscription credits reset (monthly)

## Performance Considerations

### Connection Pooling

The library uses SQLAlchemy's connection pooling:

```python
config = PricingConfig.for_database(
    database_url="postgresql://...",
    pool_size=10,          # Number of connections to keep open
    pool_max_overflow=20,  # Additional connections if pool is exhausted
)
```

### Indexes

All frequently-queried columns have indexes:
- `(entity_type, entity_id)` - Entity lookups
- `(entity_type, entity_id, product_id)` - Product-specific queries
- `created_at` - Time-based queries
- `action` - Action-based filtering

### Query Optimization

```python
# Good: Query with specific filters
records = (
    session.query(UsageRecord)
    .filter_by(entity_type="user", entity_id="user123", product_id="app")
    .filter(UsageRecord.created_at >= start_date)
    .all()
)

# Bad: Loading all records then filtering in Python
all_records = session.query(UsageRecord).all()
filtered = [r for r in all_records if r.entity_id == "user123"]
```

## Session Management

### Using Session Scope

```python
from pricing_library.database import session_scope

# Automatic commit/rollback
with session_scope(config) as session:
    um = UsageManager(db_session=session, config=config)
    um.add_credits("user123", "app", 100)
    # Automatically commits on success
    # Automatically rolls back on error
```

### Manual Session Management

```python
from pricing_library.database import get_session

session = get_session(config)
try:
    um = UsageManager(db_session=session, config=config)
    um.add_credits("user123", "app", 100)
    session.commit()
except Exception as e:
    session.rollback()
    raise
finally:
    session.close()
```

## Migrating from In-Memory to Database

### Step 1: Export Existing Data (if needed)

```python
# In-memory mode
pm = ProductManager()
um = UsageManager()

# ... create products and users ...

# Export to dictionaries
products = pm.export_products()
# Save products to a file or process them
```

### Step 2: Switch to Database Mode

```python
# Database mode
config = PricingConfig.for_database("postgresql://...")
init_db(config)

session = get_session(config)
pm = ProductManager(db_session=session, config=config)
um = UsageManager(db_session=session, config=config)

# Recreate products (they'll be persisted)
# ...
```

### Step 3: Update Application Code

No API changes needed! Just add the session and config parameters:

```diff
- pm = ProductManager()
- um = UsageManager()
+ session = get_session(config)
+ pm = ProductManager(db_session=session, config=config)
+ um = UsageManager(db_session=session, config=config)
```

## Advanced Features

### Credit Expiration (Future Feature)

The schema supports credit expiration, but it's not yet implemented:

```python
config = PricingConfig.for_database(
    database_url="postgresql://...",
    enable_credit_expiration=True  # Not yet implemented
)
```

### Feature Flags

Disable credits for specific entities:

```python
from pricing_library.database.models import CreditWallet

wallet = (
    session.query(CreditWallet)
    .filter_by(entity_type="user", entity_id="admin_user")
    .first()
)

# Disable credits for admin users
wallet.is_credits_enabled = False
session.commit()
```

### Custom Metadata

All tables support custom metadata:

```python
# Add metadata when creating credits
um.initialize_user_credits(
    user_id="user123",
    product_id="app",
    initial_credits=100,
)

# Update wallet metadata directly
from pricing_library.database.models import CreditWallet

wallet = session.query(CreditWallet).filter_by(...).first()
wallet.meta_data = {
    "subscription_tier": "premium",
    "referral_source": "friend",
    "custom_field": "value"
}
session.commit()
```

## Troubleshooting

### Connection Errors

```python
# Enable SQL logging
config = PricingConfig.for_database(
    database_url="postgresql://...",
    echo_sql=True  # Print all SQL queries
)
```

### Migration Conflicts

```bash
# Reset database (WARNING: deletes all data)
alembic downgrade base
alembic upgrade head

# Or use Python
from pricing_library.database import init_db
init_db(config, drop_all=True)  # WARNING: deletes all data
```

### Schema Issues

```bash
# Verify current schema
alembic current

# Compare database with models
alembic check
```

## Best Practices

1. **Use Session Scope**: Always use `session_scope()` or proper try/finally blocks
2. **Connection Pooling**: Configure appropriate pool sizes for your workload
3. **Indexes**: Use the built-in indexes for common queries
4. **Transactions**: Group related operations in transactions
5. **Error Handling**: Always handle database errors gracefully
6. **Monitoring**: Monitor transaction logs for audit trails
7. **Backups**: Regularly backup your PostgreSQL database

## Examples

See the `examples/` directory for complete working examples:
- `fastapi_database_example.py` - FastAPI with PostgreSQL
- `multi_tenancy_example.py` - Multi-tenancy patterns

## Support

For issues or questions:
- GitHub Issues: https://github.com/anthropics/freemium-credit-system/issues
- Documentation: See README.md and USAGE_GUIDE.md
