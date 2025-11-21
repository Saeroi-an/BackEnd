# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import UserProfileUpdate, UserResponse
from app.services.user_service import update_user_profile #get_user_by_id
from app.core.security import get_current_user
from app.core.database import get_supabase

router = APIRouter(prefix="/users", tags=["users"])

# 🆕 사용자 정보 조회 엔드포인트 추가
@router.get("/me/profile", response_model=UserResponse)
async def getMyProfile(
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase)
):
    """현재 로그인한 사용자의 정보 조회"""
    
    user_id = current_user["id"]
    
    # Supabase에서 사용자 정보 조회
    response = supabase.table("users").select("*").eq("id", user_id).single().execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )
    
    return response.data

@router.patch("/me/profile", response_model=UserResponse)
async def updateMyProfile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase)
):
    """현재 로그인한 사용자의 기본정보 업데이트"""
    
    user_id = current_user["id"]
    
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