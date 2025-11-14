"""FastAPI middleware for pricing and usage management."""

from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..managers.product_manager import ProductManager
from ..managers.usage_manager import UsageManager
from ..exceptions import (
    InsufficientCreditsError,
    UsageLimitExceededError,
)


class PricingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically handle pricing and usage tracking.

    This middleware can:
    - Track all API usage automatically
    - Check usage limits before processing requests
    - Add usage information to response headers
    """

    def __init__(
        self,
        app,
        product_manager: ProductManager,
        usage_manager: UsageManager,
        track_all_requests: bool = False,
        add_usage_headers: bool = True,
        user_id_extractor: Optional[Callable[[Request], Optional[str]]] = None,
    ):
        super().__init__(app)
        self.product_manager = product_manager
        self.usage_manager = usage_manager
        self.track_all_requests = track_all_requests
        self.add_usage_headers = add_usage_headers
        self.user_id_extractor = user_id_extractor or self._default_user_id_extractor

    def _default_user_id_extractor(self, request: Request) -> Optional[str]:
        """Default method to extract user ID from request."""
        # Try multiple sources
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            user_id = request.query_params.get("user_id")
        if not user_id and hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        return user_id

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request through the middleware."""
        user_id = self.user_id_extractor(request)

        # If we have a user_id and tracking is enabled
        if user_id and self.track_all_requests:
            product_id = getattr(request.state, "product_id", "default")
            tier_id = getattr(request.state, "tier_id", "free")

            try:
                # Get product and tier
                product = self.product_manager.get_product(product_id)
                tier = product.get_tier(tier_id)

                if tier:
                    # Check usage limits
                    try:
                        self.usage_manager.check_usage_limits(
                            user_id, product_id, tier
                        )
                    except UsageLimitExceededError as e:
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": "Usage limit exceeded",
                                "detail": str(e),
                                "limit_type": e.limit_type,
                                "limit": e.limit,
                                "current": e.current,
                            },
                        )

            except Exception:
                # If we can't check limits, let the request through
                pass

        # Process the request
        response = await call_next(request)

        # Add usage information to response headers
        if user_id and self.add_usage_headers:
            try:
                product_id = getattr(request.state, "product_id", "default")
                credits = self.usage_manager.get_user_credits(user_id, product_id)

                response.headers["X-Credits-Remaining"] = str(credits.total_credits)
                response.headers["X-Subscription-Credits"] = str(
                    credits.subscription_credits
                )
                response.headers["X-Purchased-Credits"] = str(
                    credits.purchased_credits
                )
            except Exception:
                # Don't fail the request if we can't add headers
                pass

        return response
