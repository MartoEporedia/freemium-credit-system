"""
Freemium Credit System - Product Pricing Library
A flexible Python library for managing products with free, paid, credit, and mixed pricing systems.
"""

from .models.pricing import PricingType, FreePricing, PaidPricing, CreditPricing, MixedPricing
from .models.product import Product, ProductTier
from .models.usage import UsageRecord, UsageLimit, UserCredits, UsagePeriod
from .managers.product_manager import ProductManager
from .managers.usage_manager import UsageManager
from .exceptions import (
    PricingLibraryError,
    InsufficientCreditsError,
    UsageLimitExceededError,
    ProductNotFoundError,
)

__version__ = "0.1.0"

__all__ = [
    "PricingType",
    "FreePricing",
    "PaidPricing",
    "CreditPricing",
    "MixedPricing",
    "Product",
    "ProductTier",
    "UsageRecord",
    "UsageLimit",
    "UserCredits",
    "UsagePeriod",
    "ProductManager",
    "UsageManager",
    "PricingLibraryError",
    "InsufficientCreditsError",
    "UsageLimitExceededError",
    "ProductNotFoundError",
]
