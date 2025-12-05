from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ai_service import ai_service
from app.services.s3_service import s3_service
from app.services.chat_service import process_chat_with_db, save_message_to_db  # 추가
from supabase import create_client, Client
from PIL import Image
from io import BytesIO
import os
import logging  # 추가
from app.core.config import settings

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])
logger = logging.getLogger(__name__)  # 추가

# Supabase 클라이언트
def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Response 모델 추가
class ChatResponse(BaseModel):
    user_id: str
    prescription_id: Optional[int] = None
    user_message: str
    ai_response: str
    prescription_analysis: Optional[dict] = None


@router.post("/upload", response_model=ChatResponse)
async def upload_prescription(
    user_id: str = Form(...),
    query: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    supabase: Client = Depends(get_supabase)
):
    """
    통합 엔드포인트: 이미지 업로드 + 채팅
    
    3가지 케이스 처리:
    1) 텍스트만 전송
    2) 이미지 + 텍스트 전송
    3) 이미지만 전송 (기본 프롬프트 사용)
    """
    
    prescription_id = None
    prescription_analysis = None
    user_message = query
    
    # Case 1: 파일이 있는 경우 (이미지 업로드 + VL 분석)
    if file and file.filename:
        logger.info(f"📤 File upload detected: {file.filename}")
        
        try:
            # 1-1. 파일을 PIL.Image로 변환
            contents = await file.read()
            image = Image.open(BytesIO(contents)).convert("RGB")
            
            # 1-2. S3에 업로드
            await file.seek(0)
            upload_result = await s3_service.upload_prescription(file, user_id)
            
            # 1-3. Supabase DB에 저장 (analysis_status: pending)
            data = {
                "user_id": user_id,
                "file_url": upload_result['file_url'],
                "file_key": upload_result['file_key'],
                "original_filename": upload_result['original_filename'],
                "analysis_status": "pending"
            }
            
            result = supabase.table("prescriptions").insert(data).execute()
            prescription_id = result.data[0]['id']
            
            # 1-4. VL 모델로 처방전 분석
            # 이미지만 전송한 경우 기본 프롬프트 사용
            if not query or query.strip() == "":
                user_message = "这张处方上写了什么？"
                logger.info("📝 Using default prompt (image only)")
            
            vl_prompt = user_message
            
            try:
                ai_result = await ai_service.analyze_prescription(image, vl_prompt)
                prescription_analysis = ai_result
                
                # 분석 성공 시 DB 업데이트
                supabase.table("prescriptions").update({
                    "ai_analysis": ai_result,
                    "analysis_status": "completed"
                }).eq("id", prescription_id).execute()
                
                logger.info(f"✅ VL analysis completed for prescription {prescription_id}")
                
            except Exception as e:
                logger.error(f"❌ VL analysis failed: {e}")
                supabase.table("prescriptions").update({
                    "analysis_status": "failed"
                }).eq("id", prescription_id).execute()
                
                raise HTTPException(
                    status_code=500,
                    detail=f"처방전 분석 실패: {str(e)}"
                )
        
        except Exception as e:
            logger.error(f"❌ File upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"파일 업로드 실패: {str(e)}"
            )
    
    # Case 2: 텍스트만 있는 경우 (채팅만)
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
            user_id=user_id,
            prescription_id=prescription_id,
            message=user_message,
            sender_type="user"
        )
    except Exception as e:
        logger.error(f"사용자 메시지 저장 실패: {e}")
    
    # 공통: LangChain Agent 실행
    try:
        ai_response = process_chat_with_db(
            supabase=supabase,
            user_id=user_id,
            user_query=user_message,
            prescription_analysis=prescription_analysis
        )
        
        logger.info(f"🤖 LangChain response generated")
        
    except Exception as e:
        logger.error(f"❌ LangChain agent failed: {e}")
        ai_response = "죄송합니다. 응답 생성 중 오류가 발생했습니다."
    
    # 공통: AI 응답 DB 저장
    try:
        save_message_to_db(
            supabase=supabase,
            user_id=user_id,
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
        prescription_analysis=prescription_analysis
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