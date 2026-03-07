from pydantic import BaseModel, EmailStr


# ==========================================
# ✔️ REGISTER
# ==========================================
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


# ==========================================
# ✔️ LOGIN
# ==========================================
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ==========================================
# ✔️ TOKEN
# ==========================================
class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ==========================================
# ✔️ USER RESPONSE
# ==========================================
class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    plan_id: int

    class Config:
        from_attributes = True
