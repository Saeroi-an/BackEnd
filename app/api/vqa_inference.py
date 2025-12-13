# app/api/vqa_inference.py
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class VQAInput(BaseModel):
    image_path: str
    question: str
    prescription_id: int

# 전역 변수
model = None
processor = None
device = "cuda" if torch.cuda.is_available() else "cpu"

def load_model_if_needed():
    """첫 요청 시 모델을 로드합니다 (Lazy Loading)"""
    global model, processor
    if model is not None:
        return
    
    model_name = "Rfy23/qwen2vl-ko-zh"
    print("🚀 Qwen2VL 모델 로드 시작...")
    try:
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None
        ).eval()
        processor = AutoProcessor.from_pretrained(model_name)
        print("✅ 모델 및 프로세서 로드 완료!")
    except Exception as e:
        print(f"❌ 모델 로드 오류: {e}")
        raise

@router.post("/vqa_inference")
async def vqa_inference_endpoint(input_data: VQAInput):
    """VQA 추론 엔드포인트: 이미지 경로와 질문을 받아 Qwen2VL 모델로 분석"""
    load_model_if_needed()
    
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="VQA 모델이 아직 로드되지 않았습니다.")
    
    image_url = input_data.image_path
    question = input_data.question
    
    try:
        # 1. 메시지 구성
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_url},
                    {"type": "text", "text": f"<image>\n{question}"}
                ],
            }
        ]
        
        # 2. 입력 텐서 준비
        print("입력 텐서 준비 중...")
        text_input = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, _ = process_vision_info(messages)
        inputs = processor(
            text=[text_input],
            images=image_inputs,
            padding=True,
            return_tensors="pt"
        ).to(device)
        
        # 3. 모델 추론
        print("모델 추론 시작...")
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=280)
        
        # 4. 디코딩
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        
        # 5. 결과 반환
        inference_result = f"처방 ID {input_data.prescription_id}에 대한 추론 출력: \n {output_text[0]}"
        
        print(f"✅ VQA 추론 완료 - 처방 ID: {input_data.prescription_id}")
        return {"prescription_id": input_data.prescription_id, "inference_result": inference_result}
        
    except Exception as e:
        print(f"❌ 추론 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"VQA 추론 중 오류 발생: {e}")