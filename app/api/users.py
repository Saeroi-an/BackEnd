# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import UserProfileUpdate, UserResponse
from app.services.user_service import update_user_profile
from app.core.security import get_current_user
from app.core.database import get_supabase

router = APIRouter(prefix="/users", tags=["users"])

@router.patch("/me/profile", response_model=UserResponse)
async def updateMyProfile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase)
):
    """현재 로그인한 사용자의 기본정보 업데이트"""
    
    user_id = current_user["id"]  # 정수 그대로 사용
    
    updated_user = await update_user_profile(
        supabase=supabase,
        user_id=user_id,
        profile_data=profile_data
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="프로필 업데이트 실패"
        )
    
    return updated_user