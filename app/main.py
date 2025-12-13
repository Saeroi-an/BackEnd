# app/main.py
from fastapi import FastAPI

app = FastAPI()

# ✅ VQA 라우터만 먼저 붙이기 (아래에서 만들 파일)
from app.api.vqa_inference import router as vqa_router
app.include_router(vqa_router, prefix="/api", tags=["vqa"])

# ✅ 나중에 LangChain 문제 해결되면 다시 살리기
# from app.api import prescription
# app.include_router(prescription.router)