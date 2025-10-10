from fastapi import FastAPI
from app.database import engine, Base
from app.routers import users

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(title="User Management API")

# 라우터 등록
app.include_router(users.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to User Management API"}