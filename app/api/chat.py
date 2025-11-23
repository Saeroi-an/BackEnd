# app/api/chat.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client
from app.api.prescription import get_supabase
from app.services.ai_service import ai_service
import requests
from PIL import Image
from io import BytesIO

router = APIRouter(prefix="/chats", tags=["chats"])

class ChatMessage(BaseModel):
    message: str
    prescription_id: int

@router.post("/send")
async def send_message(
    chat_message: ChatMessage,
    user_id: str = Query(...),
    supabase: Client = Depends(get_supabase)
):
    """처방전에 대한 채팅 메시지 전송"""
    
    prescription_id = chat_message.prescription_id
    
    # 1. 처방전 존재 여부 및 분석 상태 확인
    prescription_result = supabase.table("prescriptions").select(
        "id, ai_analysis, analysis_status, file_url"
    ).eq("id", prescription_id).execute()
    
    if not prescription_result.data:
        raise HTTPException(status_code=404, detail="처방전을 찾을 수 없습니다.")
    
    prescription = prescription_result.data[0]
    
    if prescription['analysis_status'] != 'completed':
        raise HTTPException(status_code=400, detail="처방전 분석이 완료되지 않았습니다.")
    
    try:
        # 2. 사용자 메시지 저장
        user_message_data = {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "message": chat_message.message,
            "sender_type": "user"
        }
        
        user_msg_result = supabase.table("prescription_chats").insert(user_message_data).execute()
        
        # 3. AI 응답 생성
        image_response = requests.get(prescription['file_url'])
        image = Image.open(BytesIO(image_response.content)).convert("RGB")
        
        # AI 프롬프트 (중국어로)
        ai_prompt = f"以下是韩语处方\n{chat_message.message}"
        
        ai_response = await ai_service.analyze_prescription(image, ai_prompt)
        
        # 4. AI 응답 저장
        ai_message_data = {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "message": ai_response,
            "sender_type": "ai"
        }
        
        ai_msg_result = supabase.table("prescription_chats").insert(ai_message_data).execute()
        
        return {
            "success": True,
            "user_message": user_msg_result.data[0],
            "ai_response": ai_msg_result.data[0]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"채팅 처리 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/messages/{prescription_id}")
async def get_messages(
    prescription_id: int,
    user_id: str = Query(...),
    supabase: Client = Depends(get_supabase)
):
    """처방전의 모든 채팅 메시지 조회"""
    
    result = supabase.table("prescription_chats").select("*").eq(
        "prescription_id", prescription_id
    ).eq("user_id", user_id).order("created_at").execute()
    
    return {
        "success": True,
        "messages": result.data
    }