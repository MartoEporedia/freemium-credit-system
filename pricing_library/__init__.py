"""
Freemium Credit System - Product Pricing Library
A flexible Python library for managing products with free, paid, credit, and mixed pricing systems.

Version 2.0.0 adds:
- PostgreSQL/SQLAlchemy database support
- Multi-tenancy (user, family, team, organization)
- Credit transaction audit trail
- Alembic migrations
"""

from .models.pricing import PricingType, FreePricing, PaidPricing, CreditPricing, MixedPricing
from .models.product import Product, ProductTier
from .models.usage import UsageRecord, UsageLimit, UserCredits, UsagePeriod
from .managers.product_manager import ProductManager
from .managers.usage_manager import UsageManager
from .config import PricingConfig
from .exceptions import (
    PricingLibraryError,
    InsufficientCreditsError,
    UsageLimitExceededError,
    ProductNotFoundError,
)

__version__ = "2.0.0"

__all__ = [
    # Pricing models
    "PricingType",
    "FreePricing",
    "PaidPricing",
    "CreditPricing",
    "MixedPricing",
    # Product models
    "Product",
    "ProductTier",
    # Usage models
    "UsageRecord",
    "UsageLimit",
    "UserCredits",
    "UsagePeriod",
    # Managers
    "ProductManager",
    "UsageManager",
    # Configuration
    "PricingConfig",
    # Exceptions
    "PricingLibraryError",
    "InsufficientCreditsError",
    "UsageLimitExceededError",
    "ProductNotFoundError",
]
