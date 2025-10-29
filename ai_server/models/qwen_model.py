import os
os.environ['HF_HOME'] = 'D:/huggingface_cache'
os.environ['TRANSFORMERS_CACHE'] = 'D:/huggingface_cache'

import torch
import requests
from PIL import Image
from io import BytesIO
from transformers import AutoTokenizer, AutoProcessor
from transformers import Qwen2VLForConditionalGeneration  # 모델 클래스
from qwen_vl_utils import process_vision_info

class QwenModel:
    def __init__(self, model_name="Qwen/Qwen2-VL-2B-Instruct", device="cpu"):
        self.device = device

         # D드라이브에 캐시 저장 설정
        import os
        os.environ['HF_HOME'] = 'D:/huggingface_cache'
        os.environ['TRANSFORMERS_CACHE'] = 'D:/huggingface_cache'

        # 1️⃣ 모델 로드
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float32, #cpu용
            #device_map="none"
        )
        self.model.eval()

        # 2️⃣ 프로세서 로드
        self.processor = AutoProcessor.from_pretrained(model_name)

    def _load_image_from_url(self, url): # 희재 재량
        """S3 URL에서 이미지 다운로드 후 PIL.Image로 반환"""
        response = requests.get(url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        return img

    def _prepare_input(self, inference_input):
        """단일 질문 Lava JSON → 모델 입력 tensor"""
        # 이미지 로드
        image = self._load_image_from_url(inference_input["image"]) 
        
        # 단일 human 질문만 추출
        text_input = inference_input["conversations"][0]["value"]
        
        # Qwen2-VL 형식으로 대화 구성
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": text_input.replace("<image>\n", "")}
                ]
            }
        ]
        
        # 채팅 템플릿 적용
        text_prompt = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        # vision_info 처리
        from qwen_vl_utils import process_vision_info
        image_inputs, video_inputs = process_vision_info(messages)
        
        # processor를 이용해 모델 입력 tensor 생성
        inputs = self.processor(
            text=[text_prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        )
        
        return inputs.to(self.device)

    def predict(self, inference_input, max_new_tokens=128):
        """단일 질문 Lava JSON → 모델 추론 → 텍스트 반환"""
        try:
            inputs = self._prepare_input(inference_input)
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

            # 입력 길이 제외
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]

            # 디코딩
            output_text = self.processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )

            return output_text

        except Exception as e:
            print(f"Prediction error: {e}")
            return [f"Error: {e}"]