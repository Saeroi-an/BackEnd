import requests

# 테스트할 이미지 경로
image_path = "D:/testimages/00002.jpg"  # 또는 00002.jpg, 00003.jpg
url = "http://localhost:8000/prescriptions/upload"

print("테스트 시작...")
print(f"이미지: {image_path}")

with open(image_path, 'rb') as f:
    files = {'file': f}
    data = {'user_id': 'test_user_123'}
    response = requests.post(url, files=files, data=data)

print(f"\n응답 상태 코드: {response.status_code}")
print("응답 내용:")
print(response.json())