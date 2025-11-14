"""
Comprehensive example of using the pricing library with FastAPI.

This example demonstrates:
1. Setting up products with different pricing tiers
2. Managing user credits and usage limits
3. Using FastAPI dependencies for automatic credit checking
4. Tracking API usage
"""

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from pricing_library import (
    ProductManager,
    UsageManager,
    Product,
    ProductTier,
    FreePricing,
    PaidPricing,
    CreditPricing,
    MixedPricing,
    UsagePeriod,
)
from pricing_library.fastapi import (
    initialize_managers,
    get_product_manager,
    get_usage_manager,
    require_credits,
    check_usage_limit,
    PricingMiddleware,
)
from pricing_library.models.pricing import RecurrenceInterval

# Initialize FastAPI app
app = FastAPI(title="Pricing Library Example")

# Initialize managers
product_manager = ProductManager()
usage_manager = UsageManager()
initialize_managers(product_manager, usage_manager)

# Add pricing middleware (optional)
app.add_middleware(
    PricingMiddleware,
    product_manager=product_manager,
    usage_manager=usage_manager,
    track_all_requests=False,  # Set to True to track all requests
    add_usage_headers=True,
)


# ========== Setup Products and Tiers ==========

def setup_products():
    """Setup example products with different pricing models."""

    # Create an API product
    api_product = product_manager.create_product(
        product_id="api_service",
        name="API Service",
        description="REST API with multiple pricing tiers",
    )

    # Free tier with usage limits
    free_tier = ProductTier(
        tier_id="free",
        name="Free Tier",
        pricing=FreePricing(
            daily_limit=100,
            monthly_limit=1000,
        ),
        features=[
            "100 API calls per day",
            "Basic support",
            "Community access",
        ],
    )
    api_product.add_tier(free_tier)

    # Paid subscription tier
    pro_tier = ProductTier(
        tier_id="pro",
        name="Pro Tier",
        pricing=PaidPricing(
            amount=29.99,
            interval=RecurrenceInterval.MONTHLY,
            usage_included=10000,  # 10k API calls included
        ),
        features=[
            "10,000 API calls per month",
            "Priority support",
            "Advanced features",
        ],
    )
    api_product.add_tier(pro_tier)

    # Credit-based tier
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
                "data_export": 10,
            },
        ),
        features=[
            "Pay only for what you use",
            "No monthly fees",
            "Volume discounts",
        ],
    )
    api_product.add_tier(credit_tier)

    # Mixed pricing tier (subscription + credits)
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
                "data_export": 5,
            },
        ),
        features=[
            "50,000 credits per month included",
            "Discounted additional credits",
            "Dedicated support",
            "SLA guarantee",
        ],
    )
    api_product.add_tier(enterprise_tier)

    print("Products and tiers set up successfully!")


# Setup products on startup
@app.on_event("startup")
async def startup_event():
    setup_products()


# ========== Request/Response Models ==========

class UserSubscription(BaseModel):
    user_id: str
    tier_id: str


class CreditPurchase(BaseModel):
    user_id: str
    credits: int


class QueryRequest(BaseModel):
    query: str
    complexity: str = "simple"  # simple or complex


# ========== Helper: Simulate user authentication ==========

async def get_current_user(request: Request) -> dict:
    """
    Mock authentication - replace with your real auth system.
    For this example, we'll use a header or query param.
    """
    user_id = request.headers.get("X-User-ID") or request.query_params.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # In a real app, you'd look up the user's tier from a database
    # For this example, we'll use a header
    tier_id = request.headers.get("X-Tier-ID", "free")

    # Store in request state for dependencies to use
    request.state.user_id = user_id
    request.state.tier_id = tier_id
    request.state.product_id = "api_service"

    return {"user_id": user_id, "tier_id": tier_id}


# ========== API Endpoints ==========

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Pricing Library Example API",
        "docs": "/docs",
    }


@app.get("/products")
async def list_products(pm: ProductManager = Depends(get_product_manager)):
    """List all available products and their tiers."""
    products = pm.list_products()
    return {"products": [p.to_dict() for p in products]}


