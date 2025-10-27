from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from supabase import create_client, Client
from typing import Generator

# SQLAlchemy 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 연결 상태 확인 (연결이 끊어졌으면 자동 재연결)
    echo=True,  # SQL 쿼리 로깅 (개발 중에만 True, 프로덕션에서는 False)
    pool_size=5,  # 커넥션 풀 크기
    max_overflow=10  # 최대 추가 연결 수
)

# 세션 팩토리
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base 클래스 (모든 모델이 상속받을 부모 클래스)
Base = declarative_base()

# FastAPI 의존성 주입용 함수
def get_db():
    """
    데이터베이스 세션을 생성하고 요청이 끝나면 자동으로 닫아줍니다.
    
    사용 예시:
    @app.get("/users")
    def get_users(db: Session = Depends(get_db)):
        return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Supabase 클라이언트 생성
def get_supabase() -> Generator[Client, None, None]:
    """
    Supabase 클라이언트를 생성하여 반환합니다.
    
    사용 예시:
    @app.get("/users")
    def get_users(supabase: Client = Depends(get_supabase)):
        return supabase.table("users").select("*").execute()
    """
    supabase: Client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_KEY
    )
    try:
        yield supabase
    finally:
        pass  # Supabase 클라이언트는 명시적 종료 불필요