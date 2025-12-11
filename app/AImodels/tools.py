# app/AImodels/tools.py
from langchain.tools import BaseTool, Tool
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.drug_service import get_drug_info
from app.services.ai_service import ai_service
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# [A] 사용자 정의 Tool 함수
# app/AImodels/tools.py 중 run_vl_model_inference 함수만 수정

def run_vl_model_inference(image_identifier: str) -> str:
    """
    VL 모델 추론 함수
    
    Args:
        image_identifier: prescription_id 또는 file_key
        
    Returns:
        VL 모델 분석 결과 텍스트
    """
    try:
        from supabase import create_client
        from app.core.config import settings
        from app.services.s3_service import s3_service
        from app.services.ai_service import ai_service
        from PIL import Image
        from io import BytesIO
        
        logger.info(f"🖼️ VL Tool 호출: {image_identifier}")
        
        # Supabase 클라이언트 생성
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # prescription_id로 조회 시도
        try:
            prescription_id = int(image_identifier)
            result = supabase.table("prescriptions").select("file_key, ai_analysis").eq(
                "id", prescription_id
            ).execute()
            
            if not result.data:
                return f"처방전 ID {image_identifier}를 찾을 수 없습니다."
            
            # 이미 분석된 결과가 있으면 반환
            if result.data[0].get('ai_analysis'):
                logger.info(f"✅ 기존 분석 결과 사용: prescription_id={image_identifier}")
                return str(result.data[0]['ai_analysis'])
            
            file_key = result.data[0]['file_key']
            
        except ValueError:
            # 숫자가 아니면 file_key로 간주
            file_key = image_identifier
        
        # S3에서 이미지 다운로드
        logger.info(f"📥 S3에서 이미지 다운로드: {file_key}")
        image_bytes = s3_service.download_prescription(file_key)
        
        if not image_bytes:
            return f"이미지를 다운로드할 수 없습니다: {file_key}"
        
        # PIL Image로 변환
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        
        # VL 모델 실행 (동기 버전 사용)
        prompt = "这张处方上写了什么？"
        analysis_result = ai_service.analyze_prescription_sync(image, prompt)
        
        # 👇 추가: 메모리 정리
        import gc
        import torch
        
        del image  # 이미지 객체 삭제
        gc.collect()  # 가비지 컬렉션
        if torch.cuda.is_available():
            torch.cuda.empty_cache()  # GPU 캐시 비우기

        logger.info(f"✅ VL 분석 완료: {image_identifier}")

        # 👇 추가: DB 업데이트
        try:
            prescription_id = int(image_identifier)
            supabase.table("prescriptions").update({
                "ai_analysis": analysis_result,
                "analysis_status": "completed"
            }).eq("id", prescription_id).execute()
            logger.info(f"💾 DB updated: prescription_id={prescription_id}")
        except ValueError:
            # file_key인 경우는 업데이트 생략
            pass
        
        return analysis_result
        
    except Exception as e:
        # 에러 시에도 상태 업데이트
        try:
            prescription_id = int(image_identifier)
            supabase.table("prescriptions").update({
                "analysis_status": "failed"
            }).eq("id", prescription_id).execute()
        except:
            pass
        
        return f"이미지 분석 중 오류가 발생했습니다: {str(e)}"


def call_public_data_api(search_query: str) -> str:
    """
    공공데이터포털 API 호출 함수 (식약처 약물 정보)
    
    Args:
        search_query: 검색할 약물 이름
        
    Returns:
        약물 정보 텍스트
    """
    try:
        logger.info(f"💊 Drug API Tool 호출: {search_query}")
        
        result = get_drug_info(search_query)
        
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
            
    except Exception as e:
        logger.error(f"약물 정보 검색 실패: {e}")
        return f"약물 정보 검색 중 오류가 발생했습니다: {str(e)}"


# [B] Tool 객체 생성 및 Description 명시 (매우 중요)
vl_tool = Tool(
    name="VL_Model_Image_Analyzer",
    func=run_vl_model_inference,
    description=(
        "사용자가 이미지 파일을 업로드했거나, 이미지에 대한 분석/추론이 필요한 질문을 했을 때 사용합니다. "
        "특히 질문에 'prescription_id: 숫자' 형식이 포함되어 있으면 반드시 이 도구를 사용해야 합니다. "
        "입력은 prescription_id 또는 이미지 파일 경로(file_key)여야 합니다."
    )
)

api_tool = Tool(
    name="Public_Data_API_Searcher",
    func=call_public_data_api,
    description=(
        "LLM의 학습 데이터에 없는 최신 정보, 실시간 데이터, 또는 공공데이터와 같은 특정 도메인 지식이 필요할 때 사용합니다. "
        "약물 이름, 의약품 정보 등을 검색할 때 이 도구를 사용하세요. 질문에 포함된 키워드로 검색을 수행합니다."
    )
)

# [C] 전역 Tool 리스트 (agent_factory.py에서 사용)
ALL_TOOLS: List[Tool] = [vl_tool, api_tool]


# [D] 기존 BaseTool 방식도 유지 (호환성)

class DrugSearchInput(BaseModel):
    """약물 검색을 위한 입력 스키마"""
    drug_name: str = Field(description="검색할 약물의 이름")


class DrugInfoTool(BaseTool):
    """식약처 API를 호출하여 약물 정보를 검색하는 Tool (기존 코드)"""
    
    name: str = "drug_information_search"
    description: str = (
        "약물 이름에 대한 자세한 정보를 찾을 때 사용합니다. "
        "효능, 사용법, 부작용, 주의사항 등을 제공합니다."
    )
    args_schema: type[BaseModel] = DrugSearchInput
    return_direct: bool = False
    
    def _run(self, drug_name: str) -> str:
        """실제 Tool의 실행 로직"""
        return call_public_data_api(drug_name)
    
    async def _arun(self, drug_name: str) -> str:
        """비동기 실행 미지원"""
        raise NotImplementedError("DrugInfoTool does not support async run")