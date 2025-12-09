# app/AImodels/agent_factory.py
"""
Agent Factory Module
LLM과 Tool을 전역으로 초기화하고, 세션별 Agent Executor를 생성합니다.
"""
from langchain_community.llms import HuggingFaceHub
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
import os
import logging
from app.AImodels.tools import DrugInfoTool

logger = logging.getLogger(__name__)

# 환경 변수에서 API 토큰 가져오기 - 👈 수정
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN', '')
REPO_ID = os.getenv('LLM_REPO_ID', "google/flan-t5-large")

# 👇 디버깅용 로그 추가
logger.info(f"🔍 HUGGINGFACE_TOKEN 길이: {len(HUGGINGFACE_TOKEN) if HUGGINGFACE_TOKEN else 0}")
logger.info(f"🔍 LLM_REPO_ID: {REPO_ID}")

# 전역 변수
huggingfacehub = None
GLOBAL_TOOLS = []
initial_agent = None

def initialize_global_agent():
    """전역 LLM과 Tool을 초기화"""
    global huggingfacehub, GLOBAL_TOOLS, initial_agent
    
    try:
        logger.info("🚀 Initializing Global LLM and Tools...")
        
        # 토큰 검증 👈 추가
        if not HUGGINGFACE_TOKEN:
            raise ValueError("HUGGINGFACE_TOKEN 환경변수가 설정되지 않았습니다.")
        
        # HuggingFace Hub LLM 초기화 - 👈 수정
        huggingfacehub = HuggingFaceHub(
            repo_id=REPO_ID,
            huggingfacehub_api_token=HUGGINGFACE_TOKEN,  # 👈 변수명 수정
            model_kwargs={"temperature": 0.2, "max_length": 500}
        )
        
        # Tool 리스트 초기화
        GLOBAL_TOOLS = [DrugInfoTool()]
        
        # 초기화 완료 표시
        initial_agent = True
        
        logger.info(f"✅ LLM initialized: {REPO_ID}")
        logger.info(f"✅ Tools loaded: {[tool.name for tool in GLOBAL_TOOLS]}")
        
    except Exception as e:
        logger.error(f"❌ LLM 초기화 오류: {e}")
        huggingfacehub = None
        GLOBAL_TOOLS = []
        initial_agent = False
        raise

def create_agent_executor(memory_instance: ConversationBufferMemory):
    """세션별 Agent Executor 생성"""
    if not huggingfacehub or not initial_agent:
        raise RuntimeError("LLM이 초기화되지 않았습니다.")
    
    agent_executor = initialize_agent(
        tools=GLOBAL_TOOLS,
        llm=huggingfacehub,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        memory=memory_instance,
        handle_parsing_errors=True
    )
    
    return agent_executor

# 세션 메모리 저장소
SESSION_MEMORY_CACHE = {}

def cleanup_old_sessions(max_sessions: int = 1000):
    """메모리 캐시 정리"""
    if len(SESSION_MEMORY_CACHE) > max_sessions:
        keys_to_delete = list(SESSION_MEMORY_CACHE.keys())[:len(SESSION_MEMORY_CACHE) // 2]
        for key in keys_to_delete:
            del SESSION_MEMORY_CACHE[key]
        logger.info(f"🧹 Cleaned up {len(keys_to_delete)} old sessions")