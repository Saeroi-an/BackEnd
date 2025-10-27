from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.services.s3_service import s3_service
from supabase import create_client, Client
import os
from typing import Optional
from app.core.config import settings

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


# Supabase 클라이언트 (의존성으로 사용)
def get_supabase() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


@router.post("/upload")
async def upload_prescription(
    file: UploadFile = File(...),
    user_id: Optional[str] = None,
    supabase: Client = Depends(get_supabase)
):
    """
    처방전 이미지 업로드
    
    - **file**: 업로드할 처방전 이미지 (jpg, jpeg, png, pdf)
    - **user_id**: 사용자 ID (옵션)
    """
    
    # S3에 업로드
    upload_result = await s3_service.upload_prescription(file, user_id)
    
    # Supabase DB에 저장
    try:
        data = {
            "user_id": user_id,
            "file_url": upload_result['file_url'],
            "file_key": upload_result['file_key'],
            "original_filename": upload_result['original_filename'],
        }
        
        result = supabase.table("prescriptions").insert(data).execute()
        
        return {
            "success": True,
            "message": "처방전이 성공적으로 업로드되었습니다.",
            "data": {
                "id": result.data[0]['id'],
                "file_url": upload_result['file_url'],
                "original_filename": upload_result['original_filename']
            }
        }
        
    except Exception as e:
        # DB 저장 실패 시 S3에서 파일 삭제 (롤백)
        s3_service.delete_prescription(upload_result['file_key'])
        raise HTTPException(
            status_code=500,
            detail=f"데이터베이스 저장 실패: {str(e)}"
        )


@router.get("/{prescription_id}")
async def get_prescription(
    prescription_id: int,
    supabase: Client = Depends(get_supabase)
):
    """처방전 정보 조회"""
    
    result = supabase.table("prescriptions").select("*").eq("id", prescription_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="처방전을 찾을 수 없습니다.")
    
    return {
        "success": True,
        "data": result.data[0]
    }


@router.get("/user/{user_id}")
async def get_user_prescriptions(
    user_id: str,
    supabase: Client = Depends(get_supabase)
):
    """사용자의 모든 처방전 조회"""
    
    result = supabase.table("prescriptions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    
    return {
        "success": True,
        "data": result.data,
        "count": len(result.data)
    }


@router.delete("/{prescription_id}")
async def delete_prescription(
    prescription_id: int,
    supabase: Client = Depends(get_supabase)
):
    """처방전 삭제"""
    
    # DB에서 파일 정보 조회
    result = supabase.table("prescriptions").select("file_key").eq("id", prescription_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="처방전을 찾을 수 없습니다.")
    
    file_key = result.data[0]['file_key']
    
    # S3에서 삭제
    s3_deleted = s3_service.delete_prescription(file_key)
    
    # DB에서 삭제
    supabase.table("prescriptions").delete().eq("id", prescription_id).execute()
    
    return {
        "success": True,
        "message": "처방전이 삭제되었습니다.",
        "s3_deleted": s3_deleted
    }


@router.get("/{prescription_id}/presigned-url")
async def get_presigned_url(
    prescription_id: int,
    expiration: int = 3600,
    supabase: Client = Depends(get_supabase)
):
    """
    처방전의 임시 접근 URL 생성 (보안이 필요한 경우)
    
    - **expiration**: URL 만료 시간(초), 기본 1시간
    """
    
    result = supabase.table("prescriptions").select("file_key").eq("id", prescription_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="처방전을 찾을 수 없습니다.")
    
    file_key = result.data[0]['file_key']
    presigned_url = s3_service.generate_presigned_url(file_key, expiration)
    
    if not presigned_url:
        raise HTTPException(status_code=500, detail="URL 생성에 실패했습니다.")
    
    return {
        "success": True,
        "presigned_url": presigned_url,
        "expires_in": expiration
    }
