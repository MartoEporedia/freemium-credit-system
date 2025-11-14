"""Custom exceptions for the pricing library."""


class PricingLibraryError(Exception):
    """Base exception for all pricing library errors."""
    pass


class InsufficientCreditsError(PricingLibraryError):
    """Raised when a user doesn't have enough credits for an action."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient credits: required {required}, available {available}"
        )


class UsageLimitExceededError(PricingLibraryError):
    """Raised when a usage limit has been exceeded."""

    def __init__(self, limit_type: str, limit: int, current: int):
        self.limit_type = limit_type
        self.limit = limit
        self.current = current
        super().__init__(
            f"Usage limit exceeded for {limit_type}: {current}/{limit}"
        )


class ProductNotFoundError(PricingLibraryError):
    """Raised when a product is not found."""

    def __init__(self, product_id: str):
        self.product_id = product_id
        super().__init__(f"Product not found: {product_id}")


class InvalidPricingConfigError(PricingLibraryError):
    """Raised when pricing configuration is invalid."""
    pass
