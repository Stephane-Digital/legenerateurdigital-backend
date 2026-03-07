import os
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext


# =====================================================
# 🔐 CONFIGURATION JWT
# =====================================================
SECRET_KEY = os.getenv("SECRET_KEY", "changeme-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 jours


# =====================================================
# 🔑 PASSWORD HASHING (bcrypt)
# =====================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash le mot de passe."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si le mot de passe correspond."""
    return pwd_context.verify(plain_password, hashed_password)


# =====================================================
# 🔏 JWT TOKEN CREATION
# =====================================================
def create_access_token(data: dict):
    """Crée un token JWT."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
