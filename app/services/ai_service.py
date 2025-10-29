# app/services/ai_service.py
import os
from dotenv import load_dotenv
from AImodels.qwen_model import QwenModel
from typing import Optional

# .env 로드
load_dotenv()
hf_token = os.getenv("HUGGINGFACE_TOKEN")

class AIService:
    def __init__(self):
        # 모델 인스턴스 한 번만 생성
        self.qwen_model = QwenModel(hf_token=hf_token)

    async def analyze_prescription(self, image_url: str, prompt: Optional[str] = None) -> str: # TODO: URL 인자 변경
        """
        처방전 이미지 분석 (단일 질문)
        
        Args:
            image_url: S3에 업로드된 이미지 URL
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
                    {"type": "image", "image": image_url}, # TODO: URL 변경
                    {"type": "text", "text": f"<image>\n{prompt}"} 
                ]
            }
        ]
        

        try:
            output_text_list = self.qwen_model.predict(messages)
            # predict 함수가 리스트 반환하므로 첫 번째 문자열 사용
            return output_text_list[0] if output_text_list else ""
        except Exception as e:
            raise Exception(f"AI 분석 중 오류 발생: {str(e)}")

# 싱글톤 인스턴스
ai_service = AIService()
