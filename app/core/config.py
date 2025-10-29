# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ============================================
    # Database
    # ============================================
    DATABASE_URL: str
    
    # ============================================
    # Supabase (선택사항)
    # ============================================
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # ============================================
    # AWS S3 (나중에 설정)
    # ============================================
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_BUCKET_NAME: str
    AWS_REGION: str = "ap-northeast-2"
    S3_PRESCRIPTION_FOLDER: str = "prescriptions/"

    # ============================================
    # Google OAuth  # <- 새로 추가
    # ============================================
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    
    # ============================================
    # JWT  # <- 새로 추가
    # ============================================
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ============================================
    # AI Server
    # ============================================
    AI_SERVER_URL: str = "http://localhost:8001"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = 'utf-8'
        extra = "allow"

# @lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