@app.post("/users/{user_id}/subscribe")
async def subscribe_user(
    user_id: str,
    subscription: UserSubscription,
    pm: ProductManager = Depends(get_product_manager),
    um: UsageManager = Depends(get_usage_manager),
):
    """Subscribe a user to a tier."""
    try:
        tier = pm.get_product_tier("api_service", subscription.tier_id)

        # Initialize user with the tier
        if isinstance(tier.pricing, FreePricing):
            # Setup usage limits for free tier
            if tier.pricing.daily_limit:
                um.set_usage_limit(
                    user_id, "api_service", UsagePeriod.DAILY, tier.pricing.daily_limit
                )
            if tier.pricing.monthly_limit:
                um.set_usage_limit(
                    user_id, "api_service", UsagePeriod.MONTHLY, tier.pricing.monthly_limit
                )

        elif isinstance(tier.pricing, MixedPricing):
            # Give user their included credits
            um.initialize_user_credits(
                user_id, "api_service", tier.pricing.included_credits, from_subscription=True
            )

        return {
            "message": f"User {user_id} subscribed to {tier.name}",
            "tier": tier.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/users/{user_id}/credits/purchase")
async def purchase_credits(
    user_id: str,
    purchase: CreditPurchase,
    um: UsageManager = Depends(get_usage_manager),
):
    """Purchase additional credits."""
    credits = um.add_credits(user_id, "api_service", purchase.credits, from_subscription=False)
    return {
        "message": f"Added {purchase.credits} credits",
        "total_credits": credits.total_credits,
        "breakdown": {
            "subscription_credits": credits.subscription_credits,
            "purchased_credits": credits.purchased_credits,
        },
    }


@app.get("/users/{user_id}/credits")
async def get_user_credits(
    user_id: str,
    um: UsageManager = Depends(get_usage_manager),
):
    """Get user's credit balance."""
    credits = um.get_user_credits(user_id, "api_service")
    return credits.to_dict()


@app.get("/users/{user_id}/usage/stats")
async def get_usage_stats(
    user_id: str,
    period: UsagePeriod = UsagePeriod.MONTHLY,
    um: UsageManager = Depends(get_usage_manager),
):
    """Get usage statistics for a user."""
    stats = um.get_usage_stats(user_id, "api_service", period)
    return stats


@app.get("/users/{user_id}/usage/history")
async def get_usage_history(
    user_id: str,
    limit: int = 50,
    um: UsageManager = Depends(get_usage_manager),
):
    """Get usage history for a user."""
    history = um.get_user_usage_history(user_id, "api_service", limit)
    return {"history": [record.to_dict() for record in history]}


# Example endpoint with automatic credit checking
@app.post("/api/query")
async def execute_query(
    request: Request,
    query: QueryRequest,
    user: dict = Depends(get_current_user),
    usage_record=Depends(require_credits("api_service", "simple_query")),
):
    """
    Execute a query with automatic credit/limit checking.

    This endpoint uses the require_credits dependency to automatically:
    - Check if user has sufficient credits
    - Check if usage limits are exceeded
    - Deduct credits
    - Record usage
    """
    return {
        "status": "success",
        "query": query.query,
        "result": "Query executed successfully",
        "credits_used": usage_record.credits_used,
    }


# Example endpoint with manual credit management
@app.post("/api/query/advanced")
async def execute_advanced_query(
    request: Request,
    query: QueryRequest,
    user: dict = Depends(get_current_user),
    pm: ProductManager = Depends(get_product_manager),
    um: UsageManager = Depends(get_usage_manager),
):
    """
    Execute a query with manual credit management.

    This shows how to manually handle credits if you need more control.
    """
    try:
        user_id = user["user_id"]
        tier_id = user["tier_id"]

        # Get the tier
        tier = pm.get_product_tier("api_service", tier_id)

        # Determine action based on complexity
        action = "complex_query" if query.complexity == "complex" else "simple_query"

        # Use the action (automatically checks limits and deducts credits)
        usage_record = um.use_action(
            user_id=user_id,
            product_id="api_service",
            tier=tier,
            action=action,
            metadata={"query": query.query},
        )

        return {
            "status": "success",
            "query": query.query,
            "result": "Advanced query executed",
            "credits_used": usage_record.credits_used,
            "remaining_credits": um.get_user_credits(user_id, "api_service").total_credits,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Error Handlers ==========

@app.exception_handler(402)
async def payment_required_handler(request: Request, exc: HTTPException):
    """Handle insufficient credits errors."""
    return JSONResponse(
        status_code=402,
        content={
            "error": "Payment Required",
            "message": "Insufficient credits. Please purchase more credits or upgrade your plan.",
            "detail": exc.detail,
        },
    )


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc: HTTPException):
    """Handle rate limit errors."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too Many Requests",
            "message": "Usage limit exceeded. Please try again later or upgrade your plan.",
            "detail": exc.detail,
        },
    )


# ========== Run the app ==========

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


# ========== Usage Examples ==========

"""
To test this API, you can use the following curl commands:

1. List products:
   curl http://localhost:8000/products

2. Subscribe user to free tier:
   curl -X POST http://localhost:8000/users/user123/subscribe \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123", "tier_id": "free"}'

3. Execute a query (free tier user):
   curl -X POST http://localhost:8000/api/query \
     -H "Content-Type: application/json" \
     -H "X-User-ID: user123" \
     -H "X-Tier-ID: free" \
     -d '{"query": "SELECT * FROM users"}'

4. Subscribe to credit-based tier:
   curl -X POST http://localhost:8000/users/user456/subscribe \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user456", "tier_id": "payg"}'

5. Purchase credits:
   curl -X POST http://localhost:8000/users/user456/credits/purchase \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user456", "credits": 100}'

6. Check credit balance:
   curl http://localhost:8000/users/user456/credits

7. Execute query with credits:
   curl -X POST http://localhost:8000/api/query \
     -H "Content-Type: application/json" \
     -H "X-User-ID: user456" \
     -H "X-Tier-ID: payg" \
     -d '{"query": "SELECT * FROM orders"}'

8. Get usage statistics:
   curl http://localhost:8000/users/user123/usage/stats

9. Get usage history:
   curl http://localhost:8000/users/user123/usage/history
"""
