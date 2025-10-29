# app/api/upload_router.py
from fastapi import APIRouter, UploadFile
from app.services.s3_service import upload_to_s3

router = APIRouter()

@router.post("/")
async def upload(file: UploadFile):
    url = upload_to_s3(file)
    return {"file_url": url}
