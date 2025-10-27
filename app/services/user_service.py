# app/services/user_service.py
from supabase import Client
from app.models.user import UserProfileUpdate, UserResponse
from datetime import datetime
from typing import Optional

async def update_user_profile(
    supabase: Client,
    user_id: int,
    profile_data: UserProfileUpdate
) -> Optional[UserResponse]:
    """사용자 기본정보 업데이트"""
    
    # 업데이트할 데이터 준비 (None이 아닌 값만)
    update_data = profile_data.model_dump(exclude_unset=True)
    
    if not update_data:
        return None
    
    # updated_at 자동 갱신
    update_data["updated_at"] = datetime.utcnow().isoformat()
    
    # Supabase 업데이트 실행
    response = supabase.table("users").update(update_data).eq("id", user_id).execute()
    
    if response.data:
        return UserResponse(**response.data[0])
    
    return None