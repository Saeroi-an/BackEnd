# app/AImodels/tools.py
from langchain.tools import BaseTool, Tool
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.drug_service import get_drug_info
import requests
import logging

logger = logging.getLogger(__name__)

# [A] 사용자 정의 Tool 함수

def run_vl_model_inference(image_identifier: str) -> str:
    """
    VL 모델 추론 함수 (VQA API 호출 방식)
    
    Args:
        image_identifier: prescription_id (문자열 또는 숫자)
        
    Returns:
        VL 모델 분석 결과 텍스트
    """
    try:
        from supabase import create_client
        from app.core.config import settings
        
        logger.info(f"🖼️ VL Tool 호출: {image_identifier}")
        
        # Supabase 클라이언트 생성
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # 1. prescription_id로 변환 시도
        try:
            prescription_id = int(image_identifier)
        except ValueError:
            return f"오류: prescription_id는 숫자여야 합니다: {image_identifier}"
        
        # 2. Supabase에서 처방전 정보 조회
        result = supabase.table("prescriptions").select(
            "file_url, ai_analysis, analysis_status"
        ).eq("id", prescription_id).execute()
        
        if not result.data:
            return f"처방전 ID {prescription_id}를 찾을 수 없습니다."
        
        prescription_data = result.data[0]
        
        # 3. 이미 분석된 결과가 있으면 반환 (캐시 활용)
        if prescription_data.get('ai_analysis') and prescription_data.get('analysis_status') == 'completed':
            logger.info(f"✅ 기존 분석 결과 사용: prescription_id={prescription_id}")
            return str(prescription_data['ai_analysis'])
        
        file_url = prescription_data.get('file_url')
        if not file_url:
            return f"처방전 ID {prescription_id}의 이미지 URL이 없습니다."
        
        # 4. VQA API 호출 (HTTP 요청)
        vqa_api_url = "http://localhost:8000/api/vqa_inference"
        
        logger.info(f"📡 VQA API 호출 시작: prescription_id={prescription_id}")
        
        try:
            response = requests.post(
                vqa_api_url,
                json={
                    "image_path": file_url,
                    "question": "这张处方上写了什么？ 尤其是药品、服用次数等，请准确全部告诉我。",
                    "prescription_id": prescription_id
                },
                headers={"Content-Type": "application/json"},
                timeout=60  # 60초 타임아웃 (VL 모델 추론 시간 고려)
            )
            
            if not response.ok:
                raise Exception(f"VQA API 호출 실패: 상태 코드 {response.status_code}")
            
            data = response.json()
            analysis_result = data.get("inference_result", "")
            
            logger.info(f"✅ VQA API 호출 성공: prescription_id={prescription_id}")
            
            # 5. DB 업데이트 (분석 결과 저장)
            try:
                supabase.table("prescriptions").update({
                    "ai_analysis": analysis_result,
                    "analysis_status": "completed"
                }).eq("id", prescription_id).execute()
                logger.info(f"💾 DB 업데이트 완료: prescription_id={prescription_id}")
            except Exception as db_error:
                logger.error(f"DB 업데이트 실패: {db_error}")
            
            return analysis_result
            
        except requests.exceptions.Timeout:
            error_msg = f"VQA API 요청 시간 초과 (60초): prescription_id={prescription_id}"
            logger.error(error_msg)
            
            # 에러 시 상태 업데이트
            try:
                supabase.table("prescriptions").update({
                    "analysis_status": "failed"
                }).eq("id", prescription_id).execute()
            except:
                pass
            
            return f"이미지 분석 중 시간 초과가 발생했습니다."
            
        except Exception as api_error:
            error_msg = f"VQA API 호출 오류: {api_error}"
            logger.error(error_msg)
            
            # 에러 시 상태 업데이트
            try:
                supabase.table("prescriptions").update({
                    "analysis_status": "failed"
                }).eq("id", prescription_id).execute()
            except:
                pass
            
            return f"이미지 분석 중 오류가 발생했습니다: {str(api_error)}"
        
    except Exception as e:
        logger.error(f"VL Tool 실행 오류: {e}")
        return f"처방전 분석 중 오류가 발생했습니다: {str(e)}"


def call_public_data_api(search_query: str) -> str:
    """
    공공데이터포털 API 호출 함수 (일반의약품 + 전문의약품 통합)
    
    Args:
        search_query: 검색할 약물 이름
        
    Returns:
        약물 정보 텍스트
    """
    try:
        logger.info(f"💊 Drug API Tool 호출: {search_query}")
        
        # 통합 검색 함수 사용
        result = get_drug_info(search_query)
        
        if result["status"] == "success":
            drug_type = result.get("drug_type", "unknown")
            data = result["data"]
            
            # 일반의약품 포맷
            if drug_type == "general":
                response = f"""
약물명: {data.get('itemName', '정보없음')}
제조사: {data.get('entpName', '정보없음')}
분류: 일반의약품

효능효과:
{data.get('efcyQesitm', '정보없음')[:500]}

사용방법:
{data.get('useMethodQesitm', '정보없음')[:300]}

주의사항:
{data.get('atpnQesitm', '정보없음')[:300]}

부작용:
{data.get('seQesitm', '정보없음')[:300]}
"""
                return response.strip()
            
            # 전문의약품 포맷
            elif drug_type == "prescription":
                response = f"""
제품명: {data.get('itemName', '정보없음')}
제조사: {data.get('entpName', '정보없음')}
분류: {data.get('spcltyPblc', '전문의약품')}

주성분: {data.get('itemIngrName', '정보없음')}
약물 분류: {data.get('prductType', '정보없음')}

품목일련번호: {data.get('itemSeq', '정보없음')}
보험코드: {data.get('ediCode', '정보없음') or '해당없음'}

※ 이 약은 전문의약품으로 의사의 처방이 필요합니다.
※ 상세한 효능, 용법, 부작용 정보는 의사 또는 약사와 상담하세요.
"""
                return response.strip()
            
            else:
                return "약물 정보를 찾았으나 형식을 확인할 수 없습니다."
        
        elif result["status"] == "not_found":
            return result.get("message", f"'{search_query}'에 대한 약물 정보를 찾을 수 없습니다.")
        
        else:  # error
            return result.get("message", "약물 정보 검색 중 오류가 발생했습니다.")
            
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
        "입력은 prescription_id(숫자)여야 합니다. "
        "예: 'prescription_id: 3'이 포함된 질문이면 이 도구에 '3'을 입력하세요."
    )
)

api_tool = Tool(
    name="Public_Data_API_Searcher",
    func=call_public_data_api,
    description=(
        "약물 정보(일반의약품 및 전문의약품)를 검색할 때 사용합니다. "
        "약물 이름, 의약품 정보, 효능, 부작용 등을 검색할 때 이 도구를 사용하세요. "
        "일반의약품은 상세 정보를, 전문의약품은 기본 정보(제품명, 제조사, 성분 등)를 제공합니다. "
        "질문에 포함된 약물 이름 키워드로 검색을 수행합니다."
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
        "일반의약품과 전문의약품을 모두 검색하며, "
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