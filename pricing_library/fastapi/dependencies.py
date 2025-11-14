"""FastAPI dependencies for pricing and usage management."""

from typing import Optional, Callable
from fastapi import Depends, HTTPException, Request, status
from functools import wraps

from ..managers.product_manager import ProductManager
from ..managers.usage_manager import UsageManager
from ..exceptions import (
    InsufficientCreditsError,
    UsageLimitExceededError,
    ProductNotFoundError,
)


# Global instances (can be overridden with dependency injection)
_product_manager: Optional[ProductManager] = None
_usage_manager: Optional[UsageManager] = None


def initialize_managers(
    product_manager: Optional[ProductManager] = None,
    usage_manager: Optional[UsageManager] = None,
):
    """Initialize global manager instances."""
    global _product_manager, _usage_manager
    _product_manager = product_manager or ProductManager()
    _usage_manager = usage_manager or UsageManager()


def get_product_manager() -> ProductManager:
    """Dependency to get the product manager."""
    if _product_manager is None:
        initialize_managers()
    return _product_manager


def get_usage_manager() -> UsageManager:
    """Dependency to get the usage manager."""
    if _usage_manager is None:
        initialize_managers()
    return _usage_manager


def get_user_id_from_request(request: Request) -> str:
    """
    Extract user ID from request.
    This is a placeholder - override with your own authentication logic.
    """
    # Try to get user_id from various sources
    user_id = None

    # From path parameters
    if hasattr(request, "path_params"):
        user_id = request.path_params.get("user_id")

    # From query parameters
    if not user_id:
        user_id = request.query_params.get("user_id")

    # From headers
    if not user_id:
        user_id = request.headers.get("X-User-ID")

    # From request state (set by auth middleware)
    if not user_id and hasattr(request.state, "user_id"):
        user_id = request.state.user_id

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in request",
        )

    return user_id


def require_credits(
    product_id: str,
    action: str,
    get_user_id: Callable[[Request], str] = get_user_id_from_request,
):
    """
    Dependency factory to require credits for an endpoint.

    Usage:
        @app.post("/api/action")
        async def perform_action(
            usage_record = Depends(require_credits("product_1", "api_call"))
        ):
            return {"status": "success"}
    """

    async def dependency(
        request: Request,
        product_manager: ProductManager = Depends(get_product_manager),
        usage_manager: UsageManager = Depends(get_usage_manager),
    ):
        try:
            user_id = get_user_id(request)

            # Get user's tier (this should be stored somewhere, simplified here)
            # In production, you'd look this up from a database
            tier_id = getattr(request.state, "tier_id", "free")

            product = product_manager.get_product(product_id)
            tier = product.get_tier(tier_id)

            if not tier:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid tier: {tier_id}",
                )

            # Process the action
            usage_record = usage_manager.use_action(
                user_id=user_id,
                product_id=product_id,
                tier=tier,
                action=action,
                metadata={"endpoint": str(request.url)},
            )

            return usage_record

        except InsufficientCreditsError as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits: {e}",
            )
        except UsageLimitExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Usage limit exceeded: {e}",
            )
        except ProductNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )

    return dependency


def check_usage_limit(
    product_id: str,
    get_user_id: Callable[[Request], str] = get_user_id_from_request,
):
    """
    Dependency to check if user has exceeded usage limits.

    Usage:
        @app.get("/api/data")
        async def get_data(
            _ = Depends(check_usage_limit("product_1"))
        ):
            return {"data": "..."}
    """

    async def dependency(
        request: Request,
        product_manager: ProductManager = Depends(get_product_manager),
        usage_manager: UsageManager = Depends(get_usage_manager),
    ):
        try:
            user_id = get_user_id(request)
            tier_id = getattr(request.state, "tier_id", "free")

            product = product_manager.get_product(product_id)
            tier = product.get_tier(tier_id)

            if not tier:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid tier: {tier_id}",
                )

            usage_manager.check_usage_limits(user_id, product_id, tier)

        except UsageLimitExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Usage limit exceeded: {e}",
            )
        except ProductNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )

    return dependency


def track_usage(product_id: str, action: str):
    """
    Decorator to automatically track usage for an endpoint.

    Usage:
        @app.post("/api/action")
        @track_usage("product_1", "api_call")
        async def perform_action(request: Request):
            return {"status": "success"}
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request object in args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")

            if request:
                usage_manager = get_usage_manager()
                try:
                    user_id = get_user_id_from_request(request)
                    tier_id = getattr(request.state, "tier_id", "free")

                    # Execute the actual function
                    result = await func(*args, **kwargs)

                    # Record successful usage
                    usage_manager.record_usage(
                        user_id=user_id,
                        product_id=product_id,
                        tier_id=tier_id,
                        action=action,
                        success=True,
                    )

                    return result

                except Exception as e:
                    # Record failed usage
                    try:
                        user_id = get_user_id_from_request(request)
                        tier_id = getattr(request.state, "tier_id", "free")
                        usage_manager.record_usage(
                            user_id=user_id,
                            product_id=product_id,
                            tier_id=tier_id,
                            action=action,
                            success=False,
                            metadata={"error": str(e)},
                        )
                    except:
                        pass  # Don't fail if we can't record
                    raise
            else:
                return await func(*args, **kwargs)

        return wrapper

    return decorator
