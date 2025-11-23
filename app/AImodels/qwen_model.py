import os
#가상환경 내부에 캐시 저장
os.environ['HF_HOME'] = '/home/ubuntu/BackEnd/hf_cache'
os.environ['TRANSFORMERS_CACHE'] = '/home/ubuntu/BackEnd/hf_cache'
os.environ['HF_HUB_CACHE'] = 'home/ubuntu/Backend/hf_cache'

import torch
import requests
from PIL import Image
from io import BytesIO
from transformers import AutoTokenizer, AutoProcessor
from transformers import Qwen2VLForConditionalGeneration  # 모델 클래스
from qwen_vl_utils import process_vision_info

class QwenModel:
    
    
    def __init__(self, model_name="Rfy23/qwen2vl-ko-zh", device=None): 
        
        # 환경에 따라 device 자동 선택
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        print(f"디바이스 종류: {self.device}")

        print("모델 로드 중...")
        # 1️⃣ 모델 로드 수정
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device=="cuda" else torch.float32,
            device_map="auto" if self.device=="cuda" else None
        )
        self.model.eval()
        print("모델 로드 완료!")
        
        
        # 2️⃣ 프로세서 로드
        self.processor = AutoProcessor.from_pretrained(model_name)
        print("프로세서 로드 완료!")
        
    # 삭제    
    # def _load_image_from_url(self, url): 
    #     """S3 URL에서 이미지 다운로드 후 PIL.Image로 반환"""
    #     response = requests.get(url)
    #     response.raise_for_status()
    #     img = Image.open(BytesIO(response.content)).convert("RGB")
    #     return img

    def _prepare_inputs_from_messages(self, messages):
        """
            messages 리스트를 모델 입력 텐서로 변환.

            Args:
                messages (list): 이미지(PIL.Image)와 텍스트를 포함한 메시지 리스트.
                                [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "image", "image": PIL.Image 객체},
                                            {"type": "text", "text": "질문 텍스트"}
                                        ]
                                    }
                                ]

            Returns:
                torch.Tensor: 모델에 입력 가능한 텐서, device(self.device)에 맞게 이동됨.
        """
        
        print("입력 텐서 준비 중...")
        text_input = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, _ = process_vision_info(messages)

        inputs = self.processor(
            text=[text_input],
            images=image_inputs,
            padding=True,
            return_tensors="pt"
        ).to(self.device)
        return inputs
    

    def predict(self, messages, max_new_tokens=128):
        """인자로 넘어온 messages의 image는 url이면 안됨."""
        try:
            inputs = self._prepare_inputs_from_messages(messages)
            print("입력 텐서 준비 완료!")
            
            print("모델 추론 시작...")
            with torch.no_grad():
                generated_ids = self.model.generate(**inputs, max_new_tokens=128)

                generated_ids_trimmed = [
                    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]

                print("디코딩 중...")

                # 디코딩
                output_text = self.processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )

            return output_text

        except Exception as e:
            print(f"Prediction error: {e}")
            return [f"Error: {e}"]
