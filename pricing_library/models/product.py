"""Product models for the pricing library."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .pricing import BasePricing, FreePricing, PaidPricing, CreditPricing, MixedPricing


@dataclass
class ProductTier:
    """Represents a pricing tier for a product."""
    tier_id: str
    name: str
    pricing: BasePricing
    features: List[str] = field(default_factory=list)
    max_users: Optional[int] = None
    priority_support: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert tier to dictionary."""
        return {
            "tier_id": self.tier_id,
            "name": self.name,
            "pricing": self.pricing.to_dict(),
            "features": self.features,
            "max_users": self.max_users,
            "priority_support": self.priority_support,
            "metadata": self.metadata,
        }


@dataclass
class Product:
    """Represents a product with pricing information."""
    product_id: str
    name: str
    description: str
    tiers: List[ProductTier] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_tier(self, tier: ProductTier) -> None:
        """Add a pricing tier to the product."""
        self.tiers.append(tier)
        self.updated_at = datetime.utcnow()

    def get_tier(self, tier_id: str) -> Optional[ProductTier]:
        """Get a specific tier by ID."""
        for tier in self.tiers:
            if tier.tier_id == tier_id:
                return tier
        return None

    def get_free_tier(self) -> Optional[ProductTier]:
        """Get the free tier if it exists."""
        for tier in self.tiers:
            if isinstance(tier.pricing, FreePricing):
                return tier
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert product to dictionary."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "description": self.description,
            "tiers": [tier.to_dict() for tier in self.tiers],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
