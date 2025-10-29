# app/services/ai_service.py
import requests
import httpx
import os
from typing import Optional

class AIService:
    def __init__(self):
        self.ai_server_url = os.getenv("AI_SERVER_URL", "http://localhost:5000")
    
    async def analyze_prescription(self, image_url: str, prompt: Optional[str] = None) -> dict:
        """
        Flask AI 서버에 처방전 이미지 분석 요청
        
        Args:
            image_url: S3에 업로드된 이미지 URL
            prompt: 분석 프롬프트 (기본값: 중국어 질문)
        
        Returns:
            AI 분석 결과 dict
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ai_server_url}/predict",
                    json={
                        "image": image_url,
                        "text": prompt
                    }
                )
                response.raise_for_status()
                return response.json()
        
        except httpx.TimeoutException:
            raise Exception("AI 서버 응답 시간 초과")
        except httpx.HTTPError as e:
            raise Exception(f"AI 서버 요청 실패: {str(e)}")
        except Exception as e:
            raise Exception(f"AI 분석 중 오류 발생: {str(e)}")

# 싱글톤 인스턴스
ai_service = AIService()
