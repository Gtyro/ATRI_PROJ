from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """令牌数据模型"""
    username: Optional[str] = None

class User(BaseModel):
    """用户模型"""
    username: str
    disabled: Optional[bool] = None

class UserInDB(User):
    """数据库中的用户模型"""
    hashed_password: str
