# app/services/ai_service.py
import requests
from app.core.config import settings

async def ask_ai(image, question: str):
    """
    FE에서 전달된 이미지+질문을 AI 서버로 전송 → 답변 반환
    """
    files = {"image": (image.filename, image.file, image.content_type)}
    data = {"question": question}

    res = requests.post(f"{settings.AI_SERVER_URL}/predict", files=files, data=data)
    if res.status_code != 200:
        return "AI 서버 오류 발생"

    return res.json().get("answer")
