# app/services/ai_service.py
import os
from PIL import Image
from dotenv import load_dotenv
from app.AImodels.qwen_model import QwenModel
from typing import Optional

# .env 로드
load_dotenv()
hf_token = os.getenv("HUGGINGFACE_TOKEN")

class AIService:
    def __init__(self):
        # temptext="백엔드 끔. 임시"
        
        # 모델 인스턴스 한 번만 생성
        self.qwen_model = QwenModel()

    async def analyze_prescription(self, image: Image.Image, prompt: Optional[str] = None) -> str:
        """
        처방전 이미지 분석
        
        Args:
            image: PIL.Image 객체
            prompt: 분석 프롬프트 (기본값: 중국어 질문)
        
        Returns:
            str: 모델 예측 텍스트
        """
        if prompt is None:
            prompt = "这张处方上写了什么？"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": f"<image>\n{prompt}"} 
                ]
            }
        ]
        
        try:
            output_text_list = self.qwen_model.predict(messages)
            return output_text_list[0] if output_text_list else ""
        except Exception as e:
            raise Exception(f"AI 분석 중 오류 발생: {str(e)}")
    
        return temptext

# 싱글톤 인스턴스
ai_service = AIService()