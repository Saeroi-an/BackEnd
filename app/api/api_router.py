# app/api/ai_router.py
from fastapi import APIRouter, UploadFile, Form
from app.services.ai_service import ask_ai

router = APIRouter()

@router.post("/predict")
async def predict(image: UploadFile, question: str = Form(...)):
    answer = await ask_ai(image, question)
    return {"answer": answer}