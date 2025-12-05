from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager
import logging

from app.core.database import get_db
from app.api import prescription
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.hospitals import router as hospitals_router
from app.api.drug import router as drug_router

# Agent 초기화 함수 import
from app.AImodels.agent_factory import initialize_global_agent

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan 이벤트 (앱 시작/종료 시 실행)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 Agent 초기화"""
    logger.info("=" * 80)
    logger.info("🚀 새로이안 백엔드 서버 시작 중...")
    logger.info("=" * 80)
    
    try:
        logger.info("📦 LangChain Agent 초기화 중...")
        initialize_global_agent()
        logger.info("✅ LangChain Agent 초기화 완료")
    except Exception as e:
        logger.error(f"❌ Agent 초기화 실패: {e}")
        logger.warning("⚠️  채팅 기능이 제한될 수 있습니다.")
    
    logger.info("=" * 80)
    logger.info("✅ 서버 시작 완료!")
    logger.info("=" * 80)
    
    yield
    
    logger.info("👋 서버 종료 중...")

# FastAPI 앱 인스턴스
app = FastAPI(
    title="새로이안 API",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
)

@app.get("/")
def root():
    return {"message": "새로이안 API"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """데이터베이스 및 Agent 상태 확인"""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected ✅"
    except Exception as e:
        db_status = f"disconnected ❌: {str(e)}"
    
    # Agent 상태 확인
    from app.AImodels.agent_factory import initial_agent, huggingfacehub
    
    return {
        "status": "healthy" if "✅" in db_status else "unhealthy",
        "database": db_status,
        "langchain_agent": {
            "initialized": initial_agent is not None and initial_agent,
            "llm_loaded": huggingfacehub is not None
        }
    }

# 라우터 등록
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(hospitals_router)
app.include_router(prescription.router)
app.include_router(drug_router)