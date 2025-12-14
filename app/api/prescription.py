# app/api/prescription.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
# from app.services.ai_service import ai_service
from app.services.s3_service import s3_service
from app.services.chat_service import process_chat_with_db, save_message_to_db
from supabase import create_client, Client
# from PIL import Image
# from io import BytesIO
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
    prescription_analysis: Optional[str] = None

@router.post("/upload", response_model=ChatResponse)
async def upload_prescription(
    current_user: dict = Depends(get_current_user),
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    supabase: Client = Depends(get_supabase)
):
    """통합 엔드포인트: 이미지 업로드 + 채팅"""
    user_id = current_user["id"]
    prescription_id = None
    user_message = query
    # prescription_analysis_result = None
    
    # Case 1: 파일이 있는 경우
    if file and file.filename:
        logger.info(f"📤 File upload detected: {file.filename}")
        
        try:
            # 1-2. S3에 업로드
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
            
            logger.info(f"🖼️ Image uploaded: prescription_id={prescription_id}")
            
        except Exception as e:
            logger.error(f"❌ File upload failed: {e}")
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
    
    
    # 공통: Agent 실행
    try:
        # prescription_id를 Agent에 전달
        if prescription_id:
            # 이미지가 있는 경우: prescription_id와 함께 질문 전달
            enhanced_query = f"prescription_id: {prescription_id}\n사용자 질문: {user_message}"
            logger.info(f"🖼️ Calling Agent with prescription_id={prescription_id}")
        else:
            # 텍스트만 있는 경우
            enhanced_query = user_message
            logger.info(f"💬 Calling Agent (text only)")
        
        # Agent 실행
        ai_response = process_chat_with_db( # supabase는 이미 과거 기록 + 신규 query
            supabase=supabase,
            user_id=str(user_id),
            user_query=enhanced_query,
            # prescription_analysis=None  # 더 이상 전달 안 함
        )
        
        logger.info(f"✅ Agent response generated")
    
        # 👇 추가: prescription이 있고 아직 pending 상태면 "completed"로 변경
        if prescription_id:
            try:
                # 현재 상태 확인
                current = supabase.table("prescriptions").select("analysis_status").eq(
                    "id", prescription_id
                ).execute()
                
                # pending 상태면 completed로 업데이트
                if current.data and current.data[0]['analysis_status'] == 'pending':
                    supabase.table("prescriptions").update({
                        "analysis_status": "completed"
                    }).eq("id", prescription_id).execute()
                    logger.info(f"💾 Prescription status updated: completed")
            except Exception as e:
                logger.error(f"Status update failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Agent execution failed: {e}")
        import traceback
        traceback.print_exc()
        
        ai_response = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
        
        # 에러 발생 시 prescription 상태 업데이트
        if prescription_id:
            try:
                supabase.table("prescriptions").update({
                    "analysis_status": "failed"
                }).eq("id", prescription_id).execute()
            except:
                pass
    
    # 공통: 채팅 로그 DB 저장 (✅ invoke 이후 저장: 히스토리와 신규쿼리 분리 유지)
    try:
        # 1) 사용자 메시지 저장 (DB에는 “사용자 발화”만 저장)
        # - user_message: 실제 사용자가 입력한 query (또는 기본 프롬프트로 설정된 문장)
        # - prescription_id: 이미지 업로드 케이스면 연결해서 저장, 텍스트만이면 None
        save_message_to_db(
            supabase=supabase,
            user_id=str(user_id),
            prescription_id=prescription_id,
            message=user_message,
            sender_type="user"
        )

        # 2) AI 응답 저장
        save_message_to_db(
            supabase=supabase,
            user_id=str(user_id),
            prescription_id=prescription_id,
            message=ai_response,
            sender_type="ai"
        )

    except Exception as e:
        logger.error(f"채팅 저장 실패: {e}")

    
    # 최종 응답 반환
    return ChatResponse(
        user_id=user_id,
        prescription_id=prescription_id,
        user_message=user_message, # 신규 query
        ai_response=ai_response, # 반환해야하는 값
        # prescription_analysis=None
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
    
    # Agent 실행 # ✅ check
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