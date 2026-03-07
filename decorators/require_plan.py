from fastapi import HTTPException
from enums.plan_enum import UserPlan

def require_plan(required: UserPlan):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user = kwargs.get("current_user")

            if not user:
                raise HTTPException(status_code=401, detail="User missing")

            # Convert to enum
            user_plan = UserPlan(user.plan)

            # Check order of plans
            plan_rank = {
                UserPlan.ESSENTIAL: 1,
                UserPlan.PRO: 2,
                UserPlan.ULTIMATE: 3
            }

            if plan_rank[user_plan] < plan_rank[required]:
                raise HTTPException(
                    status_code=403,
                    detail=f"Votre plan ne permet pas d'accéder à cette fonctionnalité ({required})."
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
