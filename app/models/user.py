#app/models/user.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """사용자 기본 정보"""
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None  # Google 프로필 이미지

class UserCreate(UserBase):
    """사용자 생성 시 필요한 정보"""
    google_id: str  # Google 고유 ID

class UserInDB(UserBase):
    """DB에 저장된 사용자 정보"""
    id: int
    google_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # ORM 모델과 호환

class UserProfileUpdate(BaseModel):
    """사용자 기본정보 업데이트 요청"""
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    birth_year: Optional[int] = Field(None, ge=1900, le=2024)
    birth_month: Optional[int] = Field(None, ge=1, le=12)
    birth_day: Optional[int] = Field(None, ge=1, le=31)
    height: Optional[float] = Field(None, gt=0, le=300)
    weight: Optional[float] = Field(None, gt=0, le=500)

class UserResponse(BaseModel):
    """API 응답용 사용자 정보"""
    id: int
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    birth_month: Optional[int] = None
    birth_day: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None

class TokenResponse(BaseModel):
    """로그인 성공 시 토큰 응답"""
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse