import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Supabase 클라이언트 생성
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# CSV 읽기
df = pd.read_csv('data/충청북도_의료기관현황_20240830.csv', encoding='cp949')

print(f"Total hospitals in CSV: {len(df)}")

# 데이터 임포트
success_count = 0
for index, row in df.iterrows():
    hospital_data = {
        'name': row['의료기관명'],
        'address': row['주소'],
        'phone': row['전화번호'],
        'image_url': None  # 일단 None
    }
    
    try:
        supabase.table('hospitals').insert(hospital_data).execute()
        success_count += 1
        if success_count % 10 == 0:
            print(f"Imported: {success_count}/{len(df)}")
    except Exception as e:
        print(f"Error importing {row['의료기관명']}: {e}")

print(f"\n✅ Import completed: {success_count}/{len(df)} hospitals")