from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.api import prescription
from app.api.auth import router as auth_router  # 새로 추가
from app.api.users import router as users_router
from app.api.hospitals import router as hospitals_router # 새로 추가

app = FastAPI(title="병원 진료 도우미 API")

@app.get("/")
def root():
    return {"message": "Hospital Assistant API"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """데이터베이스 연결 상태 확인"""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected ✅"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected ❌",
            "error": str(e)
        }

# 라우터 등록
app.include_router(prescription.router)
app.include_router(auth_router)  # 새로 추가
app.include_router(users_router) # 새로 추가
app.include_router(hospitals_router) # 새로 추가