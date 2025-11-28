# app/services/drug_service.py
import requests
from typing import Optional, Dict, Any
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_drug_info(drug_name: str) -> Dict[str, Any]:
    """
    식약처 API를 호출하여 의약품 정보를 가져옴
    
    Args:
        drug_name: 검색할 의약품 이름
        
    Returns:
        Dict: 의약품 정보 (효능, 사용법, 부작용, 주의사항)
    """
    try:
        # API 요청 파라미터
        params = {
            "serviceKey": settings.DRUG_API_SERVICE_KEY,
            "itemName": drug_name,
            "type": "json",
            "numOfRows": 10  # 최대 10개 결과
        }
        
        # API 호출
        response = requests.get(settings.DRUG_API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # 응답 검증
        if data.get("header", {}).get("resultCode") != "00":
            return {
                "status": "error",
                "message": f"API 오류: {data.get('header', {}).get('resultMsg', 'Unknown error')}"
            }
        
        items = data.get("body", {}).get("items", [])
        
        if not items:
            return {
                "status": "not_found",
                "message": f"'{drug_name}' 의약품 정보를 찾을 수 없습니다."
            }
        
        # 정확히 일치하는 약품 찾기
        matched_item = find_exact_match(items, drug_name)
        
        if not matched_item:
            # 정확히 일치하는 게 없으면 첫 번째 결과 사용
            matched_item = items[0]
        
        # 주요 정보만 추출
        return {
            "status": "success",
            "data": {
                "entpName": matched_item.get("entpName", ""),
                "itemName": matched_item.get("itemName", ""),
                "efcyQesitm": matched_item.get("efcyQesitm", ""),  # 효능
                "useMethodQesitm": matched_item.get("useMethodQesitm", ""),  # 사용법
                "atpnQesitm": matched_item.get("atpnQesitm", ""),  # 주의사항
                "seQesitm": matched_item.get("seQesitm", "")  # 부작용
            }
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"API timeout for drug: {drug_name}")
        return {
            "status": "error",
            "message": "API 요청 시간 초과"
        }
    except Exception as e:
        logger.error(f"Error fetching drug info: {str(e)}")
        return {
            "status": "error",
            "message": f"의약품 정보 조회 실패: {str(e)}"
        }


def find_exact_match(items: list, drug_name: str) -> Optional[Dict]:
    """
    검색 결과에서 약품명이 정확히 일치하는 항목 찾기
    
    Args:
        items: API 응답 아이템 리스트
        drug_name: 검색한 약품명
        
    Returns:
        정확히 일치하는 아이템 또는 None
    """
    drug_name_lower = drug_name.lower().strip()
    
    for item in items:
        item_name = item.get("itemName", "").lower().strip()
        if drug_name_lower in item_name or item_name in drug_name_lower:
            return item
    
    return None