"""Product management functionality."""

from typing import Dict, List, Optional
from datetime import datetime

from ..models.product import Product, ProductTier
from ..models.pricing import BasePricing
from ..exceptions import ProductNotFoundError, InvalidPricingConfigError


class ProductManager:
    """Manages products and their pricing tiers."""

    def __init__(self):
        self._products: Dict[str, Product] = {}

    def create_product(
        self,
        product_id: str,
        name: str,
        description: str,
        metadata: Optional[Dict] = None,
    ) -> Product:
        """Create a new product."""
        if product_id in self._products:
            raise InvalidPricingConfigError(
                f"Product with ID {product_id} already exists"
            )

        product = Product(
            product_id=product_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )
        self._products[product_id] = product
        return product

    def add_product(self, product: Product) -> None:
        """Add an existing product to the manager."""
        if product.product_id in self._products:
            raise InvalidPricingConfigError(
                f"Product with ID {product.product_id} already exists"
            )
        self._products[product.product_id] = product

    def get_product(self, product_id: str) -> Product:
        """Get a product by ID."""
        product = self._products.get(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        return product

    def get_product_tier(self, product_id: str, tier_id: str) -> ProductTier:
        """Get a specific tier from a product."""
        product = self.get_product(product_id)
        tier = product.get_tier(tier_id)
        if not tier:
            raise InvalidPricingConfigError(
                f"Tier {tier_id} not found in product {product_id}"
            )
        return tier

    def add_tier_to_product(
        self,
        product_id: str,
        tier: ProductTier,
    ) -> None:
        """Add a pricing tier to an existing product."""
        product = self.get_product(product_id)
        product.add_tier(tier)

    def list_products(self, active_only: bool = True) -> List[Product]:
        """List all products."""
        products = list(self._products.values())
        if active_only:
            products = [p for p in products if p.is_active]
        return products

    def deactivate_product(self, product_id: str) -> None:
        """Deactivate a product."""
        product = self.get_product(product_id)
        product.is_active = False
        product.updated_at = datetime.utcnow()

    def activate_product(self, product_id: str) -> None:
        """Activate a product."""
        product = self.get_product(product_id)
        product.is_active = True
        product.updated_at = datetime.utcnow()

    def remove_product(self, product_id: str) -> None:
        """Remove a product from the manager."""
        if product_id not in self._products:
            raise ProductNotFoundError(product_id)
        del self._products[product_id]

    def export_products(self) -> List[Dict]:
        """Export all products as dictionaries."""
        return [product.to_dict() for product in self._products.values()]
