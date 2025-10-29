from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from models.qwen_model import QwenModel

# .env 파일 로드
load_dotenv()

# 환경변수에서 Hugging Face 토큰 가져오기
hf_token = os.environ.get("HF_TOKEN")

app = Flask(__name__)

# 모델 인스턴스 생성 (한 번만 로드)
qwen_model = QwenModel()

@app.route("/predict", methods=["POST"]) #/predict ✅- front에서 받을 때
def predict():
    data = request.json
    # text_input = data.get("text")
    text_input = "这张处方上写了什么？" 
    image_url = data.get("image")  # 단일 이미지 URL

    # 입력 검증
    if not text_input:
        return jsonify({"error": "No text provided"}), 400
    if not image_url:
        return jsonify({"error": "No image URL provided"}), 400

    # Lava JSON 단일 질문 포맷
    inference_input = {
        "id": "inference_001",
        "image": image_url,
        "conversations": [
            {
                "from": "human",
                "value": f"<image>\n{text_input}"
            }
        ]
    }

    try:
        # 모델 predict 호출
        output_text = qwen_model.predict(inference_input)
        return jsonify({"prediction": output_text})
	      # return output_text # 문자열 ✅ -front에 보낼때
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)