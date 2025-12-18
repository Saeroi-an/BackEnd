# Saeroi-an BackEnd
BackEnd/
├── README.md: 프로젝트의 설명서
├── requirements.txt: Python 프로젝트의 의존성(dependencies) 목록을 명시하는 파일
├── setup.py: Python 패키지 설치 설정 파일 (setuptools 기반).
├── app/
│   ├── __init__.py: 초기화
│   ├── main.py: FastAPI 애플리케이션의 진입점(Entry Point). 서버 초기화, 미들웨어 설정, 라우터 등록을 담당.
│   ├── AImodels/
│   │   ├── agent_factory.py: LangChain Agent(ReAct 방식)를 생성하고 초기화하는 팩토리 모듈. OpenAI LLM + Tools를 결합하여 AgentExecutor 생성.
│   │   ├── tools.py: LangChain Agent가 사용할 Tool(도구) 함수들을 정의하고 전역 리스트로 제공.
│   │   └── qwen_model.py: Qwen2VL 비전-언어 모델을 클래스로 캡슐화하여 모델 로드 및 추론 기능 제공.
│   ├── api/
│   │   ├── __init__.py: 초기화
│   │   ├── auth.py: Google OAuth 2.0 인증을 처리하는 API 라우터. 로그인 및 콜백 엔드포인트 제공.
│   │   ├── users.py: 사용자 프로필 조회 및 수정 API 라우터.
│   │   ├── hospitals.py: 병원 정보 조회 REST API 엔드포인트. Supabase에서 병원 목록을 페이지네이션으로 제공.
│   │   ├── prescription.py: 처방전 이미지 업로드, 분석, 채팅 기능을 제공하는 핵심 API 라우터.
│   │   └── drug.py: 의약품 정보 조회 REST API 엔드포인트. 식약처 공공데이터 API를 호출하는 서비스를 래핑.
│   ├── core/
│   │   ├── __init__.py: 초기화
│   │   ├── config.py: 환경 변수 기반 애플리케이션 설정 관리. .env 파일에서 설정 로드 및 전역 접근 제공.
│   │   ├── database.py: 데이터베이스 연결 및 세션 관리. SQLAlchemy(PostgreSQL) + Supabase 클라이언트 제공.
│   │   └── security.py: JWT 토큰 생성 및 검증, 사용자 인증 처리.
│   ├── models/
│   │   ├── __init__.py: 초기화
│   │   └── user.py: 사용자 관련 Pydantic 모델 정의 (요청/응답 스키마, 데이터 검증).
│   ├── services/
│   │   ├── __init__.py: 초기화
│   │   ├── auth_service.py: 인증 관련 비즈니스 로직 처리 (Google OAuth + 이메일/비밀번호 로그인).
│   │   ├── chat_service.py: Supabase 기반 채팅 메모리 관리 및 LangChain Agent 실행 핵심 서비스.
│   │   ├── drug_service.py: 한국 식약처 공공데이터 API를 호출하여 의약품 정보 검색 (일반의약품 + 전문의약품).
│   │   ├── s3_service.py: AWS S3 파일 관리 서비스 레이어 (업로드/다운로드/삭제/Presigned URL 생성).
│   │   ├── user_service.py: 사용자 관련 비즈니스 로직 처리 (프로필 업데이트).
│   │   └── ai_service.py: Qwen2VL 모델을 래핑한 처방전 이미지 분석 서비스 (PIL.Image → 텍스트 분석)
│   └── vqa_server.py: Qwen2VL 모델을 로드하고 VQA(Visual Question Answering) 추론 API 서버를 제공하는 독립 FastAPI 애플리케이션.
├── data/
│   └── 충청북도_의료기관현황_20240830.csv: 충청북도 지역 의료기관 정보 데이터 (CSV 파일).
├── scripts/
│   └── import_hospitals.py: CSV 파일의 병원 데이터를 Supabase DB에 일괄 임포트하는 1회성 스크립트.
