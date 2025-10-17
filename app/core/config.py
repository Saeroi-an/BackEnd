# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AI_SERVER_URL: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_BUCKET_NAME: str
    AWS_REGION: str

    class Config:
        env_file = ".env"

settings = Settings()
