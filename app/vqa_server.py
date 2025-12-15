import gc
import os
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info # 실제 사용 시 임포트 필요

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ------------------------------
# 1. FastAPI 설정
# ------------------------------
app = FastAPI()

# Pydantic 모델: 입력 데이터 유효성 검사 (LangChain JS/TS 스키마와 일치해야 함)
class VQAInput(BaseModel):
    image_path: str
    question: str
    prescription_id: int

# ------------------------------
# 2. 모델 전역 로드 (앱 시작 시 한 번만)
# ------------------------------
model = None
processor = None
device = "cuda" if torch.cuda.is_available() else "cpu"

@app.on_event("startup")
async def load_vqa_model():
    """서버 시작 시 Qwen2VL 모델을 메모리에 로드"""
    global model, processor
    model_name = "Rfy23/qwenvl-7B-medical-ko-zh"
    
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
        # 실제 환경에서는 로드 실패 시 서버를 종료해야 할 수 있습니다.

# ------------------------------
# 3. VQA 추론 API 엔드포인트
# ------------------------------
@app.post("/api/vqa_inference")
async def vqa_inference_endpoint(input_data: VQAInput):
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="VQA 모델이 아직 로드되지 않았습니다.")
    
    # LangChain Tool에서 받은 인수를 사용합니다.
    image_url = input_data.image_path
    question = input_data.question

    # 요청 로깅
    print(f"📥 받은 질문: {question}")
    
    # **여기에 사용자님의 Qwen2VL 추론 로직을 넣습니다.**
    # (messages, processor.apply_chat_template, process_vision_info, model.generate 코드)
    
    # 추론 로직 실행...
    try:
        # 2. 메시지 구성 (image_url과 question 사용)
        messages = [
             {
                 "role": "user",
                 "content": [
                     {"type": "image", "image": image_url},
                     {"type": "text", "text": f"<image>\n{question}"}
                 ],
             }
        ]
        
        # 3. processor로 입력 준비       
        print("입력 텐서 준비 중...")
        text_input = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, _ = process_vision_info(messages)

        inputs = processor(
            text=[text_input],
            images=image_inputs,
            # videos=video_inputs,
            padding=True,
            return_tensors="pt"
        ).to(device)
        print("입력 텐서 준비 완료!")

        
        # 4. 추론
        print("모델 추론 시작...")
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=280)

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        print("디코딩 중...")
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )

        print("모델 출력:")
        
        inference_result = f"처방 ID {input_data.prescription_id}에 대한 추론 출력: \n {output_text[0]}"
        
        # GPU 메모리 즉시 정리
        del generated_ids, generated_ids_trimmed, inputs, image_inputs
        torch.cuda.empty_cache()
        gc.collect()
        print(f"✅ GPU 메모리 정리 완료 (prescription_id: {input_data.prescription_id})")
        
        return {"prescription_id": input_data.prescription_id, "inference_result": inference_result}
        
    except Exception as e:
        print(f"추론 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"VQA 추론 중 오류 발생: {e}")

# 서버 실행 명령어: uvicorn main:app --reload --port 8000