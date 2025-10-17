# app/main.py
from fastapi import FastAPI
from app.api import ai_router, auth_router, upload_router, hospital_router

app = FastAPI(title="Multimodal AI Backend")

# 라우터 등록
app.include_router(ai_router.router, prefix="/ai", tags=["AI"])
app.include_router(auth_router.router, prefix="/auth", tags=["Auth"])
app.include_router(upload_router.router, prefix="/upload", tags=["Upload"])
app.include_router(hospital_router.router, prefix="/hospital", tags=["Hospital"])

@app.get("/")
def root():
    return {"message": "Backend API is running 🚀"}
