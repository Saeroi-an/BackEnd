# app/AImodels/tools.py
from langchain.tools import BaseTool, tool
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.drug_service import get_drug_info
import requests
import logging

logger = logging.getLogger(__name__)

# [A] 사용자 정의 Tool 함수

@tool
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
        vqa_api_url = "http://localhost:8001/api/vqa_inference"
        
        logger.info(f"📡 VQA API 호출 시작: prescription_id={prescription_id}")
        
        try:
            response = requests.post(
                vqa_api_url,
                json={
                    "image_path": file_url,
                    "question": "请读取处方上的韩文药品名称（保持韩文原样），然后用中文说明服用方法、次数、期限等信息。",
                    "prescription_id": prescription_id
                },
                headers={"Content-Type": "application/json"},
                timeout=300  # 60초 타임아웃 (VL 모델 추론 시간 고려)
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

@tool
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
# vl_tool = Tool(
#     name="VL_Model_Image_Analyzer",
#     func=run_vl_model_inference,
#     description=(
#         "사용자가 이미지 파일을 업로드했거나, 이미지에 대한 분석/추론이 필요한 질문을 했을 때 사용합니다. "
#         "특히 질문에 'prescription_id: 숫자' 형식이 포함되어 있으면 반드시 이 도구를 사용해야 합니다. "
#         "입력은 prescription_id(숫자)여야 합니다. "
#         "예: 'prescription_id: 3'이 포함된 질문이면 이 도구에 '3'을 입력하세요."
#     )
# )

# api_tool = Tool(
#     name="Public_Data_API_Searcher",
#     func=call_public_data_api,
#     description=(
#         "LLM의 학습 데이터에 없는 최신 정보, 실시간 데이터, 또는 공공데이터와 같은 특정 도메인 지식이 필요할 때 사용합니다. "
#         "약물 이름, 의약품 정보 등을 검색할 때 이 도구를 사용하세요. 질문에 포함된 키워드로 검색을 수행합니다."
#     )
# )

# multiply_tool = Tool(
#     name = "multiply_tool",
#     func = multiply,
#     description = (
#         "사용자가  두개의 숫자를 주고 '곱하라'라고 입력이 들어올 때, 이 함수를 이용합니다."
#     )
# )

# add_tool = Tool(
#     name = "add_tool",
#     func = add,
#     description = (
#         "사용자가  두개의 숫자를 주고 '더하라'라고 입력이 들어올 때, 이 함수를 이용합니다."
#     )
# )


@tool
def multiply(x: float, y: float) -> float:
    """Multiply 'x' times 'y'."""
    return x * y

@tool
def add(x: float, y: float) -> float:
    """Add 'x' and 'y'."""
    return x + y



# [C] 전역 Tool 리스트 (agent_factory.py에서 사용)
ALL_TOOLS = [run_vl_model_inference, call_public_data_api, multiply, add]
