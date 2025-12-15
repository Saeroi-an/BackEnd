# app/services/drug_service.py
import requests
from typing import Optional, Dict, Any
import logging
from difflib import SequenceMatcher
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_drug_info(drug_name: str) -> Dict[str, Any]:
    """
    식약처 API를 호출하여 의약품 정보를 가져옴
    1단계: 일반의약품 검색
    2단계: 실패 시 전문의약품 검색
    
    Args:
        drug_name: 검색할 의약품 이름
        
    Returns:
        Dict: 의약품 정보 (효능, 사용법, 부작용, 주의사항)
    """
    # 1단계: 일반의약품 검색
    logger.info(f"💊 약물 검색 시작: {drug_name}")
    result = search_general_drug(drug_name)
    
    if result["status"] == "success":
        logger.info(f"✅ 일반의약품 검색 성공: {drug_name}")
        return result
    
    # 2단계: 전문의약품 검색
    logger.info(f"⏭️  일반의약품 검색 실패, 전문의약품 검색 시도: {drug_name}")
    result = search_prescription_drug(drug_name)
    
    if result["status"] == "success":
        logger.info(f"✅ 전문의약품 검색 성공: {drug_name}")
        return result
    
    # 두 API 모두 실패
    logger.warning(f"❌ 약물 정보 없음: {drug_name}")
    return {
        "status": "not_found",
        "message": f"'{drug_name}' 의약품 정보를 찾을 수 없습니다."
    }


def search_general_drug(drug_name: str) -> Dict[str, Any]:
    """
    일반의약품 정보 API 호출
    
    Args:
        drug_name: 검색할 의약품 이름
        
    Returns:
        Dict: 의약품 정보 또는 에러
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
                "message": f"일반의약품 '{drug_name}' 정보를 찾을 수 없습니다."
            }
        
        # 정확히 일치하는 약품 찾기
        matched_item = find_exact_match(items, drug_name)
        
        if not matched_item:
            # 정확히 일치하는 게 없으면 첫 번째 결과 사용
            matched_item = items[0]
        
        # 주요 정보만 추출
        return {
            "status": "success",
            "drug_type": "general",  # 약물 타입 추가
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
        logger.error(f"일반의약품 API timeout: {drug_name}")
        return {
            "status": "error",
            "message": "API 요청 시간 초과"
        }
    except Exception as e:
        logger.error(f"일반의약품 검색 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"의약품 정보 조회 실패: {str(e)}"
        }


def search_prescription_drug(drug_name: str) -> Dict[str, Any]:
    """
    전문의약품 정보 API 호출
    
    Args:
        drug_name: 검색할 의약품 이름
        
    Returns:
        Dict: 의약품 정보 또는 에러
    """
    try:
        # 전문의약품 API URL
        prescription_api_url = "http://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"
        
        # API 요청 파라미터
        params = {
            "serviceKey": settings.DRUG_API_SERVICE_KEY,
            "item_name": drug_name,  # 전문의약품은 item_name 사용 (언더스코어)
            "type": "json",
            "numOfRows": 10,
            "pageNo": 1
        }
        
        # API 호출
        response = requests.get(prescription_api_url, params=params, timeout=10)
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
                "message": f"전문의약품 '{drug_name}' 정보를 찾을 수 없습니다."
            }
        
        # 정확히 일치하는 약품 찾기
        matched_item = find_exact_match_prescription(items, drug_name)
        
        if not matched_item:
            # 정확히 일치하는 게 없으면 첫 번째 결과 사용
            matched_item = items[0]
        
        # 전문의약품 정보 추출
        return {
            "status": "success",
            "drug_type": "prescription",  # 약물 타입 추가
            "data": {
                "itemName": matched_item.get("ITEM_NAME", ""),
                "entpName": matched_item.get("ENTP_NAME", ""),
                "itemIngrName": matched_item.get("ITEM_INGR_NAME", ""),  # 주성분
                "prductType": matched_item.get("PRDUCT_TYPE", ""),  # 약물 분류
                "spcltyPblc": matched_item.get("SPCLTY_PBLC", ""),  # 전문의약품 표시
                "itemSeq": matched_item.get("ITEM_SEQ", ""),  # 품목일련번호
                "ediCode": matched_item.get("EDI_CODE", "")  # 보험코드
            }
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"전문의약품 API timeout: {drug_name}")
        return {
            "status": "error",
            "message": "API 요청 시간 초과"
        }
    except Exception as e:
        logger.error(f"전문의약품 검색 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"의약품 정보 조회 실패: {str(e)}"
        }


def similarity_ratio(str1: str, str2: str) -> float:
    """두 문자열의 유사도 계산 (0.0 ~ 1.0)"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def find_exact_match(items: list, drug_name: str) -> Optional[Dict]:
    """
    일반의약품 검색 결과에서 약품명이 일치하는 항목 찾기 (유사도 검색 포함)
    
    Args:
        items: API 응답 아이템 리스트
        drug_name: 검색한 약품명
        
    Returns:
        가장 유사한 아이템 또는 None
    """
    drug_name_clean = drug_name.lower().strip().replace(" ", "")
    
    # 1단계: 정확한 일치 찾기
    for item in items:
        item_name = item.get("itemName", "").lower().strip().replace(" ", "")
        if drug_name_clean in item_name or item_name in drug_name_clean:
            logger.info(f"✅ 정확한 일치: {item.get('itemName')}")
            return item
    
    # 2단계: 유사도 기반 검색 (80% 이상 유사)
    best_match = None
    best_ratio = 0.0
    
    for item in items:
        item_name = item.get("itemName", "").replace(" ", "")
        ratio = similarity_ratio(drug_name_clean, item_name)
        
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = item
    
    if best_ratio >= 0.8:  # 80% 이상 유사하면 매칭
        logger.info(f"✅ 유사 매칭 ({best_ratio:.1%}): {best_match.get('itemName')}")
        return best_match
    
    logger.warning(f"⚠️ 유사한 약품 없음 (최고 유사도: {best_ratio:.1%})")
    return None


def find_exact_match_prescription(items: list, drug_name: str) -> Optional[Dict]:
    """
    전문의약품 검색 결과에서 약품명이 일치하는 항목 찾기 (유사도 검색 포함)
    
    Args:
        items: API 응답 아이템 리스트
        drug_name: 검색한 약품명
        
    Returns:
        가장 유사한 아이템 또는 None
    """
    drug_name_clean = drug_name.lower().strip().replace(" ", "")
    
    # 1단계: 정확한 일치 찾기
    for item in items:
        item_name = item.get("ITEM_NAME", "").lower().strip().replace(" ", "")
        if drug_name_clean in item_name or item_name in drug_name_clean:
            logger.info(f"✅ 정확한 일치 (전문의약품): {item.get('ITEM_NAME')}")
            return item
    
    # 2단계: 유사도 기반 검색 (80% 이상 유사)
    best_match = None
    best_ratio = 0.0
    
    for item in items:
        item_name = item.get("ITEM_NAME", "").replace(" ", "")
        ratio = similarity_ratio(drug_name_clean, item_name)
        
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = item
    
    if best_ratio >= 0.8:  # 80% 이상 유사하면 매칭
        logger.info(f"✅ 유사 매칭 (전문의약품, {best_ratio:.1%}): {best_match.get('ITEM_NAME')}")
        return best_match
    
    logger.warning(f"⚠️ 유사한 전문의약품 없음 (최고 유사도: {best_ratio:.1%})")
    return None