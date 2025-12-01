"""Product management functionality."""

from typing import Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.product import Product, ProductTier
from ..models.pricing import BasePricing
from ..exceptions import ProductNotFoundError, InvalidPricingConfigError
from ..config import PricingConfig


class ProductManager:
    """
    Manages products and their pricing tiers.

    Supports both in-memory mode (default) and database mode.

    In-memory mode:
        pm = ProductManager()

    Database mode:
        from pricing_library.database import get_session
        from pricing_library.config import PricingConfig

        config = PricingConfig.for_database("postgresql://...")
        session = get_session(config)
        pm = ProductManager(db_session=session, config=config)
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        config: Optional[PricingConfig] = None,
    ):
        """
        Initialize ProductManager.

        Args:
            db_session: Optional SQLAlchemy session for database mode
            config: Optional configuration (required if db_session is provided)
        """
        self._products: Dict[str, Product] = {}
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

    def create_product(
        self,
        product_id: str,
        name: str,
        description: str,
        metadata: Optional[Dict] = None,
    ) -> Product:
        """
        Create a new product.

        In database mode, the product is created in memory for now.
        Tiers are persisted to database when added via add_tier_to_product.
        """
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
        """
        Add a pricing tier to an existing product.

        In database mode, the tier is persisted to the subscription_plans table.
        """
        product = self.get_product(product_id)
        product.add_tier(tier)

        # Persist to database if in database mode
        if self.use_database:
            self._persist_tier(product_id, tier)

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

    # Database persistence methods

    def _persist_tier(self, product_id: str, tier: ProductTier) -> None:
        """
        Persist a tier to the database.

        Args:
            product_id: Product ID
            tier: Product tier to persist
        """
        if not self.use_database:
            return

        from ..database.models import SubscriptionPlan

        # Create unique plan_id
        plan_id = f"{product_id}_{tier.tier_id}"

        # Check if plan already exists
        existing_plan = (
            self._db_session.query(SubscriptionPlan)
            .filter_by(plan_id=plan_id)
            .first()
        )

        if existing_plan:
            # Update existing plan
            existing_plan.name = tier.name
            existing_plan.pricing_type = tier.pricing.pricing_type.value
            existing_plan.pricing_config = tier.pricing.to_dict()
            existing_plan.features = tier.features
            existing_plan.is_active = True
            existing_plan.updated_at = datetime.utcnow()
        else:
            # Create new plan
            plan = SubscriptionPlan(
                plan_id=plan_id,
                product_id=product_id,
                name=tier.name,
                tier_id=tier.tier_id,
                pricing_type=tier.pricing.pricing_type.value,
                pricing_config=tier.pricing.to_dict(),
                features=tier.features,
                is_active=True,
            )
            self._db_session.add(plan)

        self._db_session.commit()

    def load_from_database(self) -> None:
        """
        Load products and tiers from the database.

        This method loads all active plans from the database and reconstructs
        the in-memory product catalog.
        """
        if not self.use_database:
            return

        from ..database.models import SubscriptionPlan
        from ..models.pricing import (
            FreePricing,
            PaidPricing,
            CreditPricing,
            MixedPricing,
            PricingType,
        )

        # Query all active plans
        plans = (
            self._db_session.query(SubscriptionPlan)
            .filter_by(is_active=True)
            .all()
        )

        # Group by product_id
        products_dict = {}
        for plan in plans:
            if plan.product_id not in products_dict:
                products_dict[plan.product_id] = []
            products_dict[plan.product_id].append(plan)

        # Create products and tiers
        for product_id, plan_list in products_dict.items():
            # Use the first plan to get product info
            first_plan = plan_list[0]

            # Create product if it doesn't exist
            if product_id not in self._products:
                product = Product(
                    product_id=product_id,
                    name=first_plan.name,  # Will be overridden if needed
                    description="",
                    metadata={},
                )
                self._products[product_id] = product

            # Add tiers
            for plan in plan_list:
                # Reconstruct pricing object from config
                pricing_config = plan.pricing_config
                pricing_type = PricingType(plan.pricing_type)

                if pricing_type == PricingType.FREE:
                    pricing = FreePricing(**pricing_config)
                elif pricing_type == PricingType.PAID:
                    pricing = PaidPricing(**pricing_config)
                elif pricing_type == PricingType.CREDIT:
                    pricing = CreditPricing(**pricing_config)
                elif pricing_type == PricingType.MIXED:
                    pricing = MixedPricing(**pricing_config)
                else:
                    continue

                # Create tier
                tier = ProductTier(
                    tier_id=plan.tier_id,
                    name=plan.name,
                    pricing=pricing,
                    features=plan.features or [],
                )

                # Add tier to product (skip if already exists)
                product = self._products[product_id]
                if not product.get_tier(tier.tier_id):
                    product.add_tier(tier)
