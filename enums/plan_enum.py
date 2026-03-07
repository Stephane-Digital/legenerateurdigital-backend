from enum import Enum

class UserPlan(str, Enum):
    ESSENTIAL = "essential"
    PRO = "pro"
    ULTIMATE = "ultimate"
