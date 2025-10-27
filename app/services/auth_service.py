# app/services/auth_service.py
import httpx
from supabase import create_client, Client
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import UserCreate, UserInDB
from typing import Optional

# Supabase 클라이언트 초기화
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# ============================================
# 기존 이메일/비밀번호 로그인 (유지)
# ============================================
def sign_in(email, password):
    """이메일/비밀번호 로그인"""
    user = supabase.auth.sign_in_with_password({"email": email, "password": password})
    return user

def sign_up(email, password):
    """이메일/비밀번호 회원가입"""
    user = supabase.auth.sign_up({"email": email, "password": password})
    return user

# ============================================
# Google OAuth 로그인 (새로 추가)
# ============================================
async def get_google_user_info(access_token: str) -> Optional[dict]:
    """Google OAuth access token으로 사용자 정보 가져오기"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code == 200:
            return response.json()
        return None

def get_or_create_user(google_user_data: dict) -> UserInDB:
    """Google 사용자 정보로 DB에서 조회 또는 생성"""
    google_id = google_user_data.get("id")
    email = google_user_data.get("email")
    
    # 기존 사용자 조회
    result = supabase.table("users").select("*").eq("google_id", google_id).execute()
    
    if result.data:
        # 기존 사용자 반환
        return UserInDB(**result.data[0])
    
    # 신규 사용자 생성
    new_user = UserCreate(
        email=email,
        name=google_user_data.get("name"),
        picture=google_user_data.get("picture"),
        google_id=google_id
    )
    
    insert_result = supabase.table("users").insert(new_user.model_dump()).execute()
    return UserInDB(**insert_result.data[0])