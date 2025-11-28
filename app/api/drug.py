# app/api/drug.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.drug_service import get_drug_info
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["drug"])


class DrugInfoRequest(BaseModel):
    drug_name: str


class DrugInfoResponse(BaseModel):
    status: str
    data: dict = None
    message: str = None


@router.post("/drug-info", response_model=DrugInfoResponse)
async def get_drug_information(request: DrugInfoRequest):
    """
    의약품 정보 조회 API
    
    AI 팀의 Langchain Tool에서 호출하는 엔드포인트
    """
    try:
        logger.info(f"Drug info requested: {request.drug_name}")
        
        result = get_drug_info(request.drug_name)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in drug-info endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="서버 오류가 발생했습니다.")