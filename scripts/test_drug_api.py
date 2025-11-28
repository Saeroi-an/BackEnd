import requests

def test_drug_info(drug_name: str):
    """의약품 API 테스트"""
    url = "http://localhost:8000/api/drug-info"
    payload = {"drug_name": drug_name}
    
    print(f"[TEST] POST {url}")
    print(f"[PAYLOAD] {payload}")
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"[STATUS] {res.status_code}")
        print(f"[RESPONSE] {res.json()}")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    print("===== 의약품 API 테스트 =====")
    test_drug_info("타이레놀")