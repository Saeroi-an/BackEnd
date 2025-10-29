from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional 
from jose import JWTError, jwt
from app.core.config import settings

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Access Token 생성"""
    to_encode = data.copy() # 원본 데이터 복사 (원본 수정 방지)
    
    # 만료 시간 설정
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # 기본값: 30분 (설정 파일에서 가져옴)
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # payload에 만료시간과 토큰 타입 추가
    to_encode.update({"exp": expire, "type": "access"})
    # JWT 토큰 생성 (secret key로 서명)
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    """Refresh Token 생성"""
    to_encode = data.copy()
    # 만료 시간: 7일 (설정 파일에서 가져옴)
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    # payload에 만료시간과 토큰 타입 추가
    to_encode.update({"exp": expire, "type": "refresh"})
    # JWT 토큰 생성
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str, token_type: str = "access"):
    """토큰 검증 및 payload 반환"""
    try:
        # 토큰 디코딩 (서명 검증 + 만료시간 확인)
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        
        # 토큰 타입 확인 (access인지 refresh인지)
        if payload.get("type") != token_type:
            return None
            
        # 검증 성공: payload 반환
        return payload
    except JWTError:
        # 토큰이 유효하지 않거나 만료됨
        return None

# HTTP Bearer 토큰 스키마 (헤더에서 토큰 추출)
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """JWT 토큰에서 현재 사용자 정보 추출"""
    
    token = credentials.credentials
    
    # 토큰 검증
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # payload에서 사용자 정보 반환
    return payload