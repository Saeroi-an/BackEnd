# app/services/s3_service.py
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import os
from typing import Optional
import uuid
from fastapi import UploadFile, HTTPException
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_BUCKET_NAME
        self.prescription_folder = settings.S3_PRESCRIPTION_FOLDER
        
    def _generate_unique_filename(self, original_filename: str) -> str:
        """유니크한 파일명 생성"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        extension = original_filename.split('.')[-1] if '.' in original_filename else 'jpg'
        return f"{timestamp}_{unique_id}.{extension}"
    
    async def upload_prescription(
        self, 
        file: UploadFile, 
        user_id: Optional[str] = None
    ) -> dict:
        """
        처방전 이미지를 S3에 업로드
        
        Args:
            file: 업로드할 파일
            user_id: 사용자 ID (옵션)
            
        Returns:
            dict: {
                'file_url': S3 파일 URL,
                'file_key': S3 객체 키,
                'original_filename': 원본 파일명
            }
        """
        try:
            # 파일 확장자 검증
            allowed_extensions = {'jpg', 'jpeg', 'png', 'pdf'}
            file_extension = file.filename.split('.')[-1].lower()
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"지원하지 않는 파일 형식입니다. 허용: {allowed_extensions}"
                )
            
            # 파일 크기 검증 (10MB 제한)
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="파일 크기는 10MB를 초과할 수 없습니다."
                )
            
            # 파일명 생성
            unique_filename = self._generate_unique_filename(file.filename)
            
            # S3 키 생성 (user_id가 있으면 폴더 구조에 포함)
            if user_id:
                s3_key = f"{self.prescription_folder}{user_id}/{unique_filename}"
            else:
                s3_key = f"{self.prescription_folder}{unique_filename}"
            
            # S3에 업로드
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=file.content_type or 'image/jpeg',
                Metadata={
                    'original_filename': file.filename,
                    'upload_timestamp': datetime.now().isoformat()
                }
            )
            
            # 파일 URL 생성
            file_url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            
            logger.info(f"파일 업로드 성공: {s3_key}")
            
            return {
                'file_url': file_url,
                'file_key': s3_key,
                'original_filename': file.filename
            }
            
        except ClientError as e:
            logger.error(f"S3 업로드 실패: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"파일 업로드 중 오류가 발생했습니다: {str(e)}"
            )
        except Exception as e:
            logger.error(f"예상치 못한 오류: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"파일 업로드 중 오류가 발생했습니다: {str(e)}"
            )
    
    def download_prescription(self, file_key: str) -> Optional[bytes]:
        """
        S3에서 처방전 이미지 다운로드
        
        Args:
            file_key: S3 객체 키
            
        Returns:
            bytes: 이미지 바이너리 데이터 (실패 시 None)
        """
        try:
            logger.info(f"📥 S3에서 다운로드 시도: {file_key}")
            
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            image_bytes = response['Body'].read()
            
            logger.info(f"✅ S3 다운로드 성공: {file_key} ({len(image_bytes)} bytes)")
            
            return image_bytes
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"❌ S3 다운로드 실패 ({error_code}): {file_key}")
            return None
        except Exception as e:
            logger.error(f"❌ 예상치 못한 다운로드 오류: {str(e)}")
            return None
    
    def delete_prescription(self, file_key: str) -> bool:
        """
        S3에서 처방전 이미지 삭제
        
        Args:
            file_key: S3 객체 키
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            logger.info(f"파일 삭제 성공: {file_key}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 삭제 실패: {str(e)}")
            return False
    
    def generate_presigned_url(
        self, 
        file_key: str, 
        expiration: int = 3600
    ) -> Optional[str]:
        """
        임시 접근 URL 생성 (보안이 필요한 경우)
        
        Args:
            file_key: S3 객체 키
            expiration: URL 만료 시간(초)
            
        Returns:
            str: Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_key
                },
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            logger.error(f"Presigned URL 생성 실패: {str(e)}")
            return None

# 싱글톤 인스턴스
s3_service = S3Service()