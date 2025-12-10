# app/api/prescription.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ai_service import ai_service
from app.services.s3_service import s3_service
from app.services.chat_service import process_chat_with_db, save_message_to_db
from supabase import create_client, Client
from PIL import Image
from io import BytesIO
import os
import logging
from app.core.config import settings
from app.core.security import get_current_user

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])
logger = logging.getLogger(__name__)

# Supabase 클라이언트
def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Response 모델
class ChatResponse(BaseModel):
    user_id: int
    prescription_id: Optional[int] = None
    user_message: str
    ai_response: str
    prescription_analysis: Optional[str] = None  # 👈 dict → str

@router.post("/upload", response_model=ChatResponse)
async def upload_prescription(
    current_user: dict = Depends(get_current_user),
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    supabase: Client = Depends(get_supabase)
):
    """
    통합 엔드포인트: 이미지 업로드 + 채팅
    """
    user_id = current_user["id"]
    prescription_id = None
    user_message = query
    prescription_analysis_result = None
    
    # Case 1: 파일이 있는 경우
    if file and file.filename:
        logger.info(f"📤 File upload detected: {file.filename}")
        
        try:
            # 1-1. 파일을 PIL.Image로 변환
            contents = await file.read()
            image = Image.open(BytesIO(contents)).convert("RGB")
            
            # 1-2. S3에 업로드
            await file.seek(0)
            upload_result = await s3_service.upload_prescription(file, user_id)
            
            # 1-3. Supabase DB에 저장
            data = {
                "user_id": user_id,
                "file_url": upload_result['file_url'],
                "file_key": upload_result['file_key'],
                "original_filename": upload_result['original_filename'],
                "analysis_status": "pending"
            }
            
            result = supabase.table("prescriptions").insert(data).execute()
            logger.info(f"✅ Prescription saved to DB: {result.data}")
            prescription_id = result.data[0]['id']
            
            # 1-4. 기본 프롬프트 설정
            if not query or query.strip() == "":
                user_message = "这张处方上写了什么？"
                logger.info("📝 Using default prompt (image only)")
            
            # 1-5. VL 모델 직접 실행
            logger.info(f"🔍 Running VL model analysis...")
            prescription_analysis_result = await ai_service.analyze_prescription(
                image=image,
                prompt=user_message
            )
            logger.info(f"✅ VL analysis completed: {prescription_analysis_result[:100]}...")
            
            # 1-6. DB 업데이트
            supabase.table("prescriptions").update({
                "ai_analysis": prescription_analysis_result,
                "analysis_status": "completed"
            }).eq("id", prescription_id).execute()
            
            logger.info(f"🖼️ Image analyzed: prescription_id={prescription_id}")
            
        except Exception as e:
            logger.error(f"❌ File upload/analysis failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"파일 처리 실패: {str(e)}"
            )
    
    # Case 2: 텍스트만 있는 경우
    else:
        if not query or query.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="텍스트 또는 이미지 중 하나는 필수입니다."
            )
        logger.info(f"💬 Text-only query received")
    
    # 공통: 사용자 메시지 DB 저장
    try:
        save_message_to_db(
            supabase=supabase,
            user_id=str(user_id),
            prescription_id=prescription_id,
            message=user_message,
            sender_type="user"
        )
    except Exception as e:
        logger.error(f"사용자 메시지 저장 실패: {e}")
    
    # 공통: Agent 실행 (분석 결과 포함)
    try:
        ai_response = process_chat_with_db(
            supabase=supabase,
            user_id=str(user_id),
            user_query=user_message,
            prescription_analysis=prescription_analysis_result
        )
        
        logger.info(f"🤖 LangChain response generated")
        
    except Exception as e:
        logger.error(f"❌ LangChain agent failed: {e}")
        import traceback
        traceback.print_exc()
        
        # 에러 시 분석 결과라도 반환
        if prescription_analysis_result:
            ai_response = prescription_analysis_result
        else:
            ai_response = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        
        # 에러 발생 시 prescription 상태 업데이트
        if prescription_id:
            try:
                supabase.table("prescriptions").update({
                    "analysis_status": "failed"
                }).eq("id", prescription_id).execute()
            except:
                pass
    
    # 공통: AI 응답 DB 저장
    try:
        save_message_to_db(
            supabase=supabase,
            user_id=str(user_id),
            prescription_id=prescription_id,
            message=ai_response,
            sender_type="ai"
        )
    except Exception as e:
        logger.error(f"AI 응답 저장 실패: {e}")
    
    # 최종 응답 반환
    return ChatResponse(
        user_id=user_id,
        prescription_id=prescription_id,
        user_message=user_message,
        ai_response=ai_response,
        prescription_analysis=prescription_analysis_result
    )

@router.get("/{prescription_id}")
async def get_prescription(
    prescription_id: int,
    current_user: dict = Depends(get_current_user),
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
    result = supabase.table("prescriptions").select("file_key").eq("id", prescription_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="처방전을 찾을 수 없습니다.")
    
    file_key = result.data[0]['file_key']
    s3_deleted = s3_service.delete_prescription(file_key)
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
    """처방전의 임시 접근 URL 생성"""
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

@router.get("/{prescription_id}/analysis")
async def get_prescription_analysis(
    prescription_id: int,
    supabase: Client = Depends(get_supabase)
):
    """처방전 분석 결과 조회"""
    result = supabase.table("prescriptions").select(
        "id, ai_analysis, analysis_status, created_at, original_filename"
    ).eq("id", prescription_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="처방전을 찾을 수 없습니다.")
    
    prescription = result.data[0]
    
    return {
        "success": True,
        "data": {
            "prescription_id": prescription['id'],
            "analysis_status": prescription['analysis_status'],
            "ai_analysis": prescription['ai_analysis'],
            "original_filename": prescription['original_filename'],
            "created_at": prescription['created_at']
        }
    }

@router.post("/chat")
async def chat_with_prescription(
    request: dict,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """텍스트 채팅 엔드포인트"""
    user_message = request.get("message", "")
    user_id = current_user["id"]
    
    # Agent 실행
    ai_response = process_chat_with_db(
        supabase=supabase,
        user_id=str(user_id),
        user_query=user_message,
        prescription_analysis=None
    )
    
    # 메시지 DB 저장
    save_message_to_db(supabase, str(user_id), None, user_message, "user")
    save_message_to_db(supabase, str(user_id), None, ai_response, "ai")
    
    return {
        "ai_response": ai_response
    }