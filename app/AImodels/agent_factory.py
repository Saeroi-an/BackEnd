# app/AImodels/agent_factory.py
"""
Agent Factory Module
LLM과 Tool을 전역으로 초기화하고, 세션별 Agent Executor를 생성합니다.
AI 파트 요구사항에 맞춰 변수명 통일: huggingfacehub, initial_agent
"""
from langchain_community.llms import HuggingFaceHub
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
import os
import logging

# tools.py에서 ALL_TOOLS 임포트
from app.AImodels.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# [A] 환경 변수 설정

HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN', '')
REPO_ID = os.getenv('LLM_REPO_ID', 'google/flan-t5-large')

# 디버깅용 로그
logger.info(f"🔍 HUGGINGFACE_TOKEN 길이: {len(HUGGINGFACE_TOKEN) if HUGGINGFACE_TOKEN else 0}")
logger.info(f"🔍 LLM_REPO_ID: {REPO_ID}")

# [B] 전역 변수 (AI 파트 요구사항에 맞춘 변수명)

huggingfacehub = None      # LLM 인스턴스 (변수명 유지 필수)
initial_agent = None       # 초기화 완료 플래그 (변수명 유지 필수)
GLOBAL_TOOLS = ALL_TOOLS   # tools.py에서 가져온 Tool 리스트


def initialize_global_agent():
    """
    전역 LLM과 Tool을 초기화
    AI 파트가 제공한 agent_initializer.py의 initialize_my_agent() 로직과 동일
    """
    global huggingfacehub, GLOBAL_TOOLS, initial_agent
    
    try:
        logger.info("🚀 Initializing Global LLM and Tools...")
        
        # 토큰 검증
        if not HUGGINGFACE_TOKEN:
            raise ValueError("HUGGINGFACE_TOKEN 환경변수가 설정되지 않았습니다.")
        
        # HuggingFace Hub LLM 초기화
        huggingfacehub = HuggingFaceHub(
            repo_id=REPO_ID,
            huggingfacehub_api_token=HUGGINGFACE_TOKEN,
            model_kwargs={"temperature": 0.1, "max_length": 512},  # AI 파트 설정값
            task="text2text-generation"
        )
        
        # Tool 리스트는 이미 tools.py에서 가져옴
        logger.info(f"✅ Tools loaded from ALL_TOOLS: {[tool.name for tool in GLOBAL_TOOLS]}")
        
        # 초기화 완료 표시
        initial_agent = True
        
        logger.info(f"✅ LLM initialized: {REPO_ID}")
        logger.info(f"✅ Total tools: {len(GLOBAL_TOOLS)}")
        
    except Exception as e:
        logger.error(f"❌ LLM 초기화 오류: {e}")
        huggingfacehub = None
        initial_agent = False
        raise


def create_agent_executor(memory_instance: ConversationBufferMemory):
    """
    세션별 Agent Executor 생성
    AI 파트가 제공한 GLOBAL_AGENT_EXECUTOR 생성 로직과 동일
    
    Args:
        memory_instance: 세션별 대화 메모리
        
    Returns:
        Agent Executor 인스턴스
    """
    if not huggingfacehub or not initial_agent:
        raise RuntimeError("LLM이 초기화되지 않았습니다. initialize_global_agent()를 먼저 실행하세요.")
    
    logger.info("🔧 Creating Agent Executor with memory...")
    
    agent_executor = initialize_agent(
        tools=GLOBAL_TOOLS,                              # ALL_TOOLS 사용
        llm=huggingfacehub,                              # 전역 LLM 사용
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,     # ReAct 방식
        verbose=True,                                    # 디버깅용 로그
        memory=memory_instance,                          # 세션별 메모리
        handle_parsing_errors=True                       # 파싱 에러 처리
    )
    
    logger.info("✅ Agent Executor created successfully")
    
    return agent_executor


# [C] 세션 메모리 캐시 (기존 코드 유지)
SESSION_MEMORY_CACHE = {}


def cleanup_old_sessions(max_sessions: int = 1000):
    """메모리 캐시 정리"""
    if len(SESSION_MEMORY_CACHE) > max_sessions:
        keys_to_delete = list(SESSION_MEMORY_CACHE.keys())[:len(SESSION_MEMORY_CACHE) // 2]
        for key in keys_to_delete:
            del SESSION_MEMORY_CACHE[key]
        logger.info(f"🧹 Cleaned up {len(keys_to_delete)} old sessions")


# [D] GLOBAL_AGENT_EXECUTOR 호환성

# AI 파트에서는 GLOBAL_AGENT_EXECUTOR를 사용하지만,
# 우리는 세션별로 Agent를 생성하는 방식을 사용하므로
# 이 변수는 참고용으로만 유지
GLOBAL_AGENT_EXECUTOR = None  # create_agent_executor()로 대체