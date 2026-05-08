"""认证 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
import bcrypt
import uuid

from app.config import get_settings
from app.db.postgres import Database

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    userName: str
    email: str
    password: str


class UserResponse(BaseModel):
    userId: str
    userName: str
    email: str
    profilePicture: str | None = None


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.secret_key or "dev-secret-key", algorithm=settings.algorithm)


@router.post("/login")
async def login(request: LoginRequest):
    """用户登录"""
    settings = get_settings()

    # Find user by email
    user = await Database.fetchrow(
        "SELECT * FROM users WHERE email = $1 AND is_active = TRUE",
        request.email
    )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    password_bytes = request.password.encode('utf-8')
    hash_bytes = user['password_hash'].encode('utf-8') if isinstance(user['password_hash'], str) else user['password_hash']

    if not bcrypt.checkpw(password_bytes, hash_bytes):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate token
    token = create_access_token(user['user_id'])

    return {
        "success": True,
        "data": {
            "token": token,
            "user": {
                "userId": user['user_id'],
                "userName": user['user_name'],
                "email": user['email'],
                "profilePicture": user.get('profile_picture')
            }
        }
    }


@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册"""
    settings = get_settings()

    # Check if email already exists
    existing = await Database.fetchrow(
        "SELECT * FROM users WHERE email = $1",
        request.email
    )

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    user_id = str(uuid.uuid4())
    password = request.password.encode('utf-8')
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password, salt).decode('utf-8')

    await Database.execute("""
        INSERT INTO users (user_id, user_name, email, password_hash)
        VALUES ($1, $2, $3, $4)
    """, user_id, request.userName, request.email, password_hash)

    # Generate token
    token = create_access_token(user_id)

    return {
        "success": True,
        "data": {
            "token": token,
            "user": {
                "userId": user_id,
                "userName": request.userName,
                "email": request.email,
                "profilePicture": None
            }
        }
    }


@router.get("/me")
async def get_me(authorization: str = None):
    """获取当前用户信息"""
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, settings.secret_key or "dev-secret-key", algorithms=[settings.algorithm])
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user from database
    user = await Database.fetchrow(
        "SELECT * FROM users WHERE user_id = $1 AND is_active = TRUE",
        user_id
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "userId": user['user_id'],
            "userName": user['user_name'],
            "email": user['email'],
            "profilePicture": user.get('profile_picture')
        }
    }
