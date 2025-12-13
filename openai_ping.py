from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "API 키 테스트입니다. 한 문장으로 인사해줘."}]
)

print(resp.choices[0].message.content)