# langchain_test.py  (VQA 단독 테스트용)

import os
import logging

import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# =========================
# 로깅 설정
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# 설정값
# =========================
MODEL_NAME = "Rfy23/qwenvl-7B-medical-ko-zh"
IMAGE_URL = "BackEnd/testimage.jpg"  # 실행 위치에 따라 상대경로가 꼬일 수 있어 아래에서 abs로 변환합니다.
FIXED_QUESTION = "这张处方上写了什么？ 尤其是药品、服用次数等，请准确全部告诉我。"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

QWEN_MODEL = None
QWEN_PROCESSOR = None


def load_qwen_components(model_name: str, device: str):
    """Qwen2VL 모델과 프로세서를 전역으로 1회 로드"""
    global QWEN_MODEL, QWEN_PROCESSOR

    if QWEN_MODEL is not None and QWEN_PROCESSOR is not None:
        logger.info("모델이 이미 로드되어 있습니다.")
        return

    logger.info(f"🚀 VQA 모델 '{model_name}' 로드 시작 (Device: {device})")
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    device_map = "auto" if device == "cuda" else None

    try:
        print("모델 로드 중...")
        QWEN_MODEL = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map
        )
        QWEN_MODEL.eval()

        QWEN_PROCESSOR = AutoProcessor.from_pretrained(model_name)
        print("모델 로드 완료!")
        logger.info("✅ 모델/프로세서 로드 완료")

    except Exception as e:
        logger.error(f"❌ 모델 로드 중 오류: {e}")
        raise


def vqa_model(image_path: str, question: str = FIXED_QUESTION, max_new_tokens: int = 128) -> str:
    """이미지 경로 + 질문 -> Qwen2VL로 답변 생성"""
    global QWEN_MODEL, QWEN_PROCESSOR

    if QWEN_MODEL is None or QWEN_PROCESSOR is None:
        return "오류: 모델이 로드되지 않았습니다. load_qwen_components()를 먼저 호출하세요."

    if not os.path.exists(image_path):
        return f"오류: 이미지 파일이 존재하지 않습니다: {image_path}"

    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": f"<image>\n{question}"}
                ],
            }
        ]

        logger.info(f"🖼️ VQA 추론 시작 - Image: {image_path}")
        print("입력 텐서 준비 중...")

        text_input = QWEN_PROCESSOR.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        image_inputs, _ = process_vision_info(messages)

        inputs = QWEN_PROCESSOR(
            text=[text_input],
            images=image_inputs,
            padding=True,
            return_tensors="pt"
        ).to(DEVICE)

        with torch.no_grad():
            generated_ids = QWEN_MODEL.generate(**inputs, max_new_tokens=max_new_tokens)

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        output_text = QWEN_PROCESSOR.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )

        logger.info("✅ VQA 추론 완료")
        return output_text[0]

    except Exception as e:
        return f"VQA 처리 중 오류 발생: {str(e)}"


if __name__ == "__main__":
    # 경로 확실히(상대경로 이슈 방지)
    IMAGE_URL_ABS = os.path.abspath(IMAGE_URL)
    print("이미지 경로:", IMAGE_URL_ABS)
    print("파일 존재?:", os.path.exists(IMAGE_URL_ABS))
    print("DEVICE:", DEVICE)

    # 1회 로드 후 추론
    load_qwen_components(MODEL_NAME, DEVICE)
    result = vqa_model(IMAGE_URL_ABS, FIXED_QUESTION)

    print("\n===== VQA 결과 =====")
    print(result)