# app/services/s3_service.py
from app.core.s3_client import s3_client
from app.core.config import settings

def upload_to_s3(file):
    """
    AWS S3에 파일 업로드 후 URL 반환
    """
    s3_client.upload_fileobj(file.file, settings.AWS_BUCKET_NAME, file.filename)
    return f"https://{settings.AWS_BUCKET_NAME}.s3.amazonaws.com/{file.filename}"
