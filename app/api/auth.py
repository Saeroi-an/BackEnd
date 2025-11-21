# app/api/auth.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
import httpx
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.services.auth_service import get_google_user_info, get_or_create_user
from app.models.user import UserResponse, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.get("/google/login")
async def google_login():
    """Google 로그인 페이지로 리다이렉트"""
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"prompt=select_account"
    )
    return RedirectResponse(url=google_auth_url)

@router.get("/google/callback")
async def google_callback(code: str = Query(...)):
    """Google OAuth 콜백 처리"""
    # 1. Authorization code로 access token 교환
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        
        token_data = token_response.json()
        google_access_token = token_data.get("access_token")
    
    # 2. Google 사용자 정보 가져오기
    google_user_data = await get_google_user_info(google_access_token)
    if not google_user_data:
        raise HTTPException(status_code=400, detail="Failed to get user info from Google")
    
    # 3. DB에서 사용자 조회 또는 생성
    user = get_or_create_user(google_user_data)
    
    # 4. JWT 토큰 생성
    access_token = create_access_token(data={
        "id": user.id,
        "email": user.email
    })
    refresh_token = create_refresh_token(data={
        "id": user.id
    })
    
    # 5. 응답 반환: 프론트엔드로 리다이렉트 (쿼리 파라미터로 토큰 전달)
    from urllib.parse import urlencode, quote
    from fastapi.responses import RedirectResponse

    # ⭐ 사용자 정보도 함께 전달
    params = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user_id': str(user.id),
        'user_name': user.name,
        'user_email': user.email
    }

    redirect_url = f"{settings.FRONTEND_URL}?access_token={access_token}&refresh_token={refresh_token}"
    return RedirectResponse(url=redirect_url)