from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from ...api.core.config import settings
from .models import TokenData, User, UserInDB

# OAuth2 的password bearer设置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def verify_password(plain_password, hashed_password):
    """验证密码"""
    # 简单实现，实际项目中应使用安全的哈希函数
    return plain_password == hashed_password

def get_user(username: str):
    """获取用户"""
    # 硬编码的管理员用户，实际项目应从数据库中获取
    if username == "admin":
        return UserInDB(
            username=username,
            hashed_password="admin",  # 实际项目中应存储哈希密码
            disabled=False
        )
    return None

def authenticate_user(username: str, password: str):
    """验证用户"""
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    """创建访问令牌"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=15)
    return _create_token(data, expires_delta, token_type="access")

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    """创建刷新令牌"""
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(data, expires_delta, token_type="refresh")

def _create_token(data: dict, expires_delta: timedelta, token_type: str):
    """创建JWT令牌"""
    to_encode = data.copy()
    to_encode["type"] = token_type
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise credentials_exception
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """获取当前活跃用户"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user
