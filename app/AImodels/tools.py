# app/AImodels/tools.py
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
from app.services.drug_service import get_drug_info

class DrugSearchInput(BaseModel):
    """약물 검색을 위한 입력 스키마"""
    drug_name: str = Field(description="검색할 약물의 이름")

class DrugInfoTool(BaseTool):
    """식약처 API를 호출하여 약물 정보를 검색하는 Tool"""
    
    name: str = "drug_information_search"
    description: str = (
        "약물 이름에 대한 자세한 정보를 찾을 때 사용합니다. "
        "효능, 사용법, 부작용, 주의사항 등을 제공합니다."
    )
    args_schema: type[BaseModel] = DrugSearchInput
    return_direct: bool = False
    
    def _run(self, drug_name: str) -> str:
        """실제 Tool의 실행 로직"""
        result = get_drug_info(drug_name)
        
        if result["status"] == "success":
            data = result["data"]
            response = f"""
약물명: {data.get('itemName', '정보없음')}
제조사: {data.get('entpName', '정보없음')}

효능효과: {data.get('efcyQesitm', '정보없음')[:300]}...

사용방법: {data.get('useMethodQesitm', '정보없음')[:200]}...

주의사항: {data.get('atpnQesitm', '정보없음')[:200]}...

부작용: {data.get('seQesitm', '정보없음')[:200]}...
"""
            return response.strip()
        else:
            return result.get("message", "약물 정보를 찾을 수 없습니다.")
    
    async def _arun(self, drug_name: str) -> str:
        """비동기 실행 미지원"""
        raise NotImplementedError("DrugInfoTool does not support async run")